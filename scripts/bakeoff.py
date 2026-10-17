"""Record three unedited readings per provider and compare checker fields with the truth map."""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.ai.adapter import read_plan  # noqa: E402
from server.ai.groq_provider import cooldown_seconds  # noqa: E402
from server.ai.types import AIError  # noqa: E402
from server.models import PlanMapData  # noqa: E402
from server.validation.gate import normalise_plan_map_ids, plan_map_from_reading  # noqa: E402
from server.validation.models import PlanMap  # noqa: E402


def flatten(plan: PlanMap) -> dict:
    data = normalise_plan_map_ids(plan).checker_data()
    result = {"finish_time": data.finish_time}
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in getattr(data, collection):
            for field, value in entity.model_dump().items():
                if field != "id":
                    result[f"{collection}.{entity.id}.{field}"] = value
    result.update({f"problem_sizes.{key}": value for key, value in data.problem_sizes.items()})
    return result


def compare(plan: PlanMap, expected: PlanMap | None = None) -> dict:
    truth = PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    wanted, actual = flatten(expected or PlanMap.from_truth_map(truth)), flatten(plan)
    mismatches = [
        {
            "field": key,
            "expected": wanted.get(key, "<not in truth>"),
            "actual": actual.get(key, "<missing>"),
        }
        for key in sorted(wanted.keys() | actual.keys())
        if wanted.get(key) != actual.get(key)
    ]
    matches = sum(key in actual and actual[key] == value for key, value in wanted.items())
    return {
        "matches": matches,
        "truth_fields": len(wanted),
        "field_match_percent": round(100 * matches / len(wanted), 2),
        "mismatches": mismatches,
    }


def wait_for_groq() -> None:
    remaining = cooldown_seconds()
    if remaining:
        print(f"Groq budget cooldown: {remaining:.0f}s", flush=True)
    while cooldown_seconds():
        time.sleep(min(5, cooldown_seconds()))


def main():
    logger = logging.getLogger("server.ai")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "devpost/bakeoff.json")
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    keys = {"groq": values.get("GROQ_API_KEY"), "gemini": values.get("GEMINI_API_KEY")}
    text = (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8")
    report = {"date": datetime.now(UTC).isoformat(), "readings": [], "winner": None}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    for provider in ("groq", "gemini"):
        for index in range(1, 4):
            if provider == "groq":
                wait_for_groq()
            print(f"Reading {provider} {index}/3", flush=True)
            try:
                result = read_plan(text, keys, provider=provider)
                plan = plan_map_from_reading(
                    result.reading,
                    provider=result.raw.provider,
                    model=result.raw.model,
                    timestamp=result.raw.timestamp,
                )
                comparison = compare(plan)
                row = {
                    "provider": provider,
                    "reading": index,
                    "raw": result.raw.record(),
                    "attempts": result.attempts,
                    **comparison,
                }
                print(
                    f"  {comparison['field_match_percent']}% fields; "
                    f"{result.raw.total_tokens} tokens",
                    flush=True,
                )
            except AIError as error:
                row = {
                    "provider": provider,
                    "reading": index,
                    "error": error.code,
                    "reason": str(error),
                    "attempts": getattr(error, "attempts", []),
                }
                print(f"  {error.code}: {error}", flush=True)
            report["readings"].append(row)
            save()
    scores = {
        provider: [
            row["field_match_percent"]
            for row in report["readings"]
            if row["provider"] == provider and "field_match_percent" in row
        ]
        for provider in ("groq", "gemini")
    }
    means = {
        provider: round(sum(values) / len(values), 2)
        for provider, values in scores.items()
        if len(values) == 3
    }
    report["mean_field_match_percent"] = means
    report["winner"] = max(means, key=means.get) if means else None
    save()
    print(
        json.dumps({"means": means, "winner": report["winner"], "saved": str(args.output)}),
        flush=True,
    )


if __name__ == "__main__":
    main()
