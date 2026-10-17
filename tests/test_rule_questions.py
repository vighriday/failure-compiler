"""Only rule questions add missing facts; additions stay constrained and sourced honestly."""

import json

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.review import create_review
from tests.validation_helpers import ROOT, confirmed_truth_map

CLIENT = TestClient(app)


def review_with_missing(field):
    plan = confirmed_truth_map()
    if field == "supply_delivery":
        plan.deliveries = []
    elif field == "finish_time":
        plan.finish_time = 0
    else:
        setattr(plan.routes[0], field, "" if field == "vehicle_id" else [])
    items = json.loads((ROOT / "fixtures/example-reading.json").read_text())["items"]
    items = [
        {**item, "status": "confirmed"}
        for item in items
        if field != "supply_delivery" or item["entity_type"] != "delivery"
    ]
    reading = create_review(plan, items, [])
    question = next(q for q in reading["questions"] if q.get("field") == field)
    return reading, question


def answer(reading, question, value):
    return CLIENT.post(
        "/api/update-map",
        json={
            "reading_id": reading["reading_id"],
            "action": "answer",
            "question_id": question["id"],
            "value": value,
        },
    )


def test_missing_delivery_requires_individual_answer_and_no_delivery_is_explicit():
    reading, question = review_with_missing("supply_delivery")
    assert (
        question["question_text"]
        == "The loading area has no supply delivery listed. Is one expected?"
    )
    assert question["choices"] == ["No delivery", "Add a delivery"]
    forged = CLIENT.post(
        "/api/confirm-map",
        json={"reading_id": reading["reading_id"], "answers": {question["id"]: "No delivery"}},
    )
    assert forged.status_code == 422 and question["id"] in forged.text
    response = answer(reading, question, "No delivery")
    assert response.status_code == 200, response.text
    assert response.json()["plan_map"]["deliveries"] == []
    assert not response.json()["issues"]
    assert (
        CLIENT.post("/api/confirm-map", json={"reading_id": reading["reading_id"]}).status_code
        == 200
    )


def test_added_delivery_has_fixed_label_no_source_added_status_and_counts_in_summary():
    reading, question = review_with_missing("supply_delivery")
    response = answer(
        reading,
        question,
        {"choice": "Add a delivery", "arrives_at": 540, "place_id": "place-loading-area"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    delivery = result["plan_map"]["deliveries"][0]
    assert delivery["name"] == "Supply delivery"
    assert delivery["status"] == "confirmed"  # Server entity status aggregates its accepted facts.
    assert delivery["source_line"] == ""
    item = next(item for item in result["items"] if item["entity_id"] == delivery["id"])
    assert item["status"] == "added" and item["source_line"] is None
    assert len(result["items"]) == len(reading["items"]) + 1
    assert result["unconfirmed_items"] == sum(item["status"] == "stale" for item in result["items"])
    assert not any(issue["field"] == "supply_delivery" for issue in result["issues"])


@pytest.mark.parametrize(
    "value",
    [
        {"choice": "Add a delivery", "arrives_at": "540", "place_id": "place-loading-area"},
        {"choice": "Add a delivery", "arrives_at": 1440, "place_id": "place-loading-area"},
        {"choice": "Add a delivery", "arrives_at": 540, "place_id": "place-made-up"},
        "A handwritten delivery",
    ],
)
def test_delivery_answers_reject_free_text_bad_references_and_bad_times(value):
    reading, question = review_with_missing("supply_delivery")
    response = answer(reading, question, value)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vehicle_id", "vehicle-car"),
        ("driver_ids", ["person-ravi"]),
        ("loader_ids", ["person-joel"]),
        ("finish_time", 720),
    ],
)
def test_missing_assignments_and_finish_time_use_rule_questions(field, value):
    reading, question = review_with_missing(field)
    assert question["kind"] in {"missing_assignment", "missing_finish"}
    row = next(
        item
        for item in reading["items"]
        if item["entity_type"] == ("plan" if field == "finish_time" else "route")
    )
    ordinary = CLIENT.post(
        "/api/update-map",
        json={
            "reading_id": reading["reading_id"],
            "action": "correct",
            "item_id": row["id"],
            "field": field,
            "value": value,
        },
    )
    assert ordinary.status_code == 422 and "rule question" in ordinary.text
    response = answer(reading, question, value)
    assert response.status_code == 200, response.text
    assert not any(issue["field"] == field for issue in response.json()["issues"])
    assert any(
        item["field"] == field and item["status"] == "added" and item["source_line"] is None
        for item in response.json()["items"]
    )


def test_addition_cannot_be_requested_without_a_rule_question():
    reading = create_review(confirmed_truth_map(), [], [])
    response = CLIENT.post(
        "/api/update-map",
        json={"reading_id": reading["reading_id"], "action": "add_delivery", "value": "anything"},
    )
    assert response.status_code == 422
