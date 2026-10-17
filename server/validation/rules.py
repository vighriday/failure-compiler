"""Plain consistency rules for maps after they pass the format gate."""

from __future__ import annotations

from dataclasses import dataclass

from server.config import PROBLEM_CAP, PROBLEM_TYPES, SIZE_PRESETS
from server.models import PlanMapData
from server.validation.models import PlanMap


@dataclass(frozen=True)
class RuleViolation:
    item_id: str
    field: str
    bad_value: object
    message: str


def _checker_data(plan: PlanMap | PlanMapData) -> PlanMapData:
    return plan.checker_data() if isinstance(plan, PlanMap) else plan


def validate_plan_rules(plan: PlanMap | PlanMapData) -> list[RuleViolation]:
    """Return every rule issue; callers decide how to show them to the user."""
    data = _checker_data(plan)
    issues: list[RuleViolation] = []
    people = {person.id: person for person in data.people}
    vehicles = {vehicle.id: vehicle for vehicle in data.vehicles}
    places = {place.id: place for place in data.places}

    for field in ("people", "routes"):
        if not getattr(data, field):
            issues.append(RuleViolation(field, field, [], f"The plan needs at least one {field}"))

    times = [("finish_time", "finish_time", data.finish_time)]
    times += [
        (person.id, field, getattr(person, field))
        for person in data.people
        for field in ("available_from", "available_until")
    ]
    times += [(vehicle.id, "available_from", vehicle.available_from) for vehicle in data.vehicles]
    times += [(place.id, "opens_at", place.opens_at) for place in data.places]
    times += [(delivery.id, "arrives_at", delivery.arrives_at) for delivery in data.deliveries]
    for entity_id, field, value in times:
        if not 0 <= value < 1440:
            issues.append(
                RuleViolation(
                    entity_id,
                    field,
                    value,
                    f"{entity_id} {field} value {value!r} must be within the day (0 to 1439)",
                )
            )

    for person in data.people:
        if person.available_from >= person.available_until:
            issues.append(
                RuleViolation(
                    person.id,
                    "available_until",
                    person.available_until,
                    (
                        f"{person.name} is unavailable until {person.available_until} "
                        f"before they are available at {person.available_from}"
                    ),
                )
            )

    for vehicle in data.vehicles:
        if vehicle.available_from > data.finish_time:
            issues.append(
                RuleViolation(
                    vehicle.id,
                    "available_from",
                    vehicle.available_from,
                    f"{vehicle.name} is not available before the plan finish time",
                )
            )

    for place in data.places:
        if (
            (place.one_vehicle_at_a_time or place.needs_key)
            and not any(delivery.place_id == place.id for delivery in data.deliveries)
            and place.id not in getattr(plan, "no_delivery_place_ids", [])
        ):
            issues.append(
                RuleViolation(
                    place.id,
                    "supply_delivery",
                    None,
                    "The loading area has no supply delivery listed. Is one expected?",
                )
            )
        if place.opens_at > data.finish_time:
            issues.append(
                RuleViolation(
                    place.id,
                    "opens_at",
                    place.opens_at,
                    f"{place.name} opens after the plan finish time",
                )
            )

    for delivery in data.deliveries:
        if delivery.place_id not in places:
            issues.append(
                RuleViolation(
                    delivery.id,
                    "place_id",
                    delivery.place_id,
                    f"Unknown place id '{delivery.place_id}' in {delivery.id} place_id",
                )
            )
        if delivery.arrives_at > data.finish_time:
            issues.append(
                RuleViolation(
                    delivery.id,
                    "arrives_at",
                    delivery.arrives_at,
                    f"{delivery.name} arrives after the plan finish time",
                )
            )

    for route in data.routes:
        if not route.driver_ids:
            issues.append(
                RuleViolation(route.id, "driver_ids", [], f"{route.name} needs at least one driver")
            )
        for person_id in route.driver_ids:
            person = people.get(person_id)
            if person is None:
                issues.append(
                    RuleViolation(
                        route.id,
                        "driver_ids",
                        person_id,
                        f"Unknown person id '{person_id}' in {route.id} driver_ids",
                    )
                )
            elif not person.can_drive:
                issues.append(
                    RuleViolation(
                        route.id,
                        "driver_ids",
                        person_id,
                        f"{person.name} cannot drive but is listed in {route.id} driver_ids",
                    )
                )
        for person_id in route.loader_ids:
            if person_id not in people:
                issues.append(
                    RuleViolation(
                        route.id,
                        "loader_ids",
                        person_id,
                        f"Unknown person id '{person_id}' in {route.id} loader_ids",
                    )
                )
        if route.vehicle_id not in vehicles:
            issues.append(
                RuleViolation(
                    route.id,
                    "vehicle_id",
                    route.vehicle_id,
                    f"Unknown vehicle id '{route.vehicle_id}' in {route.id} vehicle_id"
                    if route.vehicle_id
                    else f"{route.name} has no vehicle. Choose a vehicle.",
                )
            )
        if not route.loader_ids:
            issues.append(
                RuleViolation(route.id, "loader_ids", [], f"{route.name} needs at least one loader")
            )
        for field in ("households", "load_minutes", "drive_minutes"):
            value = getattr(route, field)
            valid = (
                1 <= value <= 500
                if field == "households"
                else (5 <= value <= 240 and value % 5 == 0)
            )
            if not valid:
                issues.append(
                    RuleViolation(
                        route.id,
                        field,
                        value,
                        f"{route.name} {field} value {value!r} must be "
                        + ("1 to 500" if field == "households" else "5 to 240 in 5-minute steps"),
                    )
                )

    problem_count = 0
    for problem_type in PROBLEM_TYPES:
        applies_to = problem_type["applies_to"]
        entities = {
            "person": data.people,
            "vehicle": data.vehicles,
            "place": data.places,
            "delivery": data.deliveries,
        }[applies_to]
        problem_count += len(entities)
        if problem_type["has_size"]:
            size = data.problem_sizes.get(problem_type["id"])
            if size is None:
                issues.append(
                    RuleViolation(
                        "problem_sizes",
                        problem_type["id"],
                        None,
                        f"Missing size for problem type '{problem_type['id']}'",
                    )
                )
            elif size not in SIZE_PRESETS:
                issues.append(
                    RuleViolation(
                        "problem_sizes",
                        problem_type["id"],
                        size,
                        f"Size {size} for '{problem_type['id']}' is not an allowed preset",
                    )
                )

    if problem_count > PROBLEM_CAP:
        issues.append(
            RuleViolation(
                "problem_sizes",
                "problem_count",
                problem_count,
                (
                    f"This version supports up to {PROBLEM_CAP} problems. "
                    f"This plan has {problem_count}."
                ),
            )
        )
    if data.finish_time <= 0:
        issues.append(
            RuleViolation(
                "finish_time",
                "finish_time",
                data.finish_time,
                "Finish time must be a positive time",
            )
        )
    return issues


def set_person_can_drive(
    plan: PlanMap, person_id: str, can_drive: bool
) -> tuple[PlanMap, list[RuleViolation]]:
    """Apply a person correction, clear dependent route confirmations, and re-run rules."""
    person = next((item for item in plan.people if item.id == person_id), None)
    if person is None:
        raise ValueError(f"Unknown person id '{person_id}'")

    updated_people = [
        item.model_copy(update={"can_drive": can_drive, "status": "corrected"})
        if item.id == person_id
        else item
        for item in plan.people
    ]
    affected_route_ids = {route.id for route in plan.routes if person_id in route.driver_ids}
    updated_routes = [
        route.model_copy(update={"status": "unconfirmed"})
        if route.id in affected_route_ids
        else route
        for route in plan.routes
    ]
    updated_plan = plan.model_copy(
        update={"people": updated_people, "routes": updated_routes, "fingerprint": None}
    )
    return updated_plan, validate_plan_rules(updated_plan)
