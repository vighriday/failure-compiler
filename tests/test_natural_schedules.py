"""The second objective removes idle time while preserving the locked verdict."""

from server.checker.solver import solve_scenario
from server.models import Person, Place, PlanMapData, Route, Vehicle


def test_idle_time_is_removed_after_best_lateness_is_fixed():
    plan = PlanMapData(
        people=[
            Person(
                id="person-a",
                name="Driver",
                can_drive=True,
                available_from=540,
                available_until=780,
                holds_key=True,
            )
        ],
        vehicles=[Vehicle(id="vehicle-a", name="Van", available_from=540)],
        places=[
            Place(
                id="place-a",
                name="Loading",
                opens_at=540,
                one_vehicle_at_a_time=True,
                needs_key=True,
            )
        ],
        deliveries=[],
        routes=[
            Route(
                id="route-a",
                name="A",
                households=1,
                load_minutes=10,
                drive_minutes=30,
                vehicle_id="vehicle-a",
                driver_ids=["person-a"],
                loader_ids=["person-a"],
            )
        ],
        finish_time=720,
        problem_sizes={},
    )
    state, lateness, timeline, cost = solve_scenario(plan, {})
    assert (state, lateness, cost) == ("tick", 0, None)
    assert {event.event: event.time for event in timeline} == {
        "load_start": 540,
        "load_end": 550,
        "drive_start": 550,
        "drive_end": 580,
    }

    state, lateness, timeline, cost = solve_scenario(plan, {"vehicle-a": {"returns_late": 160}})
    assert state == "cross" and lateness == 20
    assert cost == "Route A: 1 households, 20 minutes late"
    assert {event.event: event.time for event in timeline} == {
        "load_start": 700,
        "load_end": 710,
        "drive_start": 710,
        "drive_end": 740,
    }
