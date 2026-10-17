"""Build review rows from the raw AI map; display labels and provenance stay intact."""

from server.validation.gate import plan_map_from_reading, validate_ai_reading
from server.validation.models import PlanMap


def items_for_plan(plan: PlanMap) -> list[dict]:
    rows = []

    def add(item_id, group, kind, entity, field, guessed=None):
        guessed = entity.guessed if guessed is None else guessed
        rows.append(
            {
                "id": item_id,
                "group": group,
                "entity_type": kind,
                "entity_id": entity.id,
                "field": field,
                "source_line": entity.source_line or None,
                "guessed": guessed,
                "status": "guessed" if guessed else "unconfirmed",
            }
        )

    for person in plan.people:
        slug = person.id.removeprefix("person-")
        add(f"{slug}-availability", "People", "person", person, "available_until")
        add(f"{slug}-driver", "People", "person", person, "can_drive", person.can_drive_guessed)
        add(f"{slug}-key", "People", "person", person, "holds_key")
    for vehicle in plan.vehicles:
        add(vehicle.id.removeprefix("vehicle-"), "Vehicles", "vehicle", vehicle, "available_from")
    for place in plan.places:
        add(place.id, "Vehicles", "place", place, "place")
        add(f"{place.id}-loading", "Vehicles", "place", place, "one_vehicle_at_a_time")
    for route in plan.routes:
        add(route.id, "Routes", "route", route, "route")
        add(f"{route.id}-loading", "Routes", "route", route, "load_minutes")
        add(f"{route.id}-driving", "Routes", "route", route, "drive_minutes")
    for delivery in plan.deliveries:
        add(delivery.id, "Times", "delivery", delivery, "arrives_at")
    rows.append(
        {
            "id": "finish-time",
            "group": "Times",
            "entity_type": "plan",
            "entity_id": "finish-time",
            "field": "finish_time",
            "source_line": plan.finish_time_source or None,
            "guessed": plan.finish_time_guessed,
            "status": "guessed" if plan.finish_time_guessed else "unconfirmed",
        }
    )
    return rows


def questions_for_plan(plan: PlanMap, items: list[dict]) -> list[dict]:
    questions = []
    for index, question in enumerate(plan.questions, 1):
        item = next(item for item in items if item["entity_id"] == question.item_id)
        questions.append(
            {
                "id": f"reading-question-{index}",
                "item_id": item["id"],
                "question_text": question.question_text,
                "source_line": item["source_line"],
                "choices": ["Use the reviewed details"],
            }
        )
    return questions


def plan_from_record(record: dict) -> PlanMap:
    reading = validate_ai_reading(record["raw_text"])
    return plan_map_from_reading(
        reading, provider=record["provider"], model=record["model"], timestamp=record["timestamp"]
    )
