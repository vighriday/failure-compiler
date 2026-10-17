"""Make the one authorised primary reading and stop if the existing controls cannot reach truth."""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.bakeoff import wait_for_groq  # noqa: E402
from server.ai.adapter import read_plan  # noqa: E402
from server.ai.prompts import READ_PROMPT_VERSION  # noqa: E402
from server.ai.types import AIError  # noqa: E402
from server.config import PRIMARY_PROVIDER  # noqa: E402
from server.models import PlanMapData  # noqa: E402
from server.reading_review import correction_audit as audit_review  # noqa: E402
from server.validation.gate import plan_map_from_reading, validate_ai_reading  # noqa: E402
from server.validation.models import PlanMap  # noqa: E402

OUT = ROOT / "devpost/screens/live-candidates"


def correction_audit(plan: PlanMap, *, place_aliases: dict | None = None) -> dict:
    truth = PlanMap.from_truth_map(
        PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    )
    return audit_review(plan, truth, place_aliases=place_aliases)


def main():
    logger = logging.getLogger("server.ai")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT / READ_PROMPT_VERSION)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--place-alias", action="append", default=[], metavar="SOURCE=TARGET")
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    target = output / "example-reading.json"
    aliases = dict(value.split("=", 1) for value in args.place_alias)
    audit_path = args.audit_output or output / "reading-audit.json"
    if args.audit_only:
        record = json.loads(target.read_text(encoding="utf-8"))
        plan = plan_map_from_reading(
            validate_ai_reading(record["raw_text"]),
            provider=record["provider"],
            model=record["model"],
            timestamp=record["timestamp"],
        )
        audit = correction_audit(plan, place_aliases=aliases)
        audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {k: v for k, v in audit.items() if k not in {"corrected_plan", "aligned_inputs"}},
                indent=2,
            )
        )
        return
    if target.exists():
        raise SystemExit("A real reading is already recorded. Do not rerun a successful call.")
    values = dotenv_values(ROOT / ".env")
    attempts_path = output / "reading-attempts.json"
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
    if PRIMARY_PROVIDER == "groq":
        wait_for_groq()
    try:
        result = read_plan(
            (ROOT / "fixtures/example-plan.txt").read_text(),
            {"groq": values.get("GROQ_API_KEY"), "gemini": values.get("GEMINI_API_KEY")},
            provider=PRIMARY_PROVIDER,
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
    audit = correction_audit(plan, place_aliases=aliases)
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "correctable": audit["correctable"],
                "before": audit["before"],
                "after": audit["after"],
                "actual_scenario_count": audit["actual_scenario_count"],
                "not_fixable": audit["not_fixable"],
                "corrections": audit["scripted_corrections"],
            },
            indent=2,
        ),
        flush=True,
    )
    if not audit["correctable"]:
        print(
            "STOP: checker-input equivalence is incomplete with the approved controls. "
            "Reference-result matches do not discard extra entities or scenarios. "
            "No fixture was replaced or committed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
