"""Reports use the owned confirmed run and immutable fix evidence, with no AI/solve calls."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from server import session
from server.main import app
from server.models import ScenarioResult
from server.report import build_report, history_for
from tests.test_live_api import isolated as isolated
from tests.test_live_api import read_and_confirm, run


def test_report_available_after_first_run_and_is_session_private(monkeypatch):
    client = TestClient(app)
    _, confirmed = read_and_confirm(client, example=True)
    fp = confirmed["fingerprint"]
    assert client.get("/api/report", params={"map": fp}).status_code == 409
    run(client, fp)
    monkeypatch.setattr(
        "server.checker.runner.run_checker", lambda _: pytest.fail("Report must not solve")
    )
    monkeypatch.setattr(
        "server.ai.adapter.suggest_fixes", lambda *args: pytest.fail("Report must not call AI")
    )
    response = client.get("/api/report", params={"map": fp})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["source"] == "saved" and report["read_by"].startswith("Gemini / ")
    assert report["summary"]["ai_read"] == 32
    assert report["summary"]["corrected"] == 1
    assert report["summary"]["added"] == 0
    assert len(report["facts"]) == 30
    assert report["overview"]["accepted"] == report["overview"]["ai_suggested"] == 0
    assert "30 households not delivered" in report["overview"]["main_human_cost"]
    arrivals = [answer for answer in report["review_answers"] if "from" in answer["question"]]
    assert len(arrivals) == 4 and all(answer["answer"] == "09:00" for answer in arrivals)
    assert all(
        answer["answer"] != "Use the reviewed details" for answer in report["review_answers"]
    )
    assert all(row["source_line"] for row in report["facts"])
    assert report["before"] == report["after"]
    assert report["after"]["total"] == 100 and len(report["after"]["problems"]) == 14
    assert len(report["broken_before"]) == 4
    assert [group["count"] for group in report["dimmed_groups"]] == [12]
    assert not report["accepted_fixes"]
    assert not report["unknown_results"]
    assert "volunteers arriving late" in " ".join(report["not_tested"])
    assert TestClient(app).get("/api/report", params={"map": fp}).status_code == 404
    assert client.get("/api/report", params={"map": "unknown"}).status_code == 404


def test_unknowns_are_named_and_never_claimed_as_survived():
    client = TestClient(app)
    _, confirmed = read_and_confirm(client, example=True)
    fp = confirmed["fingerprint"]
    owner = client.cookies.get("failure_session")
    stored = session.get_map(fp, owner)
    assert stored is not None
    stored.results = [
        ScenarioResult(
            scenario_id="volunteer_absent__person-ravi",
            failures=["volunteer_absent__person-ravi"],
            state="qmark",
        )
    ]
    report = client.get("/api/report", params={"map": fp}).json()
    assert report["unknown_results"] == [{"label": "Ravi absent", "phases": ["Before", "After"]}]
    assert report["after"]["count"]["survived"] == 0


def test_report_rejects_missing_or_broken_history_links():
    client = TestClient(app)
    _, confirmed = read_and_confirm(client, example=True)
    fp = confirmed["fingerprint"]
    run(client, fp)
    stored = session.get_map(fp, client.cookies.get("failure_session"))
    from server.models import AppliedFix

    stored.plan.fix_history = [
        AppliedFix(
            fix_id="missing",
            description="Missing snapshot",
            operations=[],
            from_fingerprint="absent",
            to_fingerprint=fp,
        )
    ]
    assert client.get("/api/report", params={"map": fp}).status_code == 409


def test_report_build_does_not_mutate_run_or_review_evidence():
    client = TestClient(app)
    _, confirmed = read_and_confirm(client, example=True)
    fp = confirmed["fingerprint"]
    run(client, fp)
    chain = history_for(fp, client.cookies.get("failure_session"))
    before = deepcopy(chain)
    result = build_report(chain)
    assert chain == before
    result["facts"][0]["statement"] = "Browser edit"
    assert chain == before
