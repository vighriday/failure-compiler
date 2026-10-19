"""Unedited winner output plus actual review actions matches inputs and locked verdicts."""

import hashlib
import json

from fastapi.testclient import TestClient

from server.checker.runner import run_checker
from server.checker.scenarios import generate_scenarios
from server.evaluation import align_entities, checker_fields, compare_reading
from server.main import app
from server.reading import items_for_plan, plan_from_record, questions_for_plan
from server.review import REVIEWS, confirm_review, create_review, update_review
from server.session import remember_map
from tests.validation_helpers import ROOT, confirmed_truth_map


def reviewed_example():
    path = ROOT / "fixtures/example-reading.json"
    ledger = json.loads((ROOT / "fixtures/example-corrections.json").read_text())
    assert (
        hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
        == ledger["reading_sha256"]
    )
    record = json.loads(path.read_text())
    assert hashlib.sha256(record["raw_text"].encode()).hexdigest() == ledger["raw_text_sha256"]
    plan = plan_from_record(record)
    original_loaders = {route.id: route.loader_ids[:] for route in plan.routes}
    items = items_for_plan(plan)
    state = create_review(plan, items, questions_for_plan(plan, items))
    for action in ledger["actions"]:
        update_review({"reading_id": state["reading_id"], **action})
    confirm_review({"reading_id": state["reading_id"]})
    assert len(plan.places) == 2  # The provider reading itself still contains the Hall.
    reviewed = REVIEWS[state["reading_id"]].plan
    assert {route.id: route.loader_ids for route in reviewed.routes} == original_loaders
    assert not any(action.get("field") == "loader_ids" for action in ledger["actions"])
    return reviewed


def test_reading_matches_truth():
    plan, truth = reviewed_example(), confirmed_truth_map()
    aligned, _, unmatched = align_entities(plan, truth)
    assert not unmatched
    assert checker_fields(aligned) == checker_fields(truth)
    result = compare_reading(plan, truth)
    assert result["checker_matches"] == result["checker_total"] == 100
    assert not result["different_scenarios"]
    singles, pairs = generate_scenarios(plan.checker_data())
    assert len(singles) + len(pairs) == 100
    assert plan.routes[0].name == "Route A"
    assert plan.places[0].name == "Loading bay"


def test_placeholder_fix_story_uses_the_reviewed_delivery_identity():
    plan = reviewed_example()
    fingerprint = remember_map(plan, run_checker(plan.checker_data()))
    scenario = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supply-truck"
    response = TestClient(app).post(
        "/api/suggest-fixes",
        json={
            "fingerprint": fingerprint,
            "scenario_id": scenario,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["placeholder"] is True
    suggestion = next(fix for fix in body["suggestions"] if fix["id"] == "sam-route-a-driver")
    assert suggestion["eligible"] and suggestion["new_crosses_n"] == 0
    assert len(suggestion["scenario_results"]) == 100
