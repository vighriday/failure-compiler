from pathlib import Path

from server.checker.runner import run_checker
from server.models import PlanMapData

ROOT = Path(__file__).resolve().parents[1]


def test_determinism() -> None:
    plan = PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    first = [result.model_dump(mode="json") for result in run_checker(plan)]
    second = [result.model_dump(mode="json") for result in run_checker(plan)]

    assert first == second
