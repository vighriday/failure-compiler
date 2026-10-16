"""Generated pairs only combine independent entities."""

from pathlib import Path

from server.checker.scenarios import _instantiate_problems, generate_scenarios
from server.models import PlanMapData

ROOT = Path(__file__).resolve().parents[1]


def test_no_pair_targets_the_same_entity_twice() -> None:
    plan = PlanMapData.model_validate_json(
        (ROOT / "fixtures/example-truth.json").read_text(encoding="utf-8")
    )
    problems = {item["id"]: item for item in _instantiate_problems(plan)}
    _, pairs = generate_scenarios(plan)

    assert len(pairs) == 86
    for pair in pairs:
        first, second = (problems[problem_id] for problem_id in pair["failures"])
        assert (first["entity_type"], first["entity_id"]) != (
            second["entity_type"], second["entity_id"]
        )
