"""A completed old stream or AI request cannot replace a newer reading's cache."""

import asyncio
import json

import pytest
from fastapi import HTTPException, Request

from server import fixes, grid
from server.ai.adapter import FixResult
from server.ai.types import AIFixResponse, ProviderResponse
from server.credentials import CLIENTS, ClientSession
from server.models import ScenarioResult
from server.session import OWNED_SESSIONS, capture_map, remember_map
from tests.validation_helpers import confirmed_truth_map

OWNER = "revision-test-owner"
JOEL = "volunteer_absent__person-joel"


@pytest.fixture(autouse=True)
def isolated():
    OWNED_SESSIONS.clear()
    CLIENTS.clear()
    CLIENTS[OWNER] = ClientSession()
    for store in (fixes.DETAILS, fixes.SCORED, fixes.RAW_FIXES, fixes.FIX_LOCKS, fixes.RETRIED):
        store.clear()


def http_request():
    return Request({"type": "http", "state": {"owner": OWNER}})


def rename_delivery(plan):
    changed = plan.model_copy(deep=True)
    changed.deliveries[0].id = "delivery-incoming-truck"
    changed.deliveries[0].name = "Incoming truck"
    changed.ai_meta.provider = "new-provider"
    changed.ai_meta.model = "new-model"
    return changed


@pytest.mark.parametrize("change_before_start", [True, False])
def test_cached_stream_uses_one_snapshot_and_cannot_restore_old_ids(
    monkeypatch, change_before_start
):
    plan = confirmed_truth_map()
    old_problem = "supply_delivery_late__" + plan.deliveries[0].id
    cached = [ScenarioResult(scenario_id=old_problem, failures=[old_problem], state="tick")]
    fp = remember_map(plan, cached, owner=OWNER)
    session = OWNED_SESSIONS[OWNER, fp]
    response = grid.run_tests(http_request(), map=fp, reduced_motion=True)

    def no_solver(_):
        raise AssertionError("The stream captured a complete cache before it was invalidated")

    monkeypatch.setattr(grid, "iter_checker", no_solver)

    async def consume():
        stream = response.body_iterator
        output = []
        if not change_before_start:
            output.extend([await anext(stream), await anext(stream)])
        assert remember_map(rename_delivery(plan), owner=OWNER) == fp
        assert session.results is None
        async for event in stream:
            output.append(event)
        return [json.loads(event[6:]) for event in output]

    events = asyncio.run(consume())
    assert events[0]["read_by"] == "fixture / truth-map"
    assert events[0]["source"] == "saved"
    results = [event["result"] for event in events if event["type"] == "result"]
    assert [row["scenario_id"] for row in results] == [old_problem]
    assert session.results is None
    assert session.plan.deliveries[0].id == "delivery-incoming-truck"


def test_metadata_only_new_reading_also_invalidates_revision():
    plan = confirmed_truth_map()
    fp = remember_map(plan, owner=OWNER)
    session = OWNED_SESSIONS[OWNER, fp]
    captured = capture_map(session)
    changed = plan.model_copy(deep=True)
    changed.ai_meta.provider = "other-provider"
    assert remember_map(changed, owner=OWNER) == fp
    assert session.revision == captured.revision + 1


@pytest.mark.parametrize("change_during", ["generation", "scoring"])
def test_live_suggestion_stale_during_generation_or_scoring_returns_409(monkeypatch, change_during):
    plan = confirmed_truth_map()
    current = [ScenarioResult(scenario_id=JOEL, failures=[JOEL], state="cross")]
    fp = remember_map(plan, current, owner=OWNER, source="live")
    raw = ProviderResponse("gemini", "offline-model", "fix-v1", "", "{}", 0, 0, 0, {})
    suggestions = AIFixResponse(explanation="Synthetic response", fixes=[])
    if change_during == "scoring":
        suggestions = AIFixResponse.model_validate(
            {
                "explanation": "Synthetic response",
                "fixes": [{"id": "test", "description": "test", "operations": []}],
            }
        )

    def generate(*args, **kwargs):
        if change_during == "generation":
            assert remember_map(rename_delivery(plan), owner=OWNER, source="live") == fp
        return FixResult(raw, suggestions, [{"provider": "gemini", "status": "passed"}])

    def score(captured_plan, captured_results, scenario_id, suggestion):
        # Even if the shared session changes, scoring sees the captured original.
        assert captured_plan.deliveries[0].id == plan.deliveries[0].id
        assert captured_results[0].scenario_id == JOEL
        assert remember_map(rename_delivery(plan), owner=OWNER, source="live") == fp
        return fixes.ScoredFix(
            fixes.FixSuggestion(id="test", description="test", operations=[]), None
        )

    monkeypatch.setattr(fixes.adapter, "suggest_fixes", generate)
    monkeypatch.setattr(fixes, "available_keys", lambda _: {"gemini": "offline"})
    monkeypatch.setattr(fixes, "score_fix", score)
    with pytest.raises(HTTPException, match="This reading changed") as failure:
        fixes.suggest_fixes(fixes.SuggestRequest(fingerprint=fp, scenario_id=JOEL), http_request())
    assert failure.value.status_code == 409
    assert not fixes.SCORED and not fixes.DETAILS and not fixes.RAW_FIXES
    assert OWNED_SESSIONS[OWNER, fp].plan.deliveries[0].id == "delivery-incoming-truck"
