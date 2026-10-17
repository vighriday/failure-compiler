"""Missing facts are added only through explicit rule questions and constrained answers."""

from fastapi import HTTPException
from pydantic import TypeAdapter

from server.place_review import sync_place_questions
from server.validation.models import MapDelivery
from server.validation.rules import validate_plan_rules


def sync_rule_questions(review) -> None:
    sync_place_questions(review)
    for issue in validate_plan_rules(review.plan):
        kind = None
        if issue.field == "supply_delivery":
            kind = "missing_delivery"
        elif issue.field in {"driver_ids", "loader_ids", "vehicle_id"} and not issue.bad_value:
            kind = "missing_assignment"
        elif issue.field == "finish_time" and review.plan.finish_time <= 0:
            kind = "missing_finish"
        if kind is None:
            continue
        question_id = f"rule-{issue.item_id}-{issue.field}"
        existing = next((q for q in review.questions if q["id"] == question_id), None)
        if existing:
            review.answers.pop(question_id, None)
            continue
        item = next((row for row in review.items if row["entity_id"] == issue.item_id), None)
        review.questions.append(
            {
                "id": question_id,
                "item_id": item["id"] if item else issue.item_id,
                "entity_id": issue.item_id,
                "field": issue.field,
                "kind": kind,
                "question_text": issue.message,
                "source_line": None,
                "choices": ["No delivery", "Add a delivery"] if kind == "missing_delivery" else [],
            }
        )


def _added_item(review, kind, entity_id, field):
    item_id = f"added-{entity_id}-{field}"
    if not any(item["id"] == item_id for item in review.items):
        review.items.append(
            {
                "id": item_id,
                "entity_type": kind,
                "entity_id": entity_id,
                "field": field,
                "group": "Times" if kind in {"delivery", "plan"} else "Routes",
                "status": "added",
                "source_line": None,
                "original_statement": None,
            }
        )


def _minute(value, *, finish=False):
    value = TypeAdapter(int).validate_python(value, strict=True)
    if not (1 if finish else 0) <= value < 1440:
        raise HTTPException(422, f"Time value {value!r} must be within the day")
    return value


def answer_rule_question(review, question, value) -> None:
    kind = question["kind"]
    invalidate_routes = True
    if kind == "missing_delivery":
        choice = value.get("choice") if isinstance(value, dict) else value
        place_id = question["entity_id"]
        if choice == "No delivery":
            added_id = question.pop("added_delivery_id", None)
            invalidate_routes = added_id is not None
            review.plan.deliveries = [
                entity for entity in review.plan.deliveries if entity.id != added_id
            ]
            review.items = [item for item in review.items if item["entity_id"] != added_id]
            if place_id not in review.plan.no_delivery_place_ids:
                review.plan.no_delivery_place_ids.append(place_id)
        elif choice == "Add a delivery" and isinstance(value, dict):
            arrives_at = _minute(value.get("arrives_at"))
            if value.get("place_id") != place_id or place_id not in {
                p.id for p in review.plan.places
            }:
                raise HTTPException(
                    422, f"Choose the loading place {place_id!r} for this delivery question"
                )
            added_id = question.get("added_delivery_id")
            delivery = next((d for d in review.plan.deliveries if d.id == added_id), None)
            if delivery:
                delivery.arrives_at = arrives_at
            else:
                index = 1
                ids = {entity.id for entity in review.plan.deliveries}
                while f"delivery-added-{index}" in ids:
                    index += 1
                added_id = f"delivery-added-{index}"
                review.plan.deliveries.append(
                    MapDelivery(
                        id=added_id,
                        name="Supply delivery",
                        arrives_at=arrives_at,
                        place_id=place_id,
                        status="added",
                        source_line="",
                        guessed=False,
                    )
                )
                question["added_delivery_id"] = added_id
            review.plan.no_delivery_place_ids = [
                p for p in review.plan.no_delivery_place_ids if p != place_id
            ]
            _added_item(review, "delivery", added_id, "arrives_at")
        else:
            raise HTTPException(
                422, "Choose 'No delivery' or 'Add a delivery' with arrival time and place"
            )
        review.answers[question["id"]] = choice
    elif kind == "missing_finish":
        review.plan.finish_time = _minute(value, finish=True)
        review.plan.finish_time_source = ""
        review.plan.finish_time_guessed = False
        if not any(
            item["entity_type"] == "plan" and item["field"] == "finish_time"
            for item in review.items
        ):
            _added_item(review, "plan", "finish-time", "finish_time")
        for item in review.items:
            if item["entity_type"] == "plan" and item["field"] == "finish_time":
                item.update(status="added", source_line=None)
        review.answers[question["id"]] = "Finish time supplied"
    elif kind == "missing_assignment":
        route = next(route for route in review.plan.routes if route.id == question["entity_id"])
        field = question["field"]
        if field == "vehicle_id":
            if not isinstance(value, str) or value not in {
                vehicle.id for vehicle in review.plan.vehicles
            }:
                raise HTTPException(422, f"Unknown vehicle id {value!r}")
        else:
            value = TypeAdapter(list[str]).validate_python(value, strict=True)
            people = {
                person.id
                for person in review.plan.people
                if field == "loader_ids" or person.can_drive
            }
            if (
                not value
                or len(value) != len(set(value))
                or any(pid not in people for pid in value)
            ):
                raise HTTPException(422, f"Choose existing eligible people for {field}: {value!r}")
        setattr(route, field, value)
        _added_item(review, "route", route.id, field)
        review.answers[question["id"]] = "Assignment supplied"
    review.plan.fingerprint = None
    review.confirmed, review.out_of_date = False, True
    for item in review.items:
        if (
            invalidate_routes
            and item["entity_type"] == "route"
            and item["status"] in {"confirmed", "corrected"}
        ):
            item["status"] = "stale"
