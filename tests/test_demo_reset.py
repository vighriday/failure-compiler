"""Reset one browser completely without touching another browser or trusted helpers."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from server import credentials, fixes, grid
from server.ai.adapter import FixResult, ReadingResult
from server.ai.types import AIError, AIFixResponse, ProviderResponse
from server.demo import discard_browser
from server.main import app
from server.models import FixSuggestion, ScenarioResult
from server.reading import items_for_plan
from server.review import REVIEWS, create_review
from server.session import OWNED_SESSIONS, SESSIONS, capture_map, remember_map
from server.validation.gate import validate_ai_reading
from tests.validation_helpers import confirmed_truth_map

ROOT = Path(__file__).resolve().parents[1]
JOEL = "volunteer_absent__person-joel"
STORES = (
    credentials.CLIENTS,
    REVIEWS,
    OWNED_SESSIONS,
    SESSIONS,
    fixes.SCORED,
    fixes.DETAILS,
    fixes.RAW_FIXES,
    fixes.FIX_LOCKS,
    fixes.RETRIED,
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for store in STORES:
        store.clear()
    monkeypatch.setattr(credentials, "dotenv_values", lambda _: {})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield
    for store in STORES:
        store.clear()


def read_example(client, key):
    response = client.post(
        "/api/read-plan", json={"example": True, "api_key": key, "key_provider": "gemini"}
    )
    assert response.status_code == 200, response.text
    state = response.json()
    ledger = json.loads((ROOT / "fixtures/example-corrections.json").read_text("utf-8"))
    for action in ledger["actions"]:
        response = client.post(
            "/api/update-map", json={"reading_id": state["reading_id"], **action}
        )
        assert response.status_code == 200, response.text
    response = client.post("/api/confirm-map", json={"reading_id": state["reading_id"]})
    assert response.status_code == 200, response.text
    return state["reading_id"], response.json()["fingerprint"]


def seed_cache(key):
    fixes.SCORED[key] = [
        fixes.ScoredFix(FixSuggestion(id="saved", description="saved", operations=[]), None)
    ]
    fixes.DETAILS[key] = {"private": "saved suggestion"}
    fixes.RAW_FIXES[key] = [{"raw_text": "saved private response"}]
    fixes.FIX_LOCKS[key] = Lock()
    fixes.RETRIED.add(key)


def test_reset_rotates_cookie_and_clears_only_this_browser_scopes(caplog):
    first, second = TestClient(app), TestClient(app)
    first_reading, fingerprint = read_example(first, "first-private-typed-key")
    second_reading, same_fingerprint = read_example(second, "second-private-typed-key")
    assert fingerprint == same_fingerprint
    owner = first.cookies[credentials.COOKIE_NAME]
    other = second.cookies[credentials.COOKIE_NAME]
    old_client = credentials.CLIENTS[owner]
    session = OWNED_SESSIONS[owner, fingerprint]
    other_session = OWNED_SESSIONS[other, fingerprint]
    outcome = ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")
    for current in (session, other_session):
        current.results = [outcome]
        current.suggestion_batches.append({"private": "requested suggestion"})
    changed = session.plan.model_copy(deep=True)
    changed.people[0].available_until += 5
    child_fp = remember_map(
        changed, [outcome], owner=owner, ancestors={fingerprint: capture_map(session)}
    )
    child = OWNED_SESSIONS[owner, child_fp]
    captured = capture_map(session)
    first_key, other_key = (owner, fingerprint, 0, JOEL), (other, fingerprint, 0, JOEL)
    helper_key = (owner, "unowned-two-part-cache")
    for key in (first_key, other_key, helper_key):
        seed_cache(key)
    helper = confirmed_truth_map()
    helper.finish_time += 1
    helper_fp = remember_map(helper, [outcome])
    helper_review = create_review(helper, items_for_plan(helper), [])
    response = first.post("/api/demo/reset")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert response.headers["cache-control"] == "no-store"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    fresh = first.cookies[credentials.COOKIE_NAME]
    assert fresh not in {owner, other} and owner not in credentials.CLIENTS
    assert old_client.keys == {} and old_client.selected_provider is None
    assert credentials.CLIENTS[fresh].keys == {}
    assert credentials.CLIENTS[other].keys == {"gemini": "second-private-typed-key"}
    assert first_reading not in REVIEWS and second_reading in REVIEWS
    assert helper_review["reading_id"] in REVIEWS
    assert not any(key[0] == owner for key in OWNED_SESSIONS)
    assert OWNED_SESSIONS[other, fingerprint] is other_session
    assert other_session.results == [outcome] and other_session.suggestion_batches
    assert helper_fp in SESSIONS
    assert session.revision == captured.revision + 1
    for removed in (session, child):
        assert removed.results is None
        assert (
            not removed.ancestors and not removed.suggestion_batches and not removed.review_evidence
        )
    for store in (fixes.SCORED, fixes.DETAILS, fixes.RAW_FIXES, fixes.FIX_LOCKS, fixes.RETRIED):
        assert first_key not in store
        assert other_key in store and helper_key in store
    assert first.get("/api/ai-status").json()["key_available"] == {"gemini": False, "groq": False}
    assert first.get(f"/api/run-tests?map={fingerprint}").status_code == 404
    assert first.get(f"/api/report?map={fingerprint}").status_code == 404
    body = {"fingerprint": fingerprint, "scenario_id": JOEL}
    assert first.post("/api/suggest-fixes", json=body).status_code == 409
    assert first.post("/api/apply-fix", json={**body, "fix_id": "saved"}).status_code == 409
    for endpoint in ("/api/validate-map", "/api/update-map", "/api/confirm-map"):
        assert first.post(endpoint, json={"reading_id": first_reading}).status_code in {404, 422}
    assert second.post("/api/validate-map", json={"reading_id": second_reading}).status_code == 200
    assert "first-private-typed-key" not in response.text + caplog.text
    assert "second-private-typed-key" not in response.text + caplog.text


def test_repeated_reset_and_replayed_old_cookie_never_restore_state():
    client = TestClient(app)
    client.get("/api/health")
    owners = {client.cookies[credentials.COOKIE_NAME]}
    for _ in range(3):
        response = client.post("/api/demo/reset")
        assert response.status_code == 200
        owner = client.cookies[credentials.COOKIE_NAME]
        assert owner not in owners
        owners.add(owner)
        assert set(credentials.CLIENTS) == {owner}
    replay = TestClient(app)
    replay.cookies.set(
        credentials.COOKIE_NAME,
        next(item for item in owners if item != owner),
        domain="testserver.local",
        path="/",
    )
    response = replay.get("/api/ai-status")
    assert response.status_code == 200
    assert replay.cookies[credentials.COOKIE_NAME] not in owners
    assert response.json()["selected_provider"] is None
    assert response.json()["key_available"] == {"gemini": False, "groq": False}
    assert not REVIEWS and not OWNED_SESSIONS


@pytest.mark.parametrize("provider_error", [False, True, "expired_lookup"])
def test_late_read_cannot_persist_after_reset_or_return_a_key(monkeypatch, caplog, provider_error):
    client = TestClient(app)
    client.get("/api/health")
    owner = client.cookies[credentials.COOKIE_NAME]
    pending_client = TestClient(app)
    pending_client.cookies.set(credentials.COOKIE_NAME, owner, domain="testserver.local", path="/")
    started, release = Event(), Event()
    record = json.loads((ROOT / "fixtures/example-reading.json").read_text("utf-8"))

    def delayed(text, keys, **kwargs):
        assert keys["gemini"] == "pending-private-typed-key"
        started.set()
        assert release.wait(timeout=10)
        if provider_error == "expired_lookup":
            raise KeyError(owner)
        if provider_error:
            raise AIError("server_error", "Unexpected pending-private-typed-key", status=503)
        return ReadingResult(
            ProviderResponse(**record), validate_ai_reading(record["raw_text"]), []
        )

    monkeypatch.setattr("server.main.adapter.read_plan", delayed)
    with ThreadPoolExecutor(max_workers=1) as workers:
        pending = workers.submit(
            pending_client.post,
            "/api/read-plan",
            json={"text": "An offline plan", "api_key": "pending-private-typed-key"},
        )
        assert started.wait(timeout=10)
        try:
            assert client.post("/api/demo/reset").status_code == 200
        finally:
            release.set()
        response = pending.result(timeout=10)
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers
    assert owner not in credentials.CLIENTS
    assert not any(review.owner == owner for review in REVIEWS.values())
    assert not any(key[0] == owner for key in OWNED_SESSIONS)
    assert "pending-private-typed-key" not in response.text + caplog.text


def test_old_stream_and_suggestion_cannot_reinstall_reset_results_or_caches(monkeypatch):
    owner = credentials.browser_session(None)
    credentials.remember_key(owner, "gemini", "offline-private-key")
    plan = confirmed_truth_map()
    result = ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")
    fingerprint = remember_map(plan, owner=owner)
    session = OWNED_SESSIONS[owner, fingerprint]
    request = Request({"type": "http", "state": {"owner": owner}})
    monkeypatch.setattr(grid, "iter_checker", lambda _: iter([result]))
    response = grid.run_tests(request, map=fingerprint, reduced_motion=True)
    captured = capture_map(session)
    discard_browser(owner)

    async def consume():
        return [part async for part in response.body_iterator]

    assert asyncio.run(consume())
    assert session.revision > captured.revision and session.results is None
    assert (owner, fingerprint) not in OWNED_SESSIONS
    # A provider call that was already running must also fail its revision check.
    second_owner = credentials.browser_session(None)
    credentials.remember_key(second_owner, "gemini", "offline-private-key")
    fingerprint = remember_map(plan, [result], owner=second_owner, source="live")
    raw = ProviderResponse("gemini", "offline-model", "fix-v1", "", "{}", 0, 0, 0, {})

    def delayed(*args, **kwargs):
        discard_browser(second_owner)
        return FixResult(raw, AIFixResponse(explanation="Offline response", fixes=[]), [])

    monkeypatch.setattr(fixes.adapter, "suggest_fixes", delayed)
    request = Request({"type": "http", "state": {"owner": second_owner}})
    with pytest.raises(HTTPException) as failure:
        fixes.suggest_fixes(
            fixes.SuggestRequest(fingerprint=fingerprint, scenario_id=JOEL), request
        )
    assert failure.value.status_code == 409
    assert not OWNED_SESSIONS
    for store in (fixes.SCORED, fixes.DETAILS, fixes.RAW_FIXES, fixes.FIX_LOCKS, fixes.RETRIED):
        assert not any(len(key) == 4 and key[0] == second_owner for key in store)


def test_fix_lock_allocated_after_reset_is_removed_when_the_stale_http_request_finishes(
    monkeypatch,
):
    client = TestClient(app)
    client.get("/api/health")
    owner = client.cookies[credentials.COOKIE_NAME]
    plan = confirmed_truth_map()
    result = ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")
    fingerprint = remember_map(plan, [result], owner=owner)
    pending_client = TestClient(app)
    pending_client.cookies.set(credentials.COOKIE_NAME, owner, domain="testserver.local", path="/")
    started, release = Event(), Event()
    original_capture = fixes.capture_map

    def delayed(session):
        captured = original_capture(session)
        started.set()
        assert release.wait(timeout=10)
        return captured

    monkeypatch.setattr(fixes, "capture_map", delayed)
    with ThreadPoolExecutor(max_workers=1) as workers:
        pending = workers.submit(
            pending_client.post,
            "/api/suggest-fixes",
            json={"fingerprint": fingerprint, "scenario_id": JOEL},
        )
        assert started.wait(timeout=10)
        try:
            assert client.post("/api/demo/reset").status_code == 200
        finally:
            release.set()
        response = pending.result(timeout=10)
    assert response.status_code == 409
    assert not any(len(key) == 4 and key[0] == owner for key in fixes.FIX_LOCKS)
    assert not OWNED_SESSIONS and not fixes.SCORED and not fixes.DETAILS
