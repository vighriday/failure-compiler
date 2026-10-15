from pathlib import Path

from server.checker.runner import run_checker
from server.models import PlanMapData

ROOT = Path(__file__).resolve().parents[1]


def test_checker_monotone() -> None:
    plan = PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    results = {result.scenario_id: result for result in run_checker(plan)}

    for pair in results.values():
        if len(pair.failures) != 2 or pair.state == "dim":
            continue
        for problem_id in pair.failures:
            single = results[problem_id]
            assert pair.lateness_minutes is not None
            assert single.lateness_minutes is not None
            assert pair.lateness_minutes >= single.lateness_minutes
