"""The server owns confirmations and constrains every editable fact type."""

import json

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.review import REVIEWS
from server.validation.gate import GateError, validate_ai_reading
from server.validation.rules import validate_plan_rules
from tests.validation_helpers import ROOT, ai_reading_payload

CLIENT = TestClient(app)


@pytest.fixture(autouse=True)
def handmade_review_contract(monkeypatch):
    """Keep the old hardening cases explicit; real reading coverage lives separately."""
    reading = json.loads((ROOT / "tests/fixtures/handmade-reading.json").read_text())
    original = main._fixture
    monkeypatch.setattr(
        main,
        "_fixture",
        lambda path: reading if path == "fixtures/example-reading.json" else original(path),
    )


def draft():
    response = CLIENT.post("/api/read-plan", json={"example": True})
    assert response.status_code == 200, response.text
    return response.json()


def action(reading_id, name, **values):
    response = CLIENT.post(
        "/api/update-map",
        json={
            "reading_id": reading_id,
            "action": name,
            **values,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirmed():
    reading = draft()
    reading_id = reading["reading_id"]
    action(reading_id, "confirm_all")
    action(reading_id, "answer", question_id="ravi-van-loading-question", value="Only his car")
    action(reading_id, "confirm_item", item_id="route-c-loading")
    response = CLIENT.post("/api/confirm-map", json={"reading_id": reading_id})
    assert response.status_code == 200, response.text
    return response.json()


def test_confirmation_cannot_be_bypassed_with_omitted_or_forged_browser_lists():
    reading = draft()
    response = CLIENT.post("/api/confirm-map", json={"plan_map": reading["plan_map"]})
    assert response.status_code == 422
    assert "reading_id" in response.text
    response = CLIENT.post(
        "/api/confirm-map",
        json={
            "reading_id": reading["reading_id"],
            "items": [],
            "questions": [],
            "answers": {},
        },
    )
    assert response.status_code == 422
    assert "ravi-driver" in response.text and "ravi-van-loading-question" in response.text
    action(reading["reading_id"], "confirm_all")
    response = CLIENT.post("/api/confirm-map", json={"reading_id": reading["reading_id"]})
    assert response.status_code == 422
    assert "route-c-loading" in response.text and "ravi-van-loading-question" in response.text
    assert confirmed()["confirmed"] is True


@pytest.mark.parametrize(
    ("item_id", "field", "value", "control_type"),
    [
        ("ravi-availability", "available_from", 545, "time"),
        ("ravi-availability", "available_until", 775, "time"),
        ("ravi-driver", "can_drive", False, "boolean"),
        ("joel-key", "holds_key", False, "boolean"),
        ("loading-team", "loading_team", ["person-joel", "person-anita"], "ordered_people"),
        ("route-a", "driver_ids", ["person-ravi", "person-sam"], "ordered_people"),
        ("route-a", "loader_ids", ["person-joel", "person-anita"], "ordered_people"),
        ("van", "available_from", 575, "time"),
        ("loading-area", "opens_at", 545, "time"),
        ("loading-area", "needs_key", False, "boolean"),
        ("supply-truck", "arrives_at", 545, "time"),
        ("route-a", "vehicle_id", "vehicle-van", "select"),
        ("route-a", "households", 11, "number"),
        ("route-a", "load_minutes", 15, "number"),
        ("route-a", "drive_minutes", 65, "number"),
        ("finish-time", "finish_time", 725, "time"),
    ],
)
def test_every_fact_has_constrained_correction_rules_and_cascade(
    item_id, field, value, control_type
):
    reading = confirmed()
    reading_id = reading["reading_id"]
    before = next(item for item in reading["items"] if item["id"] == item_id)
    control = next(control for control in before["controls"] if control["field"] == field)
    assert control["type"] == control_type
    changed = action(reading_id, "correct", item_id=item_id, field=field, value=value)
    assert changed["confirmed"] is False
    assert changed["out_of_date"] is True
    assert changed["plan_map"]["fingerprint"] is None
    assert any(item["status"] == "stale" for item in changed["items"])
    assert next(item for item in changed["items"] if item["id"] == item_id)["status"] == "corrected"
    assert changed["issues"] == [
        issue.__dict__ for issue in validate_plan_rules(REVIEWS[reading_id].plan)
    ]
    if field == "can_drive":
        assert len(changed["issues"]) == 3
        assert all("Ravi" in issue["message"] for issue in changed["issues"])
        assert all(route["status"] == "unconfirmed" for route in changed["plan_map"]["routes"])


@pytest.mark.parametrize("value", ["30", True, 30.5])
def test_ai_integer_fields_reject_coercion(value):
    payload = ai_reading_payload()
    payload["routes"][0]["load_minutes"] = value
    with pytest.raises(GateError, match="load_minutes"):
        validate_ai_reading(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("can_drive", "true"),
        ("can_drive", 1),
        ("holds_key", "false"),
        ("guessed", 0),
    ],
)
def test_ai_boolean_fields_reject_coercion(field, value):
    payload = ai_reading_payload()
    payload["people"][0][field] = value
    with pytest.raises(GateError, match=field):
        validate_ai_reading(payload)


def test_duplicate_ids_are_a_named_422_at_http_boundary():
    reading = draft()
    plan = reading["plan_map"]
    plan["people"][1]["id"] = plan["people"][0]["id"]
    response = CLIENT.post("/api/validate-map", json={"plan_map": plan})
    assert response.status_code == 422
    assert "Duplicate id 'person-ravi'" in response.text


@pytest.mark.parametrize(
    ("collection", "index", "field", "value"),
    [
        ("people", 0, "available_from", -1),
        ("people", 0, "available_until", 1440),
        ("people", 0, "available_until", 540),
        ("vehicles", 0, "available_from", 1440),
        ("places", 0, "opens_at", -1),
        ("deliveries", 0, "arrives_at", 1440),
        ("routes", 0, "households", 501),
        ("routes", 0, "load_minutes", 7),
        ("routes", 0, "drive_minutes", 245),
    ],
)
def test_invalid_bounds_cannot_be_confirmed(collection, index, field, value):
    reading = confirmed()
    review = REVIEWS[reading["reading_id"]]
    setattr(getattr(review.plan, collection)[index], field, value)
    response = CLIENT.post("/api/confirm-map", json={"reading_id": reading["reading_id"]})
    assert response.status_code == 422
    assert field in response.text or "before" in response.text


@pytest.mark.parametrize("collection", ["people", "routes"])
def test_empty_required_collection_cannot_be_confirmed(collection):
    reading = confirmed()
    review = REVIEWS[reading["reading_id"]]
    setattr(review.plan, collection, [])
    response = CLIENT.post("/api/confirm-map", json={"reading_id": reading["reading_id"]})
    assert response.status_code == 422
    assert collection in response.text or "Unknown person" in response.text


def test_rejected_correction_is_transactional_and_does_not_trust_browser_fields():
    reading = confirmed()
    response = CLIENT.post(
        "/api/update-map",
        json={
            "reading_id": reading["reading_id"],
            "action": "correct",
            "item_id": "route-a",
            "field": "driver_ids",
            "value": ["person-dave"],
        },
    )
    assert response.status_code == 422 and "person-dave" in response.text
    assert REVIEWS[reading["reading_id"]].plan.routes[0].driver_ids[0] == "person-ravi"
