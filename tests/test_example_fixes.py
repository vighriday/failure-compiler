"""The demo's fix story, applied to the truth map with the fixed fix operations."""

from pathlib import Path

from server.checker.runner import run_checker
from server.models import PlanMapData

ROOT = Path(__file__).resolve().parents[1]

JOEL_ABSENT = "volunteer_absent__person-joel"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supplies"
VAN_ANITA_LEAVES = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
VAN_ANITA_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"
JOEL_MAYA_ABSENT = "volunteer_absent__person-joel+volunteer_absent__person-maya"
ORIGINAL_CROSSES = {JOEL_ABSENT, TRUCK_RAVI, VAN_ANITA_LEAVES, VAN_ANITA_ABSENT}


def example_plan() -> PlanMapData:
    return PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())


def add_driver(plan: PlanMapData, route_id: str, person_id: str) -> PlanMapData:
    routes = [
        route.model_copy(update={"driver_ids": route.driver_ids + [person_id]})
        if route.id == route_id and person_id not in route.driver_ids else route
        for route in plan.routes
    ]
    return plan.model_copy(update={"routes": routes})


def add_loader(plan: PlanMapData, route_id: str, person_id: str) -> PlanMapData:
    routes = [
        route.model_copy(update={"loader_ids": route.loader_ids + [person_id]})
        if route.id == route_id and person_id not in route.loader_ids else route
        for route in plan.routes
    ]
    return plan.model_copy(update={"routes": routes})


def give_spare_keys(plan: PlanMapData, *person_ids: str) -> PlanMapData:
    """Spare keys are additive: existing holders keep theirs."""
    people = [
        person.model_copy(update={"holds_key": True}) if person.id in person_ids else person
        for person in plan.people
    ]
    return plan.model_copy(update={"people": people})


def crosses(plan: PlanMapData) -> set[str]:
    return {result.scenario_id for result in run_checker(plan) if result.state == "cross"}


def test_original_crosses() -> None:
    assert crosses(example_plan()) == ORIGINAL_CROSSES


def test_obvious_fix_is_turned_down() -> None:
    # "Add Maya as another backup driver for Route C" fixes nothing: the gap is
    # loading, not driving, and Maya leaves at 10:45 anyway.
    plan = add_driver(example_plan(), "route-c", "person-maya")
    assert crosses(plan) == ORIGINAL_CROSSES


def test_sam_loads_route_c_fixes_both_van_pairs() -> None:
    # Sam brings the van back at 10:45; letting him load Route C closes the gap.
    plan = add_loader(example_plan(), "route-c", "person-sam")
    assert crosses(plan) == {JOEL_ABSENT, TRUCK_RAVI}


def test_sam_backs_up_route_a_fixes_truck_pair() -> None:
    plan = add_driver(example_plan(), "route-a", "person-sam")
    assert crosses(plan) == {JOEL_ABSENT, VAN_ANITA_LEAVES, VAN_ANITA_ABSENT}


def test_one_spare_key_reveals_a_new_hidden_pair() -> None:
    fixed = add_driver(add_loader(example_plan(), "route-c", "person-sam"), "route-a", "person-sam")
    # One spare key fixes "Joel absent" but turns "Joel + Maya absent" into a cross.
    assert crosses(give_spare_keys(fixed, "person-maya")) == {JOEL_MAYA_ABSENT}


def test_all_fixes_survive_every_scenario() -> None:
    fixed = add_driver(add_loader(example_plan(), "route-c", "person-sam"), "route-a", "person-sam")
    results = run_checker(give_spare_keys(fixed, "person-maya", "person-sam"))
    assert len(results) == 105
    assert all(result.state == "tick" for result in results)


def test_spare_keys_first_create_no_new_crosses() -> None:
    plan = give_spare_keys(example_plan(), "person-maya", "person-sam")
    assert crosses(plan) == {TRUCK_RAVI, VAN_ANITA_LEAVES, VAN_ANITA_ABSENT}
