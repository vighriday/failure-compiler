"""The recording command never repeats a successful per-case call or stores credentials."""

import json

from scripts import record_example_fixes as recording
from server.ai.adapter import FixResult
from server.ai.types import AIFixResponse, ProviderResponse


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
