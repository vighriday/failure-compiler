from fastapi.testclient import TestClient

from server import main
from server.ai.types import AIError
from server.credentials import CLIENTS
from server.rate_limit import MAX_REQUESTS_PER_WINDOW, clear_rate_limits


def setup_function():
    CLIENTS.clear()
    clear_rate_limits()


def test_live_read_plan_has_plan_size_limit_and_rate_limit(monkeypatch):
    client = TestClient(main.app)
    oversized = "x" * 4001
    response = client.post("/api/read-plan", json={"text": oversized})
    assert response.status_code == 422

    def provider_failure(*args, **kwargs):
        raise AIError("providers_failed", "stub provider failure")

    monkeypatch.setattr(main.adapter, "read_plan", provider_failure)
    for _ in range(MAX_REQUESTS_PER_WINDOW - 1):
        result = client.post("/api/read-plan", json={"text": "plan", "api_key": "key"})
        assert result.status_code == 502
    limited = client.post("/api/read-plan", json={"text": "plan", "api_key": "key"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
