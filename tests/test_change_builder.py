"""Coordinator changes are bounded, gated and scored through the same fix pipeline."""

import pytest
from fastapi.testclient import TestClient

from server.fixes import SCORED, apply_operations
from server.main import app
from server.models import FixOperation, ScenarioResult
from server.session import remember_map
from tests.validation_helpers import confirmed_truth_map

JOEL = "volunteer_absent__person-joel"
KEY = {"op": "give_spare_key", "target_id": "person-maya", "field": "holds_key", "value": True}


@pytest.mark.parametrize(
    "operations",
    [
        [],
        [KEY] * 4,
        [{**KEY, "target_id": "person-dave"}],
        [{**KEY, "value": False}],
        [
            {
                "op": "replace_drivers",
                "target_id": "route-a",
                "field": "driver_ids",
                "value": ["person-sam"],
            }
        ],
        [
            {
                "op": "add_driver",
                "target_id": "route-a",
                "field": "driver_ids",
                "value": ["person-sam", "person-maya"],
            }
        ],
        [
            {
                "op": "set_person_availability",
                "target_id": "person-maya",
                "field": "available_until",
                "value": "12:00",
            }
        ],
        [
            {
                "op": "set_person_availability",
                "target_id": "person-maya",
                "field": "available_until",
                "value": 400,
            }
        ],
    ],
)
def test_builder_rejects_unbounded_or_invalid_operations_before_solving(monkeypatch, operations):
    plan = confirmed_truth_map()
    fp = remember_map(plan, [ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")])
    monkeypatch.setattr(
        "server.fixes.run_checker",
        lambda _: pytest.fail("Invalid builder output reached the solver"),
    )
    response = TestClient(app).post(
        "/api/test-change", json={"fingerprint": fp, "scenario_id": JOEL, "operations": operations}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "operation",
    [
        KEY,
        {"op": "add_driver", "target_id": "route-a", "field": "driver_ids", "value": "person-sam"},
        {"op": "add_loader", "target_id": "route-c", "field": "loader_ids", "value": "person-sam"},
        {
            "op": "set_person_availability",
            "target_id": "person-maya",
            "field": "available_until",
            "value": 720,
        },
        {"op": "move_route", "target_id": "route-c", "field": "vehicle_id", "value": "vehicle-car"},
    ],
)
def test_every_builder_operation_passes_the_same_gate(operation):
    candidate = apply_operations(confirmed_truth_map(), [FixOperation.model_validate(operation)])
    assert candidate.fingerprint is None


def test_builder_cannot_forge_scores_origin_or_acceptance():
    response = TestClient(app).post(
        "/api/test-change",
        json={
            "fingerprint": "unknown",
            "scenario_id": JOEL,
            "operations": [KEY],
            "eligible": True,
            "origin": "ai",
        },
    )
    assert response.status_code == 422


def test_builder_rechecks_snapshot_after_scoring(monkeypatch):
    from server.session import SESSIONS

    plan = confirmed_truth_map()
    fp = remember_map(plan, [ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")])

    def change_during_solve(_):
        SESSIONS[fp].revision += 1
        return [ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="tick")]

    monkeypatch.setattr("server.fixes.run_checker", change_during_solve)
    response = TestClient(app).post(
        "/api/test-change", json={"fingerprint": fp, "scenario_id": JOEL, "operations": [KEY]}
    )
    assert response.status_code == 409
    assert not any(entry.suggestion.origin == "yours" for entry in SCORED.get((fp, JOEL), []))
