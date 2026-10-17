"""Explain the confirmed inputs and optimal schedule without changing the solver."""

from server.checker.scenarios import _instantiate_problems
from server.labels import route_label
from server.models import PlanMapData, ScenarioResult


def clock(minute: int) -> str:
    return f"{minute // 60}:{minute % 60:02d}"


def route_reasons(plan: PlanMapData, result: ScenarioResult) -> dict[str, str]:
    problems = {problem["id"]: problem for problem in _instantiate_problems(plan)}
    active = [problems[problem_id] for problem_id in result.failures]
    absent = {p["entity_id"] for p in active if p["type_id"] == "volunteer_absent"}
    early = {p["entity_id"]: p["size"] for p in active if p["type_id"] == "volunteer_leaves_early"}
    late = {
        p["entity_id"]: p["size"]
        for p in active
        if p["type_id"] in {"vehicle_returns_late", "supply_delivery_late", "place_blocked"}
    }
    people = {person.id: person for person in plan.people}
    key_holders = [person for person in plan.people if person.holds_key and person.id not in absent]
    no_key = any(place.needs_key for place in plan.places) and not key_holders
    reasons = {}
    for route in plan.routes:
        if not any(
            event.route_id == route.id and event.event == "not_delivered"
            for event in result.timeline
        ):
            continue
        if no_key:
            reasons[route.id] = "Nobody can open the loading area."
            continue
        vehicle = next(vehicle for vehicle in plan.vehicles if vehicle.id == route.vehicle_id)
        first_free = vehicle.available_from + late.get(vehicle.id, 0)
        # Other delivered routes keep their actual intervals from the best schedule.
        # Find the first gap long enough for this route's load and drive.
        intervals = []
        for other in plan.routes:
            if other.id == route.id or other.vehicle_id != vehicle.id:
                continue
            start = next(
                (
                    e.time
                    for e in result.timeline
                    if e.route_id == other.id and e.event == "load_start"
                ),
                None,
            )
            end = next(
                (
                    e.time
                    for e in result.timeline
                    if e.route_id == other.id and e.event == "drive_end"
                ),
                None,
            )
            if start is not None and end is not None:
                intervals.append((start, end))
        for start, end in sorted(intervals):
            if first_free + route.load_minutes + route.drive_minutes <= start:
                break
            if end > first_free:
                first_free = end
        ready = max(
            [first_free]
            + [p.opens_at + late.get(p.id, 0) for p in plan.places]
            + [d.arrives_at + late.get(d.id, 0) for d in plan.deliveries]
            + ([min(p.available_from for p in key_holders)] if key_holders else [])
        )

        def person_fact(person_id: str) -> str:
            person = people[person_id]
            until = max(person.available_from, person.available_until - early.get(person_id, 0))
            if person_id in absent:
                return f"{person.name} absent"
            if until <= ready:
                verb = "leaves" if until == ready else "left"
                return f"{person.name} {verb} {clock(until)}"
            if person.available_from > ready:
                return f"{person.name} arrives {clock(person.available_from)}"
            for other in plan.routes:
                for job in ("load", "drive"):
                    begin = next(
                        (
                            e
                            for e in result.timeline
                            if e.route_id == other.id
                            and e.event == f"{job}_start"
                            and e.person_id == person_id
                        ),
                        None,
                    )
                    end = next(
                        (
                            e
                            for e in result.timeline
                            if e.route_id == other.id and e.event == f"{job}_end"
                        ),
                        None,
                    )
                    if begin and end and begin.time <= ready < end.time:
                        verb = "loading" if job == "load" else "driving"
                        return (
                            f"{person.name} {verb} {route_label(other.name)} "
                            f"until {clock(end.time)}"
                        )
            return f"{person.name} available until {clock(until)}"

        verb = "back" if vehicle.available_from > min(p.opens_at for p in plan.places) else "free"
        facts = [f"{vehicle.name} {verb} {clock(first_free)}."]
        for delivery in plan.deliveries:
            arrives = delivery.arrives_at + late.get(delivery.id, 0)
            if arrives > first_free:
                facts.append(f"{delivery.name} arrives {clock(arrives)}.")
        if all(
            pid in absent or people[pid].available_until - early.get(pid, 0) <= ready
            for pid in route.loader_ids
        ):
            facts.append("Loading team gone.")
        loaders = ", ".join(person_fact(pid) for pid in route.loader_ids)
        drivers = ", ".join(person_fact(pid) for pid in route.driver_ids)
        facts.append(f"Loaders for {route_label(route.name)}: {loaders}.")
        facts.append(f"Drivers for {route_label(route.name)}: {drivers}.")
        reasons[route.id] = " ".join(facts)
    return reasons
