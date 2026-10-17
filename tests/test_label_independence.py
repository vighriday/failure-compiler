"""Changing or duplicating labels cannot alter identity, schedules, totals or fingerprints."""

from server.checker.runner import run_checker
from server.session import SESSIONS, remember_map
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.gate import validate_ai_reading
from tests.validation_helpers import ai_reading_payload, confirmed_truth_map


def test_normaliser_never_doubles_type_words():
    payload = ai_reading_payload()
    payload["routes"][0]["name"] = "Route A"
    assert validate_ai_reading(payload).routes[0].id == "route-a"


def test_all_label_changes_leave_fingerprint_and_numeric_results_unchanged():
    truth = confirmed_truth_map()
    changed = truth.model_copy(deep=True)
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in getattr(changed, collection):
            entity.name = "A shared display label"
    assert fingerprint_plan_map(changed) == fingerprint_plan_map(truth)
    before, after = run_checker(truth.checker_data()), run_checker(changed.checker_data())
    for original, relabelled in zip(before, after):
        assert original.model_dump(exclude={"human_cost"}) == relabelled.model_dump(
            exclude={"human_cost"}
        )
    joel = next(result for result in after if result.scenario_id == "volunteer_absent__person-joel")
    assert "30 households not delivered" in joel.human_cost


def test_equivalent_new_labels_cannot_replay_stale_cached_ids():
    truth = confirmed_truth_map()
    fingerprint = remember_map(truth, [])
    changed = truth.model_copy(deep=True)
    changed.vehicles[0].name = "Different van label"
    assert remember_map(changed) == fingerprint
    assert SESSIONS[fingerprint].results is None
    assert SESSIONS[fingerprint].plan.vehicles[0].name == "Different van label"
