"""Inspect SDK call arguments offline, including retries, token caps and structured output."""

from types import SimpleNamespace

import pytest

from server.ai import gemini_provider, groq_provider
from server.ai.types import AIError


def test_groq_uses_strict_schema_low_reasoning_and_no_sdk_retry(monkeypatch, caplog):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=150, total_tokens=250),
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            model_dump=lambda **kwargs: {"provider": "groq", "body": "unchanged"},
        )

    def client(**kwargs):
        assert kwargs == {"api_key": "private-key", "max_retries": 0, "timeout": 45}
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr("groq.Groq", client)
    monkeypatch.setattr(groq_provider, "_NEXT_CALL", 0)
    with caplog.at_level("INFO", logger="server.ai.groq_provider"):
        result = groq_provider.generate(
            "system", "plan", {"type": "object"}, "private-key", "read-v1"
        )
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    assert calls[0]["reasoning_effort"] == "low"
    assert calls[0]["max_completion_tokens"] <= 4096
    assert result.raw_text == '{"ok":true}'
    assert "total=250" in caplog.text and "private-key" not in caplog.text
    with pytest.raises(AIError, match="Rate limited"):
        groq_provider.generate("system", "plan", {}, "private-key", "read-v1")
    assert len(calls) == 1


def test_gemini_uses_installed_schema_field_and_exactly_one_sdk_attempt(monkeypatch, caplog):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "private-key"
            assert kwargs["http_options"].retry_options.attempts == 1
            self.models = self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text='{"ok":true}',
                usage_metadata=SimpleNamespace(
                    prompt_token_count=100,
                    candidates_token_count=150,
                    thoughts_token_count=20,
                    total_token_count=270,
                ),
                model_dump=lambda **kwargs: {"body": "unchanged"},
            )

    monkeypatch.setattr("google.genai.Client", Client)
    with caplog.at_level("INFO", logger="server.ai.gemini_provider"):
        result = gemini_provider.generate(
            "system", "plan", {"type": "object"}, "private-key", "read-v1"
        )
    config = calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == {"type": "object"}
    assert config.response_schema is None
    assert result.output_tokens == 170
    assert "total=270" in caplog.text and "private-key" not in caplog.text
