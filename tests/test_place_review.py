"""Place identity choices stay individual, constrained, reversible and server-owned."""

import pytest
from fastapi import HTTPException

from server.reading import items_for_plan, questions_for_plan
from server.review import REVIEWS, confirm_review, create_review, update_review
from server.validation.models import AIQuestion
from tests.validation_helpers import confirmed_truth_map


def draft():
    plan = confirmed_truth_map()
    plan.places.append(
        plan.places[0].model_copy(
            update={
                "id": "place-extra",
                "name": "Community hall",
                "needs_key": False,
                "one_vehicle_at_a_time": False,
                "source_line": "L3",
            }
        )
    )
    plan.questions = [AIQuestion(item_id="place-extra", question_text="What time does it open?")]
    items = items_for_plan(plan)
    return create_review(plan, items, questions_for_plan(plan, items))


def act(state, action, **values):
    return update_review({"reading_id": state["reading_id"], "action": action, **values})


def merge(state, target="place-loading-area"):
    return act(
        state,
        "answer",
        question_id="rule-place-extra-identity",
        value={
            "choice": "Same place as another listing",
            "place_id": target,
        },
    )


def test_bulk_and_forged_browser_answers_cannot_resolve_identity():
    state = act(draft(), "confirm_all")
    assert len(state["plan_map"]["places"]) == 2
    assert "rule-place-extra-identity" not in state["answers"]
    with pytest.raises(HTTPException, match="rule-place-extra-identity"):
        confirm_review(
            {
                "reading_id": state["reading_id"],
                "answers": {
                    "rule-place-extra-identity": "Keep as a separate place",
                },
            }
        )
    state = act(
        state, "answer", question_id="rule-place-extra-identity", value="Keep as a separate place"
    )
    assert len(state["plan_map"]["places"]) == 2


@pytest.mark.parametrize("target", ["place-extra", "missing", 4, None])
def test_invalid_target_is_rejected_without_partial_mutation(target):
    state = draft()
    with pytest.raises(HTTPException, match="Invalid place_id"):
        merge(state, target)
    assert len(REVIEWS[state["reading_id"]].plan.places) == 2


def test_merge_preserves_source_trace_retargets_questions_and_change_restores_it():
    state = draft()
    original = state["plan_map"]["places"][1]
    state = act(state, "confirm_all")
    state = merge(state)
    assert len(state["plan_map"]["places"]) == 1
    assert (
        "Community hall is the same place as Loading area"
        in state["answers"]["rule-place-extra-identity"]
    )
    question = next(q for q in state["questions"] if q.get("kind") == "place_identity")
    assert question["merge"]["source"]["source_line"] == "L3"
    assert state["plan_map"]["questions"][0]["item_id"] == "place-loading-area"
    assert all(
        row["status"] == "stale"
        for row in state["items"]
        if row["entity_type"] in {"place", "route"}
    )
    state = act(state, "confirm_all")
    assert any(row["status"] == "stale" for row in state["items"])
    state = act(state, "reopen_question", question_id=question["id"])
    restored = next(place for place in state["plan_map"]["places"] if place["id"] == "place-extra")
    assert {k: v for k, v in restored.items() if k != "status"} == {
        k: v for k, v in original.items() if k != "status"
    }
    assert state["plan_map"]["questions"][0]["item_id"] == "place-extra"
    assert question["id"] not in state["answers"]


def test_a_place_with_supply_activity_cannot_be_merged_by_a_forged_question_id():
    state = draft()
    with pytest.raises(HTTPException, match="Unknown question_id"):
        act(
            state,
            "answer",
            question_id="rule-place-loading-area-identity",
            value={
                "choice": "Same place as another listing",
                "place_id": "place-extra",
            },
        )
