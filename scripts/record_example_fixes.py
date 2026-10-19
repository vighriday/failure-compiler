"""Capture one winner response per broken case; retain raw output and checker verdicts locally."""

import argparse
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.ai.adapter import suggest_fixes  # noqa: E402
from server.ai.types import AIError, AIFixResponse  # noqa: E402
from server.checker.explain import route_reasons  # noqa: E402
from server.checker.runner import run_checker  # noqa: E402
from server.checker.scenarios import _instantiate_problems  # noqa: E402
from server.config import PRIMARY_PROVIDER  # noqa: E402
from server.fixes import score_fix  # noqa: E402
from server.reading import items_for_plan, plan_from_record, questions_for_plan  # noqa: E402
from server.review import REVIEWS, confirm_review, create_review, update_review  # noqa: E402


def reviewed_plan():
    text = (ROOT / "fixtures/example-reading.json").read_text(encoding="utf-8")
    record = json.loads(text)
    ledger = json.loads((ROOT / "fixtures/example-corrections.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(text.encode()).hexdigest() == ledger["reading_sha256"]
    plan = plan_from_record(record)
    items = items_for_plan(plan)
    state = create_review(plan, items, questions_for_plan(plan, items))
    for action in ledger["actions"]:
        update_review({"reading_id": state["reading_id"], **action})
    confirm_review({"reading_id": state["reading_id"]})
    return REVIEWS[state["reading_id"]].plan


def context_for(plan, result, results):
    problems = {problem["id"]: problem for problem in _instantiate_problems(plan.checker_data())}
    return {
        "confirmed_map": plan.checker_data().model_dump(mode="json"),
        "selected_case": result.model_dump(mode="json"),
        "selected_problems": [problems[pid] for pid in result.failures],
        "checker_reasons": route_reasons(plan.checker_data(), result),
        "each_alone": [
            row.model_dump(mode="json")
            for row in results
            if len(row.failures) == 1 and row.scenario_id in result.failures
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "devpost/screens/live-candidates/read-v3"
    )
    parser.add_argument(
        "--score-only", action="store_true", help="Reuse recorded responses; no AI calls"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry saved transient failures once; retain prior attempts and reuse successes",
    )
    args = parser.parse_args()
    if args.score_only and args.retry_failed:
        parser.error("score-only cannot request retries")
    logger = logging.getLogger("server.ai")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / "example-fixes.json"
    verdicts_path = args.output / "fix-verdicts.json"
    captures = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"cases": {}}
    verdicts = (
        json.loads(verdicts_path.read_text(encoding="utf-8"))
        if verdicts_path.exists()
        else {"cases": {}}
    )
    plan = reviewed_plan()
    if captures.get("map_fingerprint") not in {None, plan.fingerprint}:
        raise SystemExit("Saved suggestions belong to a different confirmed map.")
    captures["map_fingerprint"] = plan.fingerprint
    results = run_checker(plan.checker_data())
    assert len(results) == 100 and sum(row.state == "cross" for row in results) == 4
    values = {} if args.score_only else dotenv_values(ROOT / ".env")
    keys = {"groq": values.get("GROQ_API_KEY"), "gemini": values.get("GEMINI_API_KEY")}

    def save(path, data):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for result in results:
        if result.state != "cross":
            continue
        case_id = result.scenario_id
        captured = captures["cases"].get(case_id)
        retry = (
            args.retry_failed
            and captured is not None
            and "error" in captured
            and captured.get("attempts")
            and all(
                attempt.get("error") in {"server_error", "timeout", "rate_limited"}
                for attempt in captured["attempts"]
            )
        )
        if captured is None or retry:
            if args.score_only:
                raise SystemExit(f"No saved response for {case_id}; score-only makes no AI call.")
            previous = (
                [
                    *captured.get("previous_attempts", []),
                    {key: value for key, value in captured.items() if key != "previous_attempts"},
                ]
                if retry
                else []
            )
            context = context_for(plan, result, results)
            print(f"Capturing {case_id} from {PRIMARY_PROVIDER}", flush=True)
            try:
                response = suggest_fixes(context, keys, provider=PRIMARY_PROVIDER)
                captured = {
                    "raw": response.raw.record(),
                    "attempts": response.attempts,
                    "context": context,
                }
            except AIError as error:
                captured = {
                    "error": error.code,
                    "reason": str(error),
                    "attempts": getattr(error, "attempts", []),
                    "context": context,
                }
            captured["recorded_at"] = datetime.now(UTC).isoformat()
            if previous:
                captured["previous_attempts"] = previous
            captures["cases"][case_id] = captured
            save(target, captures)  # Save before scoring or making another call.
        if "error" in captured:
            print(f"STOP: saved provider error for {case_id}: {captured['reason']}", flush=True)
            continue  # Never silently retry a saved failed or successful call.
        if case_id not in verdicts["cases"]:
            response = AIFixResponse.model_validate_json(captured["raw"]["raw_text"])
            scored = [
                score_fix(plan, results, case_id, fix.model_dump(mode="json")).suggestion
                for fix in response.fixes
            ]
            verdicts["cases"][case_id] = {
                "explanation": response.explanation,
                "suggestions": [fix.model_dump(mode="json") for fix in scored],
            }
            save(verdicts_path, verdicts)
        print(
            json.dumps(
                {
                    "case": case_id,
                    "suggestions": [
                        {
                            key: fix.get(key)
                            for key in (
                                "id",
                                "description",
                                "gate_status",
                                "gate_reason",
                                "eligible",
                                "fixes_n",
                                "still_broken_n",
                                "new_crosses_n",
                                "rejection_reason",
                            )
                        }
                        for fix in verdicts["cases"][case_id]["suggestions"]
                    ],
                },
                indent=2,
            ),
            flush=True,
        )
    print(
        "STOP: raw suggestions and verdicts are local only. Review before committing them.",
        flush=True,
    )


if __name__ == "__main__":
    main()
