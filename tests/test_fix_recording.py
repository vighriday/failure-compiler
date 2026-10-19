"""The recording command never repeats a successful per-case call or stores credentials."""

import json

from scripts import record_example_fixes as recording
from server.ai.adapter import FixResult
from server.ai.types import AIError, AIFixResponse, ProviderResponse


def test_each_broken_case_is_captured_once_and_can_be_rescored_without_ai(
    monkeypatch, tmp_path, capsys
):
    calls = []
    payload = json.dumps(
        {
            "explanation": "Recorded test response",
            "fixes": [
                {
                    "id": "recorded-fix",
                    "description": "Recorded operation",
                    "operations": [
                        {
                            "op": "add_loader",
                            "target_id": "route-c",
                            "field": "loader_ids",
                            "value": "person-sam",
                        }
                    ],
                }
            ],
        }
    )

    def fake(context, keys, *, provider):
        calls.append(context["selected_case"]["scenario_id"])
        assert "ai_meta" not in context["confirmed_map"]
        raw = ProviderResponse(
            provider, "offline-test", "fix-v1", "2026-10-17", payload, 10, 10, 20, {}
        )
        return FixResult(raw, AIFixResponse.model_validate_json(payload), [{"status": "passed"}])

    monkeypatch.setattr(recording, "suggest_fixes", fake)
    monkeypatch.setattr(
        recording, "dotenv_values", lambda _: {"GEMINI_API_KEY": "private-test-key"}
    )
    monkeypatch.setattr("sys.argv", ["record_example_fixes.py", "--output", str(tmp_path)])
    recording.main()
    recording.main()
    monkeypatch.setattr(
        "sys.argv", ["record_example_fixes.py", "--output", str(tmp_path), "--score-only"]
    )
    recording.main()
    assert len(calls) == len(set(calls)) == 4
    captured = (tmp_path / "example-fixes.json").read_text(encoding="utf-8")
    assert "private-test-key" not in captured + capsys.readouterr().out
    assert all(
        case["raw"]["raw_text"] == payload for case in json.loads(captured)["cases"].values()
    )
    verdicts = json.loads((tmp_path / "fix-verdicts.json").read_text(encoding="utf-8"))
    assert len(verdicts["cases"]) == 4
    assert all(
        len(case["suggestions"][0]["scenario_results"]) == 100
        for case in verdicts["cases"].values()
    )


def test_explicit_retry_retains_failure_and_never_repeats_success(monkeypatch, tmp_path):
    calls = []
    payload = json.dumps({"explanation": "Unedited saved response", "fixes": []})

    def fake(context, keys, *, provider):
        case = context["selected_case"]["scenario_id"]
        calls.append(case)
        if len(calls) == 1:
            error = AIError("providers_failed", "Gemini returned HTTP 503")
            error.attempts = [{"provider": provider, "error": "server_error"}]
            raise error
        raw = ProviderResponse(
            provider, "offline-test", "fix-v1", "2026-10-19", payload, 10, 10, 20, {}
        )
        return FixResult(raw, AIFixResponse.model_validate_json(payload), [{"status": "passed"}])

    monkeypatch.setattr(recording, "suggest_fixes", fake)
    monkeypatch.setattr(recording, "dotenv_values", lambda _: {})
    argv = ["record_example_fixes.py", "--output", str(tmp_path)]
    monkeypatch.setattr("sys.argv", argv)
    recording.main()
    recording.main()
    assert len(calls) == 4  # A saved failure is never retried by default.
    monkeypatch.setattr("sys.argv", [*argv, "--retry-failed", "--minimum-interval", "600"])
    recording.main()
    assert len(calls) == 4  # Enforce the user's minimum retry interval.
    monkeypatch.setattr("sys.argv", [*argv, "--retry-failed", "--max-provider-attempts", "1"])
    recording.main()
    assert len(calls) == 4  # A per-provider cap cannot be exceeded.
    monkeypatch.setattr("sys.argv", [*argv, "--retry-failed", "--provider", "groq"])
    recording.main()
    recording.main()
    assert len(calls) == 5 and calls[0] == calls[-1]
    cases = json.loads((tmp_path / "example-fixes.json").read_text(encoding="utf-8"))["cases"]
    assert cases[calls[0]]["raw"]["raw_text"] == payload
    assert cases[calls[0]]["raw"]["provider"] == "groq"
    assert cases[calls[0]]["previous_attempts"][0]["error"] == "providers_failed"
    assert len(cases[calls[0]]["previous_attempts"]) == 1
