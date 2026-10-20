"""Explicitly opt-in SDK smoke test; normal offline tests never make AI calls."""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_live_provider_only_when_explicitly_enabled(provider):
    if os.environ.get("RUN_LIVE_AI_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_AI_TESTS=1 explicitly to allow real AI requests.")
    root = Path(__file__).resolve().parents[1]
    name = f"{provider.upper()}_API_KEY"
    key = os.environ.get(name) or dotenv_values(root / ".env").get(name)
    if not key:
        pytest.skip(f"{name} is not configured.")
    from server.ai.adapter import read_plan

    result = read_plan(
        (root / "fixtures/example-plan.txt").read_text(encoding="utf-8"),
        {provider: key},
        provider=provider,
    )
    assert result.reading.is_distribution_plan
    assert result.raw.provider == provider
