"""SDK transport exceptions reach the same bounded fallback as provider 503s."""

import httpx
import pytest

from server.ai import gemini_provider
from server.ai.types import AIError


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_gemini_httpx_transport_failure_is_a_retryable_ai_error(monkeypatch, error_type):
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            raise error_type("Synthetic transport failure")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("google.genai.Client", Client)
    with pytest.raises(AIError) as failure:
        gemini_provider.generate("system", "plan", {}, "synthetic-key", "read-v3")
    assert failure.value.code == "timeout"
    assert failure.value.status == 502
    assert "synthetic-key" not in str(failure.value)
