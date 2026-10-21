"""The production SPA does not swallow missing APIs or its licence notice."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_unknown_api_is_not_a_successful_html_page():
    response = TestClient(app).get("/api/this-endpoint-does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_bundled_notices_are_served_as_text_when_frontend_is_built():
    # Static routes are installed only when a production frontend exists.
    if not (ROOT / "web/dist/index.html").exists():
        pytest.skip("Build the frontend to check its bundled notices")
    response = TestClient(app).get("/third-party-notices.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "SIL OPEN FONT LICENSE" in response.text
    assert "<!doctype html>" not in response.text.lower()


def test_frontend_docker_inputs_include_the_plan_import():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8").split("AS runtime", 1)[0]
    copy = "COPY fixtures/example-plan.txt ./fixtures/example-plan.txt"
    assert copy in docker
    assert docker.index(copy) < docker.index("RUN npm run build")
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for private in (".env", ".env.*", ".venv", "devpost/learner-profile.md", ".oxcode-memory"):
        assert private in ignored
