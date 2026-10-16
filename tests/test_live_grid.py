"""The browser receives all 100 real results, in order, and can replay the cache."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from server.grid import count_results
from server.main import app
from server.models import PlanMapData, ScenarioResult
from server.session import SESSIONS, remember_map
from server.validation.models import PlanMap

ROOT = Path(__file__).resolve().parents[1]


def test_stream_matches_locked_results_and_replays_without_solving(monkeypatch) -> None:
    plan = PlanMap.from_truth_map(PlanMapData.model_validate_json(
        (ROOT / "fixtures/example-truth.json").read_text()
    ))
    fingerprint = remember_map(plan)
    SESSIONS[fingerprint].results = None
    client = TestClient(app)
    response = client.get(f"/api/run-tests?map={fingerprint}&reduced_motion=true")
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(block[6:]) for block in response.text.split("\n\n") if block]
    assert events[0]["type"] == "start"
    assert events[0]["total"] == 100
    assert len(events[0]["problems"]) == 14
    results = [event["result"] for event in events if event["type"] == "result"]
    expected = json.loads((ROOT / "fixtures/expected-results.json").read_text())
    assert [(r["scenario_id"], r["state"]) for r in results] == [
        (r["scenario_id"], r["state"]) for r in expected
    ]
    assert all(len(r["failures"]) == 1 for r in results[:14])
    assert all(len(r["failures"]) == 2 for r in results[14:])
    for event in events[1:]:
        count = event["count"]
        assert sum(count[key] for key in (
            "weak_spots", "hidden_pairs", "dimmed", "survived", "unknown", "pending"
        )) == 100
    assert events[-1]["count"]["line"] == (
        "100 tests: 1 single weak spot, 3 hidden pairs, "
        "12 already broken by the weak spot, 84 survived."
    )

    def no_solver(_plan):
        raise AssertionError("A cached fingerprint must not re-solve")

    monkeypatch.setattr("server.grid.iter_checker", no_solver)
    replay = client.get(f"/api/run-tests?map={fingerprint}&reduced_motion=true")
    assert replay.text == response.text


def test_count_line_keeps_unknown_and_pending_out_of_survived() -> None:
    results = [ScenarioResult(scenario_id="unclear", failures=["unclear"], state="qmark")]
    count = count_results(results, total=3)
    assert count.survived == 0
    assert count.unknown == 1
    assert count.pending == 2
    assert "1 unknown, 2 to go" in count.line


def test_unknown_fingerprint_does_not_run() -> None:
    assert TestClient(app).get("/api/run-tests?map=not-a-confirmed-map").status_code == 404
