"""The second objective removes idle time while preserving the locked verdict."""

from server.checker.solver import solve_scenario
from server.models import Person, Place, PlanMapData, Route, Vehicle


def single_route_plan():
    return PlanMapData(
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


def test_idle_time_is_removed_after_best_lateness_is_fixed():
    plan = single_route_plan()
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


def test_secondary_timeout_preserves_the_proven_verdict(monkeypatch):
    from ortools.sat.python import cp_model

    original = cp_model.CpSolver.solve
    calls = []

    def solve(self, model, *args, **kwargs):
        calls.append(model)
        if len(calls) == 2:
            return cp_model.UNKNOWN
        return original(self, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", solve)
    state, lateness, timeline, cost = solve_scenario(
        single_route_plan(), {"vehicle-a": {"returns_late": 160}}
    )
    assert len(calls) == 2
    assert (state, lateness, cost) == ("cross", 20, "Route A: 1 households, 20 minutes late")
    assert timeline
