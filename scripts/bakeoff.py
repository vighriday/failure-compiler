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
from server.evaluation import (  # noqa: E402
    MEASUREMENT_VERSION,
    checker_fields,
    compare_reading,
    rank_providers,
)
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


def rescore_saved_report(saved: dict) -> dict:
    """Re-evaluate recorded responses offline, retaining scores from superseded contracts."""
    report = {**saved, "readings": [], "rescored_at": datetime.now(UTC).isoformat()}
    measurement = saved.get("measurement_version", "full-result-or-exact-name-legacy")
    if measurement != MEASUREMENT_VERSION:
        history = {
            "measurement_version": measurement,
            "ranking": saved.get("ranking"),
            "winner": saved.get("winner"),
            "mean_field_match_percent": saved.get("mean_field_match_percent"),
            "readings": [
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"raw", "attempts", "previous_attempts", "measurement_history"}
                }
                for row in saved["readings"]
            ],
        }
        report["measurement_history"] = [*saved.get("measurement_history", []), history]
    for row in saved["readings"]:
        if "raw" not in row:
            report["readings"].append(row)
            continue
        raw = row["raw"]
        reading = validate_ai_reading(raw["raw_text"])
        plan = plan_map_from_reading(
            reading, provider=raw["provider"], model=raw["model"], timestamp=raw["timestamp"]
        )
        current = {
            key: value
            for key, value in row.items()
            if key not in {"matches", "field_match_percent"}
        }
        report["readings"].append({**current, **compare(plan)})
    report.pop("mean_field_match_percent", None)
    report["measurement_version"] = MEASUREMENT_VERSION
    report["ranking"] = rank_providers(report["readings"])
    report["winner"] = report["ranking"][0]["provider"] if report["ranking"] else None
    return report


def main():
    logger = logging.getLogger("server.ai")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "devpost/bakeoff.json")
    parser.add_argument(
        "--rescore", type=Path, help="Score saved raw calls without calling a provider"
    )
    parser.add_argument(
        "--resume", type=Path, help="Retry saved provider errors, never successful readings"
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

    if args.resume:
        report = json.loads(args.resume.read_text(encoding="utf-8"))
        for index, row in enumerate(report["readings"]):
            if not row.get("error"):
                continue
            attempts = row.get("attempts", [])
            provider_error = any(
                attempt.get("error") in {"timeout", "rate_limited", "server_error"}
                for attempt in attempts
            )
            provider_error |= any(
                candidate.get("finish_reason") == "MAX_TOKENS"
                for attempt in attempts
                for candidate in attempt.get("raw", {}).get("response", {}).get("candidates", [])
            )
            if not provider_error:
                continue
            print(f"Retry provider error: {row['provider']} run {row['reading']}", flush=True)
            if row["provider"] == "groq":
                wait_for_groq()
            try:
                result = read_plan(text, keys, provider=row["provider"])
                plan = plan_map_from_reading(
                    result.reading,
                    provider=result.raw.provider,
                    model=result.raw.model,
                    timestamp=result.raw.timestamp,
                )
                replacement = {
                    "provider": row["provider"],
                    "reading": row["reading"],
                    "raw": result.raw.record(),
                    "attempts": result.attempts,
                    **compare(plan),
                }
                print(f"  {replacement['checker_matches']}/100 exact results", flush=True)
            except AIError as error:
                replacement = {
                    "provider": row["provider"],
                    "reading": row["reading"],
                    "error": error.code,
                    "reason": str(error),
                    "attempts": getattr(error, "attempts", []),
                }
            replacement["previous_attempts"] = [
                *row.get("previous_attempts", []),
                {k: v for k, v in row.items() if k != "previous_attempts"},
            ]
            report["readings"][index] = replacement
            save()
        report["ranking"] = rank_providers(report["readings"])
        report["winner"] = report["ranking"][0]["provider"] if report["ranking"] else None
        save()
        print(json.dumps(report["ranking"], indent=2))
        return

    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        report = rescore_saved_report(saved)
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
