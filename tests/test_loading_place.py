"""Capacity is independent of loading-place access, supply and opening constraints."""

import pytest

from server.checker.solver import solve_scenario
from server.models import Delivery, Person, Place, PlanMapData, Route, Vehicle
from server.validation.rules import validate_plan_rules
from tests.validation_helpers import confirmed_truth_map


def parallel_plan() -> PlanMapData:
    return PlanMapData(
        people=[
            Person(
                id=f"person-{letter}",
                name=letter,
                can_drive=True,
                available_from=540,
                available_until=780,
                holds_key=False,
            )
            for letter in ("a", "b")
        ],
        vehicles=[
            Vehicle(id=f"vehicle-{letter}", name=letter, available_from=540)
            for letter in ("a", "b")
        ],
        places=[
            Place(
                id="place-bay",
                name="Bay",
                opens_at=540,
                one_vehicle_at_a_time=False,
                needs_key=False,
            )
        ],
        deliveries=[
            Delivery(id="delivery-supply", name="Supplies", arrives_at=540, place_id="place-bay")
        ],
        routes=[
            Route(
                id=f"route-{letter}",
                name=letter,
                households=1,
                load_minutes=30,
                drive_minutes=30,
                vehicle_id=f"vehicle-{letter}",
                driver_ids=[f"person-{letter}"],
                loader_ids=[f"person-{letter}"],
            )
            for letter in ("a", "b")
        ],
        finish_time=600,
        problem_sizes=confirmed_truth_map().problem_sizes,
    )


def test_parallel_loading_does_not_bypass_the_only_key():
    plan = confirmed_truth_map().checker_data()
    plan.places[0].one_vehicle_at_a_time = False
    assert not validate_plan_rules(plan)
    state, _, timeline, cost = solve_scenario(plan, {"person-joel": {"absent": True}})
    assert state == "cross"
    assert "30 households not delivered" in cost
    assert "Nobody can open the loading area" in cost
    assert all(event.event == "not_delivered" for event in timeline)


@pytest.mark.parametrize("constraint", ["opening", "delivery", "delivery_late", "blocked"])
def test_parallel_loading_keeps_opening_supply_and_blocked_times(constraint):
    plan = parallel_plan()
    plan.finish_time = 720
    changes, expected = {}, 540
    if constraint == "opening":
        plan.places[0].opens_at = expected = 600
    elif constraint == "delivery":
        plan.deliveries[0].arrives_at = expected = 600
    elif constraint == "delivery_late":
        changes = {"delivery-supply": {"arrives_late": 45}}
        expected = 585
    else:
        changes = {"place-bay": {"blocked": 30}}
        expected = 570
    state, _, timeline, _ = solve_scenario(plan, changes)
    assert state == "tick"
    assert [event.time for event in timeline if event.event == "load_start"] == [expected, expected]


def test_capacity_flag_only_controls_whether_the_loads_overlap():
    plan = parallel_plan()
    state, _, timeline, _ = solve_scenario(plan, {})
    assert state == "tick"
    assert sorted(event.time for event in timeline if event.event == "load_start") == [540, 540]
    plan.places[0].one_vehicle_at_a_time = True
    state, _, timeline, _ = solve_scenario(plan, {})
    assert state == "cross"
    assert sorted(event.time for event in timeline if event.event == "load_start") == [540, 570]


def test_unique_delivery_destination_identifies_a_nonexclusive_place():
    plan = parallel_plan()
    plan.finish_time = 720
    plan.places[0].opens_at = 600
    plan.places.insert(
        0,
        Place(
            id="place-unused",
            name="Unused",
            opens_at=540,
            one_vehicle_at_a_time=False,
            needs_key=False,
        ),
    )
    state, _, timeline, _ = solve_scenario(plan, {})
    assert state == "tick"
    assert [event.time for event in timeline if event.event == "load_start"] == [600, 600]


def test_unique_keyed_place_is_identified_among_unused_places_without_a_delivery():
    plan = parallel_plan()
    plan.finish_time = 720
    plan.deliveries = []
    plan.places[0].needs_key = True
    plan.places.insert(
        0,
        plan.places[0].model_copy(
            update={
                "id": "place-unused",
                "name": "Unused",
                "needs_key": False,
            }
        ),
    )
    plan.people[0].holds_key = True
    plan.people[0].available_from = 600
    state, _, timeline, _ = solve_scenario(plan, {})
    assert state == "tick"
    assert [event.time for event in timeline if event.event == "load_start"] == [600, 600]


@pytest.mark.parametrize("role", ["one_vehicle_at_a_time", "needs_key", "destination"])
def test_ambiguous_loading_areas_return_unknown_without_partial_output(role):
    plan = parallel_plan()
    second = plan.places[0].model_copy(update={"id": "place-second", "name": "Second"})
    plan.places.append(second)
    if role == "destination":
        plan.deliveries.append(
            plan.deliveries[0].model_copy(
                update={
                    "id": "delivery-second",
                    "place_id": "place-second",
                }
            )
        )
    else:
        for place in plan.places:
            setattr(place, role, True)
    assert solve_scenario(plan, {}) == (
        "qmark",
        None,
        [],
        "The checker needs one unambiguous loading area.",
    )
