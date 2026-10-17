"""Array order cannot change results or strand cached scenario IDs."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from server.checker.runner import run_checker
from server.checker.scenarios import generate_scenarios
from server.main import app
from server.models import PlanMapData
from server.session import SESSIONS, remember_map
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.models import PlanMap

ROOT = Path(__file__).resolve().parents[1]


def test_shuffled_map_has_identical_results_and_no_missing_cached_ids():
    truth = PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    shuffled = truth.model_copy(update={
        field: list(reversed(getattr(truth, field)))
        for field in ("people", "vehicles", "places", "deliveries", "routes")
    })
    expected = run_checker(truth)
    actual = run_checker(shuffled)
    assert actual == expected
    assert generate_scenarios(shuffled) == generate_scenarios(truth)
    original_map, shuffled_map = map(PlanMap.from_truth_map, (truth, shuffled))
    fingerprint = fingerprint_plan_map(original_map)
    assert fingerprint_plan_map(shuffled_map) == fingerprint
    remember_map(original_map, expected)
    remember_map(shuffled_map)
    assert shuffled_map.fingerprint == fingerprint
    response = TestClient(app).get(
        "/api/run-tests", params={"map": fingerprint, "reduced_motion": True}
    )
    events = [json.loads(line[6:]) for line in response.text.splitlines()
              if line.startswith("data: ")]
    metadata_ids = {row["scenario_id"] for row in events[0]["scenarios"]}
    cached_ids = {row["result"]["scenario_id"] for row in events if row["type"] == "result"}
    assert len(metadata_ids) == 100
    assert metadata_ids == cached_ids
    assert SESSIONS[fingerprint].plan.people[0].id == "person-ravi"
