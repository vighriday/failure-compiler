"""A fix cannot turn unproved results into credited repairs or acceptance."""

import pytest

from server.fixes import score_fix
from server.models import ScenarioResult
from tests.validation_helpers import confirmed_truth_map

SELECTED = "volunteer_absent__person-joel"
OTHER = "vehicle_returns_late__vehicle-van"


@pytest.mark.parametrize("unknown_case", ["old_cross", "old_tick", "selected"])
def test_unknown_results_never_count_as_fixed_or_allow_acceptance(monkeypatch, unknown_case):
    before = [
        ScenarioResult(scenario_id=SELECTED, failures=[SELECTED], state="cross"),
        ScenarioResult(
            scenario_id=OTHER,
            failures=[OTHER],
            state="cross" if unknown_case == "old_cross" else "tick",
        ),
    ]
    after = [
        ScenarioResult(
            scenario_id=SELECTED,
            failures=[SELECTED],
            state="qmark" if unknown_case == "selected" else "tick",
        ),
        ScenarioResult(
            scenario_id=OTHER,
            failures=[OTHER],
            state="tick" if unknown_case == "selected" else "qmark",
        ),
    ]
    monkeypatch.setattr("server.fixes.run_checker", lambda _: after)
    scored = score_fix(
        confirmed_truth_map(),
        before,
        SELECTED,
        {
            "id": "unknown-audit",
            "description": "A synthetic change",
            "operations": [
                {
                    "op": "give_spare_key",
                    "target_id": "person-maya",
                    "field": "holds_key",
                    "value": True,
                }
            ],
        },
    )
    assert scored.plan is not None
    assert not scored.suggestion.eligible
    assert scored.suggestion.fixes_n == (0 if unknown_case == "selected" else 1)
    assert scored.suggestion.still_broken_n == 0
    assert scored.suggestion.new_crosses_n == 0
    assert scored.suggestion.rejection_reason == (
        "The checker could not determine 1 scenario. This change cannot be accepted."
    )
    assert any(result.state == "qmark" for result in scored.suggestion.scenario_results)
