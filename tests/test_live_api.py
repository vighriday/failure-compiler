"""Offline HTTP flow: recorded reading, explicitly synthetic fixes and provider failures."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import credentials
from server.ai import adapter
from server.ai.types import AIError, ProviderResponse
from server.fixes import DETAILS, FIX_LOCKS, RAW_FIXES, RETRIED, SCORED
from server.main import app
from server.review import REVIEWS
from server.session import OWNED_SESSIONS, SESSIONS

ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8")
JOEL = "volunteer_absent__person-joel"


def raw_reading(provider="gemini"):
    record = json.loads((ROOT / "fixtures/example-reading.json").read_text(encoding="utf-8"))
    record["provider"] = provider
    return ProviderResponse(**record)


def synthetic_fixes(provider="gemini", payload=None):
    text = payload or (ROOT / "tests/fixtures/synthetic-fix-response.json").read_text("utf-8")
    return ProviderResponse(provider, "synthetic-offline-model", "fix-v1", "", text, 1, 1, 2, {})


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for store in (
        credentials.CLIENTS,
        OWNED_SESSIONS,
        SESSIONS,
        REVIEWS,
        SCORED,
        DETAILS,
        RAW_FIXES,
        FIX_LOCKS,
        RETRIED,
    ):
        store.clear()
    monkeypatch.setattr(credentials, "dotenv_values", lambda _: {})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(adapter, "PRIMARY_PROVIDER", "gemini")
    monkeypatch.setattr(adapter, "FALLBACK_PROVIDER", "groq")


def fake_providers(monkeypatch, *, fail_primary=None, fixes=None):
    calls = []

    def generate(provider):
        def run(system, user, schema, key, version):
            calls.append((provider, version, key))
            if provider == "gemini" and fail_primary:
                raise AIError(fail_primary, "Controlled provider failure", provider=provider)
            return (
                raw_reading(provider)
                if version.startswith("read-")
                else (fixes or synthetic_fixes(provider))
            )

        return run

    monkeypatch.setattr(adapter.gemini_provider, "generate", generate("gemini"))
    monkeypatch.setattr(adapter.groq_provider, "generate", generate("groq"))
    return calls


def read_and_confirm(
    client, *, api_key="typed-private-gemini", key_provider="gemini", example=False
):
    response = client.post(
        "/api/read-plan",
        json={
            "text": PLAN,
            "example": example,
            "api_key": api_key,
            "key_provider": key_provider,
        },
    )
    assert response.status_code == 200, response.text
    reading = response.json()
    rid = reading["reading_id"]
    # The server still owns the entire gate; omitting browser lists cannot confirm.
    assert client.post("/api/confirm-map", json={"reading_id": rid}).status_code == 422
    ledger = json.loads((ROOT / "fixtures/example-corrections.json").read_text("utf-8"))
    for action in ledger["actions"]:
        response = client.post("/api/update-map", json={"reading_id": rid, **action})
        assert response.status_code == 200, response.text
    response = client.post("/api/confirm-map", json={"reading_id": rid})
    assert response.status_code == 200, response.text
    return reading, response.json()


def run(client, fingerprint):
    response = client.get(f"/api/run-tests?map={fingerprint}&reduced_motion=true")
    assert response.status_code == 200, response.text
    events = [json.loads(block[6:]) for block in response.text.split("\n\n") if block]
    assert events[-1]["count"]["total"] == 100
    assert events[-1]["count"]["hidden_pairs"] == 3
    return response, events


def test_live_http_flow_keys_metadata_gate_score_apply_and_cache(monkeypatch, caplog):
    calls = fake_providers(monkeypatch)
    client = TestClient(app)
    cookie_header = client.get("/api/health").headers["set-cookie"]
    assert "HttpOnly" in cookie_header and "SameSite=lax" in cookie_header
    reading, confirmed = read_and_confirm(client)
    assert reading["source"] == "live" and not reading["placeholder"]
    assert reading["read_by"].startswith("gemini / ")
    cookie = client.cookies[credentials.COOKIE_NAME]
    assert credentials.CLIENTS[cookie].keys == {"gemini": "typed-private-gemini"}
    fp = confirmed["fingerprint"]
    stream, events = run(client, fp)
    assert events[0]["read_by"] == reading["read_by"]
    body = {"fingerprint": fp, "scenario_id": JOEL}
    detail = client.post("/api/suggest-fixes", json=body)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["source"] == "live" and payload["suggested_by"].startswith("gemini / ")
    good, bad = payload["suggestions"]
    assert good["eligible"] and len(good["scenario_results"]) == 100
    assert not bad["eligible"] and bad["gate_status"] == "couldnt_apply"
    assert "person-dave" in bad["gate_reason"]
    assert client.post("/api/suggest-fixes", json=body).json() == payload
    assert [version for _, version, _ in calls] == ["read-v3", "fix-v1"]
    accepted = client.post("/api/apply-fix", json={**body, "fix_id": good["id"]})
    assert accepted.status_code == 200, accepted.text
    new_fp = accepted.json()["fingerprint"]
    assert (cookie, new_fp) in OWNED_SESSIONS
    # Restoring the accepted map is confined to the same reviewed reading.
    restored = client.post(
        "/api/update-map",
        json={
            "reading_id": reading["reading_id"],
            "action": "restore_fixed",
            "fingerprint": new_fp,
        },
    )
    assert restored.status_code == 200
    assert "typed-private-gemini" not in (
        json.dumps(reading)
        + stream.text
        + detail.text
        + accepted.text
        + restored.text
        + caplog.text
    )
    status = client.get("/api/ai-status")
    assert status.json()["key_available"] == {"gemini": True, "groq": False}
    assert "typed-private-gemini" not in status.text


def test_saved_then_live_identical_map_gets_live_suggestions(monkeypatch):
    calls = fake_providers(monkeypatch)
    client = TestClient(app)
    _, saved = read_and_confirm(client, example=True)
    fp = saved["fingerprint"]
    run(client, fp)
    body = {"fingerprint": fp, "scenario_id": JOEL}
    saved_detail = client.post("/api/suggest-fixes", json=body).json()
    assert saved_detail["source"] == "saved" and not saved_detail["placeholder"]
    assert not calls
    _, live = read_and_confirm(client)
    assert live["fingerprint"] == fp
    response = client.post("/api/suggest-fixes", json=body)
    assert response.status_code == 200 and response.json()["source"] == "live"
    assert [version for _, version, _ in calls] == ["read-v3", "fix-v1"]


def test_suggestions_503_falls_back_to_groq(monkeypatch):
    monkeypatch.setattr(credentials, "dotenv_values", lambda _: {"GROQ_API_KEY": "env-groq"})
    calls = fake_providers(monkeypatch, fail_primary="server_error")
    client = TestClient(app)
    _, confirmed = read_and_confirm(client)
    fp = confirmed["fingerprint"]
    run(client, fp)
    response = client.post("/api/suggest-fixes", json={"fingerprint": fp, "scenario_id": JOEL})
    assert response.status_code == 200
    assert response.json()["fallback_used"]
    assert response.json()["suggested_by"].startswith("groq / ")
    assert [name for name, _, _ in calls] == ["gemini", "groq", "gemini", "groq"]


def test_env_keys_and_503_fallback_are_reported(monkeypatch):
    monkeypatch.setattr(
        credentials,
        "dotenv_values",
        lambda _: {
            "GEMINI_API_KEY": "env-private-gemini",
            "GROQ_API_KEY": "env-private-groq",
        },
    )
    calls = fake_providers(monkeypatch, fail_primary="server_error")
    response = TestClient(app).post("/api/read-plan", json={"text": PLAN, "example": False})
    assert response.status_code == 200
    result = response.json()
    assert result["fallback_used"] and result["read_by"].startswith("groq / ")
    assert result["attempts"] == [
        {"provider": "gemini", "error": "server_error"},
        {"provider": "groq", "status": "passed"},
    ]
    assert [name for name, _, _ in calls] == ["gemini", "groq"]
    assert "env-private" not in response.text


def test_typed_groq_is_first_and_success_does_not_call_gemini(monkeypatch):
    calls = fake_providers(monkeypatch)
    client = TestClient(app)
    reading, _ = read_and_confirm(client, api_key="typed-groq", key_provider="groq")
    assert reading["read_by"].startswith("groq / ")
    assert [name for name, _, _ in calls] == ["groq"]
    assert client.get("/api/ai-status").json()["selected_provider"] == "groq"


def test_browsers_cannot_read_update_run_or_apply_each_others_maps(monkeypatch):
    fake_providers(monkeypatch)
    first, second = TestClient(app), TestClient(app)
    reading, confirmed = read_and_confirm(first)
    fp = confirmed["fingerprint"]
    assert second.get(f"/api/run-tests?map={fp}").status_code == 404
    for endpoint in ("validate-map", "confirm-map", "update-map"):
        response = second.post(
            f"/api/{endpoint}",
            json={
                "reading_id": reading["reading_id"],
                "action": "confirm_all",
            },
        )
        assert response.status_code == 404
    response = second.post("/api/suggest-fixes", json={"fingerprint": fp, "scenario_id": JOEL})
    assert response.status_code == 409
    # Identical fingerprints still retain distinct typed keys and map instances.
    _, other = read_and_confirm(second, api_key="different-private-key")
    assert fp == other["fingerprint"]
    one, two = first.cookies[credentials.COOKIE_NAME], second.cookies[credentials.COOKIE_NAME]
    assert OWNED_SESSIONS[one, fp] is not OWNED_SESSIONS[two, fp]
    assert credentials.CLIENTS[one].keys != credentials.CLIENTS[two].keys


@pytest.mark.parametrize(
    "code,status",
    [("invalid_key", 401), ("server_error", 502), ("timeout", 502), ("rate_limited", 502)],
)
def test_provider_failures_are_bounded_retryable_and_never_echo_keys(monkeypatch, code, status):
    calls = []

    def fail(*args):
        calls.append(1)
        raise AIError(code, "Controlled typed-secret failure", status=status)

    monkeypatch.setattr(adapter.gemini_provider, "generate", fail)
    monkeypatch.setattr(adapter.groq_provider, "generate", fail)
    monkeypatch.setattr(credentials, "dotenv_values", lambda _: {"GROQ_API_KEY": "env-groq"})
    client = TestClient(app)
    body = {"text": PLAN, "api_key": "typed-secret", "key_provider": "gemini"}
    response = client.post("/api/read-plan", json=body)
    assert response.status_code == status
    assert "typed-secret" not in response.text
    assert response.json()["error_code"] == (
        "invalid_key" if code == "invalid_key" else "providers_failed"
    )
    assert len(calls) == (1 if code == "invalid_key" else 2)
    monkeypatch.setattr(adapter.gemini_provider, "generate", lambda *args: raw_reading())
    assert client.post("/api/read-plan", json={"text": PLAN}).status_code == 200


def test_format_non_distribution_missing_key_and_input_errors(monkeypatch):
    client = TestClient(app)
    assert client.post("/api/read-plan", json={"text": PLAN}).json()["error_code"] == "missing_key"
    for body in (
        {"example": "false"},
        {"text": 42},
        {"text": "x" * 4001},
        {"unknown": "secret"},
        {"text": PLAN, "key_provider": []},
    ):
        assert client.post("/api/read-plan", json=body).status_code == 422
    malformed = client.post("/api/read-plan", json=[{"api_key": "never-echo-this"}])
    assert malformed.status_code == 422 and "never-echo-this" not in malformed.text
    monkeypatch.setattr(
        adapter.gemini_provider, "generate", lambda *args: synthetic_fixes(payload='{"extra":true}')
    )
    response = client.post("/api/read-plan", json={"text": PLAN, "api_key": "private"})
    assert response.json()["error_code"] == "format_check_failed"
    assert "Missing required field 'people'" in response.json()["detail"]
    record = raw_reading()
    parsed = json.loads(record.raw_text)
    parsed.update(is_distribution_plan=False, not_distribution_reason="This is a shopping list.")
    record.raw_text = json.dumps(parsed)
    monkeypatch.setattr(adapter.gemini_provider, "generate", lambda *args: record)
    response = client.post("/api/read-plan", json={"text": PLAN})
    assert response.status_code == 422 and response.json()["error_code"] == "not_distribution"
    assert "shopping list" in response.text


def test_suggestion_failures_keep_checker_facts_and_retry_without_losing_key(monkeypatch):
    fake_providers(monkeypatch)
    client = TestClient(app)
    _, confirmed = read_and_confirm(client)
    fp = confirmed["fingerprint"]
    run(client, fp)

    def fail(*args):
        raise AIError("server_error", "Controlled 503", provider="gemini")

    monkeypatch.setattr(adapter.gemini_provider, "generate", fail)
    body = {"fingerprint": fp, "scenario_id": JOEL}
    failure = client.post("/api/suggest-fixes", json=body)
    assert failure.status_code == 502
    assert failure.json()["error_code"] == "providers_failed"
    assert set(failure.json()["case_detail"]["route_reasons"].values()) == {
        "Nobody can open the loading area."
    }
    monkeypatch.setattr(adapter.gemini_provider, "generate", lambda *args: synthetic_fixes())
    assert client.post("/api/suggest-fixes", json=body).status_code == 200


def test_none_worked_can_request_one_extra_successful_response(monkeypatch):
    payload = json.dumps({"explanation": "Synthetic empty response.", "fixes": []})
    calls = fake_providers(monkeypatch, fixes=synthetic_fixes(payload=payload))
    client = TestClient(app)
    _, confirmed = read_and_confirm(client)
    fp = confirmed["fingerprint"]
    run(client, fp)
    body = {"fingerprint": fp, "scenario_id": JOEL}
    assert client.post("/api/suggest-fixes", json=body).json()["can_retry"]
    assert not client.post("/api/suggest-fixes", json={**body, "retry": True}).json()["can_retry"]
    assert client.post("/api/suggest-fixes", json={**body, "retry": True}).status_code == 409
    assert len(calls) == 3  # One read, first suggestions, one explicit extra.


@pytest.mark.parametrize(
    "scenario_id",
    [
        JOEL,
        "volunteer_absent__person-ravi+supply_delivery_late__delivery-supply-truck",
        "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van",
        "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van",
    ],
)
def test_optional_recorded_fix_replays_through_live_http(monkeypatch, scenario_id):
    path = os.environ.get("RECORDED_AI_FIXES_PATH", str(ROOT / "fixtures/example-fixes.json"))
    captures = json.loads(Path(path).read_text(encoding="utf-8"))
    recorded = captures["cases"][scenario_id]["raw"]
    fake_providers(monkeypatch)
    monkeypatch.setattr(credentials, "dotenv_values", lambda _: {"GROQ_API_KEY": "offline-groq"})

    def recorded_provider(provider):
        def generate(system, user, schema, key, version):
            if version.startswith("read-"):
                return raw_reading()
            if provider != recorded["provider"]:
                raise AIError("server_error", "Recorded primary outage (503).", provider=provider)
            return ProviderResponse(**recorded)

        return generate

    monkeypatch.setattr(adapter.gemini_provider, "generate", recorded_provider("gemini"))
    monkeypatch.setattr(adapter.groq_provider, "generate", recorded_provider("groq"))
    client = TestClient(app)
    _, confirmed = read_and_confirm(client)
    fp = confirmed["fingerprint"]
    run(client, fp)
    response = client.post(
        "/api/suggest-fixes", json={"fingerprint": fp, "scenario_id": scenario_id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["explanation"] == json.loads(recorded["raw_text"])["explanation"]
    assert len(response.json()["suggestions"]) == len(json.loads(recorded["raw_text"])["fixes"])
    assert response.json()["suggested_by"] == f"{recorded['provider']} / {recorded['model']}"
    assert response.json()["fallback_used"] == (recorded["provider"] != "gemini")
    for fix in response.json()["suggestions"]:
        if fix["new_crosses"] and "+" not in fix["new_crosses"][0]:
            assert "new single weak spot" in fix["rejection_reason"]
    eligible = next((fix for fix in response.json()["suggestions"] if fix["eligible"]), None)
    if eligible:
        applied = client.post(
            "/api/apply-fix",
            json={
                "fingerprint": fp,
                "scenario_id": scenario_id,
                "fix_id": eligible["id"],
            },
        )
        assert applied.status_code == 200, applied.text
        after = client.get(
            "/api/run-tests",
            params={
                "map": applied.json()["fingerprint"],
                "reduced_motion": "true",
            },
        )
        assert after.status_code == 200
        events = [json.loads(block[6:]) for block in after.text.split("\n\n") if block]
        assert events[-1]["count"]["total"] == 100
        selected = next(
            event["result"]
            for event in events
            if event["type"] == "result" and event["result"]["scenario_id"] == scenario_id
        )
        assert selected["state"] == "tick"
