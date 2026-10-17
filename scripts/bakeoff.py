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
from server.evaluation import checker_fields, compare_reading, rank_providers  # noqa: E402
from server.models import PlanMapData  # noqa: E402
from server.validation.gate import (  # noqa: E402
    plan_map_from_reading,
    validate_ai_reading,
)
from server.validation.models import PlanMap  # noqa: E402


def flatten(plan: PlanMap) -> dict:
    return checker_fields(plan)


def compare(plan: PlanMap, expected: PlanMap | None = None) -> dict:
    truth = PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    return compare_reading(plan, expected or PlanMap.from_truth_map(truth))


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
    parser.add_argument(
        "--rescore", type=Path, help="Score saved raw calls without calling a provider"
    )
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

    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        for row in saved["readings"]:
            if "raw" not in row:
                report["readings"].append(row)
                continue
            raw = row["raw"]
            reading = validate_ai_reading(raw["raw_text"])
            plan = plan_map_from_reading(
                reading, provider=raw["provider"], model=raw["model"], timestamp=raw["timestamp"]
            )
            report["readings"].append(
                {
                    "provider": row["provider"],
                    "reading": row["reading"],
                    "raw": raw,
                    "attempts": row["attempts"],
                    **compare(plan),
                }
            )
        report["ranking"] = rank_providers(report["readings"])
        report["winner"] = report["ranking"][0]["provider"] if report["ranking"] else None
        save()
        print(json.dumps(report["ranking"], indent=2))
        return

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
                    f"  {comparison['aligned_field_match_percent']}% fields; "
                    f"{comparison['checker_matches']}/{comparison['checker_total']} exact results; "
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
    ranking = rank_providers(report["readings"])
    report["ranking"] = ranking
    report["winner"] = ranking[0]["provider"] if ranking else None
    save()
    print(
        json.dumps({"ranking": ranking, "winner": report["winner"], "saved": str(args.output)}),
        flush=True,
    )


if __name__ == "__main__":
    main()
