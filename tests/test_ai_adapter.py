"""Offline provider contracts: strict schemas, bounded fallback and raw record preservation."""

import json

import pytest

from server.ai import adapter
from server.ai.prompts import READ_PROMPT_VERSION
from server.ai.types import AIError, AIFixResponse, ProviderResponse, compact_schema
from server.validation.models import AIPlanReading
from tests.validation_helpers import ROOT, ai_reading_payload


@pytest.mark.parametrize("model", [AIPlanReading, AIFixResponse])
def test_every_schema_object_is_closed_and_requires_all_fields(model):
    def visit(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
                assert set(value["required"]) == set(value["properties"])
            assert "default" not in value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(compact_schema(model.model_json_schema()))
    if model is AIPlanReading:
        assert {
            row["type"]
            for row in model.model_json_schema()["properties"]["not_distribution_reason"]["anyOf"]
        } == {"string", "null"}


def fake_response(payload=None, provider="groq"):
    raw = payload if isinstance(payload, str) else json.dumps(payload or ai_reading_payload())
    return ProviderResponse(
        provider,
        "fake-model",
        READ_PROMPT_VERSION,
        "2026-10-17T00:00:00Z",
        raw,
        1200,
        1800,
        3000,
        {"raw": raw},
    )


def reading_response(provider="groq"):
    payload = ai_reading_payload()
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in payload[collection]:
            entity["source_line"] = "L3"
    return fake_response(payload, provider)


@pytest.mark.parametrize("failure", ["rate_limited", "timeout", "server_error", "gate"])
def test_one_attempt_each_and_fallback_on_provider_or_gate_failure(monkeypatch, failure):
    called = []

    def primary(*args):
        called.append("groq")
        if failure == "gate":
            return fake_response('{"broken":true}')
        raise AIError(failure, "Controlled provider failure", provider="groq")

    def fallback(*args):
        called.append("gemini")
        return reading_response("gemini")

    monkeypatch.setattr(adapter.groq_provider, "generate", primary)
    monkeypatch.setattr(adapter.gemini_provider, "generate", fallback)
    result = adapter.read_plan(
        (ROOT / "fixtures/example-plan.txt").read_text(),
        {"groq": "private-primary", "gemini": "private-fallback"},
    )
    assert called == ["groq", "gemini"]
    assert result.raw.provider == "gemini"
    assert "private-" not in json.dumps(result.raw.record())
    assert len(result.attempts) == 2


def test_success_preserves_exact_raw_response_and_only_normalises_separate_copy(monkeypatch):
    response = reading_response()
    monkeypatch.setattr(adapter.groq_provider, "generate", lambda *args: response)
    result = adapter.read_plan((ROOT / "fixtures/example-plan.txt").read_text(), {"groq": "secret"})
    assert result.raw is response
    assert result.raw.raw_text == response.response["raw"]
    assert result.reading.deliveries[0].id == "delivery-supply-truck"
    assert '"id": "delivery-supplies"' in result.raw.raw_text


def test_invalid_key_is_clear_and_is_not_retried(monkeypatch):
    calls = []

    def primary(*args):
        calls.append("groq")
        raise AIError("invalid_key", "Check your key.", status=401)

    monkeypatch.setattr(adapter.groq_provider, "generate", primary)
    with pytest.raises(AIError, match="Check your key"):
        adapter.read_plan("A distribution plan", {"groq": "secret", "gemini": "secret2"})
    assert calls == ["groq"]


def test_both_failed_is_bounded_and_format_reason_survives(monkeypatch):
    calls = []

    def invalid(*args):
        calls.append(1)
        return fake_response('{"extra": true}')

    monkeypatch.setattr(adapter.groq_provider, "generate", invalid)
    monkeypatch.setattr(adapter.gemini_provider, "generate", invalid)
    with pytest.raises(AIError, match="Missing required field 'people'") as error:
        adapter.read_plan("A distribution plan", {"groq": "secret", "gemini": "secret2"})
    assert len(calls) == 2
    assert error.value.code == "format_check_failed"
    assert all(row["raw"]["raw_text"] == '{"extra": true}' for row in error.value.attempts)


def test_non_distribution_reason_is_reported_without_fallback(monkeypatch):
    payload = ai_reading_payload()
    payload.update(is_distribution_plan=False, not_distribution_reason="This is a poem.")
    monkeypatch.setattr(adapter.groq_provider, "generate", lambda *args: fake_response(payload))
    with pytest.raises(AIError, match="This is a poem") as error:
        adapter.read_plan("A poem", {"groq": "secret"})
    assert error.value.code == "not_distribution"
