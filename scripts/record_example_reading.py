"""Make the one authorised primary reading and stop if the existing controls cannot reach truth."""

import json
import logging
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.bakeoff import compare, flatten, wait_for_groq  # noqa: E402
from server.ai.adapter import read_plan  # noqa: E402
from server.ai.types import AIError  # noqa: E402
from server.facts import FIELDS  # noqa: E402
from server.models import PlanMapData  # noqa: E402
from server.validation.gate import normalise_plan_map_ids, plan_map_from_reading  # noqa: E402
from server.validation.models import PlanMap  # noqa: E402

OUT = ROOT / "devpost/screens/live-candidates"


def correction_audit(plan: PlanMap) -> dict:
    """Do not rename, add or remove entities: none is an approved Part 1 correction."""
    truth = normalise_plan_map_ids(
        PlanMap.from_truth_map(
            PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
        )
    )
    candidate = normalise_plan_map_ids(plan)
    uneditable = []
    corrections = []
    for kind, collection in {
        "person": "people",
        "vehicle": "vehicles",
        "place": "places",
        "delivery": "deliveries",
        "route": "routes",
    }.items():
        wanted = {entity.id: entity for entity in getattr(truth, collection)}
        actual = {entity.id: entity for entity in getattr(candidate, collection)}
        for entity_id in sorted(wanted.keys() - actual.keys()):
            uneditable.append(
                {"collection": collection, "id": entity_id, "reason": "Missing entity"}
            )
        for entity_id in sorted(actual.keys() - wanted.keys()):
            uneditable.append(
                {
                    "collection": collection,
                    "id": entity_id,
                    "reason": "Unexpected entity or different name",
                }
            )
        for entity_id in wanted.keys() & actual.keys():
            expected, current = wanted[entity_id], actual[entity_id]
            for field in expected.__class__.model_fields:
                if field not in expected.__class__.__mro__[1].model_fields:
                    continue
                before, after = getattr(current, field), getattr(expected, field)
                if before == after:
                    continue
                if field not in FIELDS[kind]:
                    uneditable.append(
                        {
                            "collection": collection,
                            "id": entity_id,
                            "field": field,
                            "actual": before,
                            "expected": after,
                            "reason": "No existing constrained correction",
                        }
                    )
                else:
                    corrections.append({"entity_id": entity_id, "field": field, "value": after})
                    setattr(current, field, after)
    if candidate.finish_time != truth.finish_time:
        corrections.append(
            {"entity_id": "finish-time", "field": "finish_time", "value": truth.finish_time}
        )
        candidate.finish_time = truth.finish_time
    for field, value in truth.problem_sizes.items():
        if candidate.problem_sizes.get(field) != value:
            corrections.append({"entity_id": "problem_sizes", "field": field, "value": value})
            candidate.problem_sizes[field] = value
    same_after_corrections = flatten(candidate) == flatten(truth)
    return {
        "correctable": not uneditable and same_after_corrections,
        "uneditable": uneditable,
        "scripted_corrections": corrections,
    }


def main():
    logger = logging.getLogger("server.ai")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "example-reading.json"
    if target.exists():
        raise SystemExit("A real reading is already recorded. Do not rerun a successful call.")
    values = dotenv_values(ROOT / ".env")
    attempts_path = OUT / "reading-attempts.json"
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
    wait_for_groq()
    try:
        result = read_plan(
            (ROOT / "fixtures/example-plan.txt").read_text(),
            {"groq": values.get("GROQ_API_KEY")},
            provider="groq",
        )
    except AIError as error:
        attempts.append(
            {"error": error.code, "reason": str(error), "attempts": getattr(error, "attempts", [])}
        )
        attempts_path.write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(str(error)) from error
    # Preserve the raw provider record exactly; comparisons are saved separately.
    target.write_text(
        json.dumps(result.raw.record(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    attempts.append(
        {
            "status": "passed",
            "provider": result.raw.provider,
            "timestamp": result.raw.timestamp,
            "attempts": result.attempts,
        }
    )
    attempts_path.write_text(json.dumps(attempts, indent=2) + "\n", encoding="utf-8")
    plan = plan_map_from_reading(
        result.reading,
        provider=result.raw.provider,
        model=result.raw.model,
        timestamp=result.raw.timestamp,
    )
    audit = {**compare(plan), **correction_audit(plan)}
    (OUT / "reading-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2), flush=True)
    if not audit["correctable"]:
        print(
            "STOP: the real reading cannot reach the truth map with the approved controls. "
            "No fixture was replaced or committed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
