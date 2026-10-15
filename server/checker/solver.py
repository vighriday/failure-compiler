"""CP-SAT solver: one run per scenario.

Models the plan as a scheduling problem where the solver minimises total
households-times-minutes-late.  Routes that cannot run (no available driver,
loading area cannot open) use a "not delivered" penalty: households * (finish_time
+ 180 minutes), keeping every scenario feasible.

Uses max_deterministic_time (not wall clock) and a fixed seed so results are
identical on every machine.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from server.config import NOT_DELIVERED_HORIZON_PADDING, SOLVER_MAX_DETERMINISTIC_TIME, SOLVER_SEED
from server.models import Person, Place, PlanMapData, Route, TimelineEvent, Vehicle


def solve_scenario(
    plan: PlanMapData,
    disabled_entities: dict[str, dict],
) -> tuple[str, int | None, list[TimelineEvent], str | None]:
    """Run CP-SAT for a single scenario.

    Args:
        plan: The confirmed plan map data.
        disabled_entities: Maps entity ids to modification dicts.
            For "absent":        {"absent": True}
            For "leaves_early":  {"leaves_early": minutes_before_end}
            For "returns_late":  {"returns_late": minutes}
            For "arrives_late":  {"arrives_late": minutes}
            For "blocked":       {"blocked": minutes_from_opens_at}

    Returns:
        (state, lateness_minutes, timeline, human_cost)
        state: "tick" | "cross" | "qmark"
    """
    model = cp_model.CpModel()

    finish_time = plan.finish_time
    horizon = finish_time + NOT_DELIVERED_HORIZON_PADDING
    not_delivered_penalty_per_household = horizon

    # Build effective entity maps with modifications applied
    people_by_id: dict[str, dict] = {}
    for p in plan.people:
        d = {
            "id": p.id, "name": p.name, "can_drive": p.can_drive,
            "available_from": p.available_from, "available_until": p.available_until,
            "holds_key": p.holds_key, "absent": False,
        }
        if p.id in disabled_entities:
            mods = disabled_entities[p.id]
            if mods.get("absent"):
                d["absent"] = True
            if "leaves_early" in mods:
                d["available_until"] = max(d["available_from"], d["available_until"] - mods["leaves_early"])
        people_by_id[p.id] = d

    vehicles_by_id: dict[str, dict] = {}
    for v in plan.vehicles:
        d = {"id": v.id, "name": v.name, "available_from": v.available_from}
        if v.id in disabled_entities:
            mods = disabled_entities[v.id]
            if "returns_late" in mods:
                d["available_from"] = v.available_from + mods["returns_late"]
        vehicles_by_id[v.id] = d

    deliveries_by_id: dict[str, dict] = {}
    for dl in plan.deliveries:
        d = {"id": dl.id, "name": dl.name, "arrives_at": dl.arrives_at, "place_id": dl.place_id}
        if dl.id in disabled_entities:
            mods = disabled_entities[dl.id]
            if "arrives_late" in mods:
                d["arrives_at"] = dl.arrives_at + mods["arrives_late"]
        deliveries_by_id[d["id"]] = d

    places_by_id: dict[str, dict] = {}
    for pl in plan.places:
        d = {
            "id": pl.id, "name": pl.name, "opens_at": pl.opens_at,
            "one_vehicle_at_a_time": pl.one_vehicle_at_a_time,
            "needs_key": pl.needs_key, "blocked_until": pl.opens_at,
        }
        if pl.id in disabled_entities:
            mods = disabled_entities[pl.id]
            if "blocked" in mods:
                d["blocked_until"] = pl.opens_at + mods["blocked"]
        places_by_id[d["id"]] = d

    routes = list(plan.routes)

    # Find the loading area (the place with needs_key or one_vehicle_at_a_time)
    loading_place_id: str | None = None
    for pl in places_by_id.values():
        if pl["one_vehicle_at_a_time"]:
            loading_place_id = pl["id"]
            break

    # Determine earliest loading start based on key holders and deliveries
    loading_place = places_by_id.get(loading_place_id, {}) if loading_place_id else {}
    earliest_loading = loading_place.get("blocked_until", loading_place.get("opens_at", 0))

    # If the place needs a key, loading can't start until a key holder is present
    if loading_place.get("needs_key"):
        earliest_key_holder = horizon
        for pid, pdata in people_by_id.items():
            if pdata["holds_key"] and not pdata["absent"]:
                earliest_key_holder = min(earliest_key_holder, pdata["available_from"])
        earliest_loading = max(earliest_loading, earliest_key_holder)

    # Deliveries to the loading place also constrain start
    for dl in deliveries_by_id.values():
        if dl["place_id"] == loading_place_id:
            earliest_loading = max(earliest_loading, dl["arrives_at"])

    # --- Build CP-SAT model ---
    # For each route: decide if it's "delivered" or "not_delivered",
    # and if delivered, schedule its load and drive.

    route_vars: dict[str, dict] = {}
    all_lateness_terms: list = []

    for route in routes:
        r = route
        rv: dict = {}
        route_vars[r.id] = rv

        # Check which drivers and loaders are actually available
        available_drivers = [
            did for did in r.driver_ids
            if did in people_by_id and not people_by_id[did]["absent"] and people_by_id[did]["can_drive"]
        ]
        available_loaders = [
            lid for lid in r.loader_ids
            if lid in people_by_id and not people_by_id[lid]["absent"]
        ]

        vehicle_data = vehicles_by_id.get(r.vehicle_id)

        # If no drivers, no loaders, or no vehicle, route cannot be delivered
        if not available_drivers or not available_loaders or vehicle_data is None:
            rv["delivered"] = False
            rv["lateness"] = r.households * not_delivered_penalty_per_household
            rv["human_cost"] = f"Route {r.name}: {r.households} households not delivered"
            all_lateness_terms.append(r.households * not_delivered_penalty_per_household)
            continue

        # Boolean: is this route delivered?
        is_delivered = model.new_bool_var(f"delivered_{r.id}")
        rv["is_delivered"] = is_delivered

        # Load start/end, drive start/end
        load_start = model.new_int_var(0, horizon, f"load_start_{r.id}")
        load_end = model.new_int_var(0, horizon, f"load_end_{r.id}")
        drive_start = model.new_int_var(0, horizon, f"drive_start_{r.id}")
        drive_end = model.new_int_var(0, horizon, f"drive_end_{r.id}")

        rv["load_start"] = load_start
        rv["load_end"] = load_end
        rv["drive_start"] = drive_start
        rv["drive_end"] = drive_end

        # If delivered: load_end = load_start + load_minutes, drive_end = drive_start + drive_minutes
        # drive_start >= load_end
        model.add(load_end == load_start + r.load_minutes).only_enforce_if(is_delivered)
        model.add(drive_end == drive_start + r.drive_minutes).only_enforce_if(is_delivered)
        model.add(drive_start >= load_end).only_enforce_if(is_delivered)

        # Loading can't start before earliest_loading
        model.add(load_start >= earliest_loading).only_enforce_if(is_delivered)

        # Vehicle available_from constraint
        model.add(load_start >= vehicle_data["available_from"]).only_enforce_if(is_delivered)

        # If not delivered, zero out the times
        model.add(load_start == 0).only_enforce_if(is_delivered.negated())
        model.add(load_end == 0).only_enforce_if(is_delivered.negated())
        model.add(drive_start == 0).only_enforce_if(is_delivered.negated())
        model.add(drive_end == 0).only_enforce_if(is_delivered.negated())

        # Driver assignment: exactly one driver assigned if delivered
        driver_assigned = {}
        for did in available_drivers:
            dvar = model.new_bool_var(f"driver_{r.id}_{did}")
            driver_assigned[did] = dvar

        if available_drivers:
            model.add(sum(driver_assigned.values()) == 1).only_enforce_if(is_delivered)
            model.add(sum(driver_assigned.values()) == 0).only_enforce_if(is_delivered.negated())

        # Driver availability: if assigned, drive must be within their window
        for did, dvar in driver_assigned.items():
            pdata = people_by_id[did]
            model.add(drive_start >= pdata["available_from"]).only_enforce_if(dvar)
            model.add(drive_end <= pdata["available_until"]).only_enforce_if(dvar)

        rv["driver_assigned"] = driver_assigned

        # Loader assignment: exactly one loader assigned if delivered
        loader_assigned = {}
        for lid in available_loaders:
            lvar = model.new_bool_var(f"loader_{r.id}_{lid}")
            loader_assigned[lid] = lvar

        if available_loaders:
            model.add(sum(loader_assigned.values()) == 1).only_enforce_if(is_delivered)
            model.add(sum(loader_assigned.values()) == 0).only_enforce_if(is_delivered.negated())

        # Loader availability: if assigned, load must be within their window
        for lid, lvar in loader_assigned.items():
            pdata = people_by_id[lid]
            model.add(load_start >= pdata["available_from"]).only_enforce_if(lvar)
            model.add(load_end <= pdata["available_until"]).only_enforce_if(lvar)

        rv["loader_assigned"] = loader_assigned

        # Lateness: max(0, drive_end - finish_time) * households if delivered,
        #           not_delivered_penalty if not delivered
        lateness = model.new_int_var(0, r.households * not_delivered_penalty_per_household, f"lateness_{r.id}")
        rv["lateness"] = lateness

        # If delivered, lateness = max(0, drive_end - finish_time) * households
        over = model.new_int_var(0, horizon, f"over_{r.id}")
        model.add(over >= drive_end - finish_time).only_enforce_if(is_delivered)
        model.add(over >= 0)
        # over <= drive_end - finish_time is not needed; minimisation will push it down

        delivered_lateness = model.new_int_var(
            0, r.households * horizon, f"del_lateness_{r.id}"
        )
        # delivered_lateness = over * households
        model.add(delivered_lateness == over * r.households).only_enforce_if(is_delivered)
        model.add(delivered_lateness == 0).only_enforce_if(is_delivered.negated())

        not_delivered_cost = r.households * not_delivered_penalty_per_household
        # lateness = delivered_lateness if delivered, not_delivered_cost if not
        model.add(lateness == delivered_lateness).only_enforce_if(is_delivered)
        model.add(lateness == not_delivered_cost).only_enforce_if(is_delivered.negated())

        all_lateness_terms.append(lateness)

    # --- Person-at-a-time constraints ---
    # A person cannot be in two places at once: if person P is assigned to
    # drive route X and load route Y, their intervals must not overlap.
    # Also, a person can't load and drive at the same time (even for different routes).
    person_intervals: dict[str, list] = {}
    for route in routes:
        rv = route_vars[route.id]
        if "is_delivered" not in rv:
            continue
        is_del = rv["is_delivered"]

        # Driver intervals
        for did, dvar in rv.get("driver_assigned", {}).items():
            both = model.new_bool_var(f"both_drv_{route.id}_{did}")
            model.add_bool_and([is_del, dvar]).only_enforce_if(both)
            model.add_bool_or([is_del.negated(), dvar.negated()]).only_enforce_if(both.negated())
            interval = model.new_optional_fixed_size_interval_var(
                rv["drive_start"], route.drive_minutes, both, f"drv_int_{route.id}_{did}"
            )
            person_intervals.setdefault(did, []).append(interval)

        # Loader intervals
        for lid, lvar in rv.get("loader_assigned", {}).items():
            both = model.new_bool_var(f"both_ldr_{route.id}_{lid}")
            model.add_bool_and([is_del, lvar]).only_enforce_if(both)
            model.add_bool_or([is_del.negated(), lvar.negated()]).only_enforce_if(both.negated())
            interval = model.new_optional_fixed_size_interval_var(
                rv["load_start"], route.load_minutes, both, f"ldr_int_{route.id}_{lid}"
            )
            person_intervals.setdefault(lid, []).append(interval)

    for pid, intervals in person_intervals.items():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)

    # --- Vehicle-at-a-time constraints ---
    # Each vehicle can only do one route at a time (load + drive is one block per route)
    vehicle_intervals: dict[str, list] = {}
    for route in routes:
        rv = route_vars[route.id]
        if "is_delivered" not in rv:
            continue
        is_del = rv["is_delivered"]
        # The vehicle is busy from load_start to drive_end
        total_duration = route.load_minutes + route.drive_minutes
        # Use a variable-size interval from load_start to drive_end
        size_var = model.new_int_var(0, horizon, f"veh_size_{route.id}")
        model.add(size_var == rv["drive_end"] - rv["load_start"]).only_enforce_if(is_del)
        model.add(size_var == 0).only_enforce_if(is_del.negated())
        interval = model.new_optional_interval_var(
            rv["load_start"], size_var, rv["drive_end"], is_del, f"veh_int_{route.id}"
        )
        vehicle_intervals.setdefault(route.vehicle_id, []).append(interval)

    for vid, intervals in vehicle_intervals.items():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)

    # --- One vehicle at loading area at a time ---
    if loading_place_id and loading_place.get("one_vehicle_at_a_time"):
        loading_intervals = []
        for route in routes:
            rv = route_vars[route.id]
            if "is_delivered" not in rv:
                continue
            is_del = rv["is_delivered"]
            interval = model.new_optional_fixed_size_interval_var(
                rv["load_start"], route.load_minutes, is_del, f"loading_int_{route.id}"
            )
            loading_intervals.append(interval)
        if len(loading_intervals) > 1:
            model.add_no_overlap(loading_intervals)

    # Minimise total lateness
    if all_lateness_terms:
        # Separate constant terms from variable terms
        constant_sum = 0
        variable_terms = []
        for term in all_lateness_terms:
            if isinstance(term, int):
                constant_sum += term
            else:
                variable_terms.append(term)

        if variable_terms:
            total = model.new_int_var(
                0,
                sum(r.households for r in routes) * (horizon + not_delivered_penalty_per_household),
                "total_lateness",
            )
            model.add(total == sum(variable_terms) + constant_sum)
            model.minimize(total)
        # If only constants, there's nothing to optimise
    else:
        total = model.new_int_var(0, 0, "total_lateness")
        model.minimize(total)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_deterministic_time = SOLVER_MAX_DETERMINISTIC_TIME
    solver.parameters.random_seed = SOLVER_SEED
    solver.parameters.num_workers = 1

    status = solver.solve(model)

    if status == cp_model.OPTIMAL:
        # Compute total lateness from solution
        total_lateness = 0
        late_routes: list[str] = []
        not_delivered_routes: list[str] = []
        timeline_events: list[TimelineEvent] = []

        for route in routes:
            rv = route_vars[route.id]
            if "is_delivered" not in rv:
                # Route was forced not-delivered
                total_lateness += rv["lateness"]
                not_delivered_routes.append(route.name)
                timeline_events.append(TimelineEvent(
                    route_id=route.id, event="not_delivered", time=0,
                ))
                continue

            is_del_val = solver.value(rv["is_delivered"])
            if not is_del_val:
                total_lateness += route.households * not_delivered_penalty_per_household
                not_delivered_routes.append(route.name)
                timeline_events.append(TimelineEvent(
                    route_id=route.id, event="not_delivered", time=0,
                ))
                continue

            ls = solver.value(rv["load_start"])
            le = solver.value(rv["load_end"])
            ds = solver.value(rv["drive_start"])
            de = solver.value(rv["drive_end"])

            # Find who was assigned
            assigned_driver = None
            for did, dvar in rv.get("driver_assigned", {}).items():
                if solver.value(dvar):
                    assigned_driver = did
                    break

            assigned_loader = None
            for lid, lvar in rv.get("loader_assigned", {}).items():
                if solver.value(lvar):
                    assigned_loader = lid
                    break

            timeline_events.extend([
                TimelineEvent(route_id=route.id, event="load_start", time=ls,
                              person_id=assigned_loader, vehicle_id=route.vehicle_id),
                TimelineEvent(route_id=route.id, event="load_end", time=le,
                              person_id=assigned_loader, vehicle_id=route.vehicle_id),
                TimelineEvent(route_id=route.id, event="drive_start", time=ds,
                              person_id=assigned_driver, vehicle_id=route.vehicle_id),
                TimelineEvent(route_id=route.id, event="drive_end", time=de,
                              person_id=assigned_driver, vehicle_id=route.vehicle_id),
            ])

            route_lateness_minutes = max(0, de - finish_time)
            if route_lateness_minutes > 0:
                total_lateness += route_lateness_minutes * route.households
                late_routes.append(
                    f"Route {route.name}: {route.households} households, "
                    f"{route_lateness_minutes} minutes late"
                )

        if total_lateness == 0:
            return "tick", 0, timeline_events, None

        # Build human cost string
        cost_parts = []
        if not_delivered_routes:
            nd_households = sum(
                r.households for r in routes if r.name in not_delivered_routes
            )
            cost_parts.append(
                f"{'Routes ' if len(not_delivered_routes) > 1 else 'Route '}"
                f"{', '.join(not_delivered_routes)}: {nd_households} households not delivered"
            )
            # Add reason if loading area can't open
            if loading_place.get("needs_key"):
                key_holders_present = [
                    people_by_id[pid]["name"]
                    for pid in people_by_id
                    if people_by_id[pid]["holds_key"] and not people_by_id[pid]["absent"]
                ]
                if not key_holders_present:
                    cost_parts[-1] += ". Nobody can open the loading area"
        cost_parts.extend(late_routes)
        human_cost = ". ".join(cost_parts) if cost_parts else None

        return "cross", total_lateness, timeline_events, human_cost

    elif status == cp_model.FEASIBLE:
        # Feasible but not proven optimal -> question mark
        best = solver.objective_value
        return "qmark", int(best), [], f"Solver found a solution but could not prove optimality"

    else:
        # Should not happen with our "not delivered" penalty making everything feasible
        # But just in case: qmark
        return "qmark", None, [], "Solver returned no solution"
