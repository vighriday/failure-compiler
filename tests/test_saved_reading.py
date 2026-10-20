"""Real saved readings retain their labels, provenance and individual review gate."""

import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server import main
from server.reading import items_for_plan, questions_for_plan
from server.review import create_review, update_review
from server.validation.models import AIQuestion
from tests.validation_helpers import ai_reading_payload, confirmed_truth_map


def test_saved_raw_reading_is_rendered_without_overwriting_names_or_inserting_truth(monkeypatch):
    payload = ai_reading_payload()
    payload["places"][0]["name"] = "Hall"
    payload["routes"][0]["name"] = "Route A"
    payload["deliveries"] = []
    record = {
        "provider": "gemini",
        "model": "test-model",
        "timestamp": "2026-10-17T00:00:00Z",
        "raw_text": json.dumps(payload),
    }
    original = main._fixture
    monkeypatch.setattr(
        main,
        "_fixture",
        lambda path: record if path == "fixtures/example-reading.json" else original(path),
    )
    response = TestClient(main.app).post("/api/read-plan", json={"example": True})
    assert response.status_code == 200
    body = response.json()
    assert not body["placeholder"]
    assert body["read_by"] == "Gemini / test-model"
    assert body["plan_map"]["places"][0]["name"] == "Hall"
    assert body["plan_map"]["routes"][0]["name"] == "Route A"
    assert body["plan_map"]["routes"][0]["id"] == "route-a"
    assert body["plan_map"]["deliveries"] == []
    assert any(question.get("kind") == "missing_delivery" for question in body["questions"])
    assert all(item["source_line"] for item in body["items"])
    assert record["raw_text"] == json.dumps(payload)


def test_ai_question_requires_reviewing_its_guessed_facts_individually():
    plan = confirmed_truth_map()
    plan.people[0].guessed = True
    plan.questions = [AIQuestion(item_id=plan.people[0].id, question_text="When do they arrive?")]
    items = items_for_plan(plan)
    state = create_review(plan, items, questions_for_plan(plan, items))
    reading_id = state["reading_id"]
    question = state["questions"][0]
    answer = {
        "reading_id": reading_id,
        "action": "answer",
        "question_id": question["id"],
        "value": "Use the reviewed details",
    }
    with pytest.raises(HTTPException, match="Review the associated facts individually"):
        update_review(answer)
    state = update_review({"reading_id": reading_id, "action": "confirm_all"})
    with pytest.raises(HTTPException, match="Review the associated facts individually"):
        update_review(answer)
    for row in state["items"]:
        if row["entity_id"] == plan.people[0].id and row["status"] == "guessed":
            update_review(
                {"reading_id": reading_id, "action": "confirm_item", "item_id": row["id"]}
            )
    assert update_review(answer)["answers"][question["id"]] == "Use the reviewed details"
