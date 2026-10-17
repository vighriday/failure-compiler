"""Strict AI-output parsing, reference checks, and stable ID normalisation."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from server.validation.models import (
    AIMetadata,
    AIPlanReading,
    MapDelivery,
    MapPerson,
    MapPlace,
    MapQuestion,
    MapRoute,
    MapVehicle,
    PlanMap,
)


class GateError(ValueError):
    """An input error with the field and offending value preserved."""

    def __init__(self, message: str, *, field: str, bad_value: Any = None) -> None:
        super().__init__(message)
        self.field = field
        self.bad_value = bad_value


def _read_json(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise GateError(f"Invalid JSON: {exc}", field="$", bad_value=raw) from exc
    if not isinstance(value, dict):
        raise GateError("The reading must be a JSON object", field="$", bad_value=value)
    return value


def _validate_shape(payload: dict[str, Any]) -> AIPlanReading:
    try:
        return AIPlanReading.model_validate(payload)
    except ValidationError as exc:
        issue = exc.errors(include_url=False)[0]
        field = ".".join(str(part) for part in issue["loc"])
        bad_value = issue.get("input")
        if issue["type"] == "missing":
            raise GateError(
                f"Missing required field '{field}'", field=field, bad_value="<missing>"
            ) from exc
        raise GateError(
            f"Invalid value {bad_value!r} for field '{field}': {issue['msg']}",
            field=field,
            bad_value=bad_value,
        ) from exc


def _entity_groups(reading: AIPlanReading) -> list[tuple[str, list[Any]]]:
    return [
        ("person", reading.people),
        ("vehicle", reading.vehicles),
        ("place", reading.places),
        ("delivery", reading.deliveries),
        ("route", reading.routes),
    ]


def _check_ids_and_references(reading: AIPlanReading) -> None:
    ids_by_kind: dict[str, set[str]] = {}
    ids_seen: set[str] = set()
    for kind, entities in _entity_groups(reading):
        ids_by_kind[kind] = set()
        for entity in entities:
            if entity.id in ids_seen:
                raise GateError(
                    f"Duplicate id '{entity.id}'", field=f"{kind}s.id", bad_value=entity.id
                )
            ids_seen.add(entity.id)
            ids_by_kind[kind].add(entity.id)

    for route in reading.routes:
        for person_id in route.driver_ids:
            if person_id not in ids_by_kind["person"]:
                raise GateError(
                    f"Unknown person id '{person_id}' in {route.id} driver_ids",
                    field=f"{route.id}.driver_ids",
                    bad_value=person_id,
                )
        for person_id in route.loader_ids:
            if person_id not in ids_by_kind["person"]:
                raise GateError(
                    f"Unknown person id '{person_id}' in {route.id} loader_ids",
                    field=f"{route.id}.loader_ids",
                    bad_value=person_id,
                )
        if route.vehicle_id not in ids_by_kind["vehicle"]:
            raise GateError(
                f"Unknown vehicle id '{route.vehicle_id}' in {route.id} vehicle_id",
                field=f"{route.id}.vehicle_id",
                bad_value=route.vehicle_id,
            )

    for delivery in reading.deliveries:
        if delivery.place_id not in ids_by_kind["place"]:
            raise GateError(
                f"Unknown place id '{delivery.place_id}' in {delivery.id} place_id",
                field=f"{delivery.id}.place_id",
                bad_value=delivery.place_id,
            )

    for question in reading.questions:
        if question.item_id not in ids_seen:
            raise GateError(
                f"Unknown item id '{question.item_id}' in questions item_id",
                field="questions.item_id",
                bad_value=question.item_id,
            )


def _slug(kind: str, name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    while value.startswith(kind + "-"):
        value = value[len(kind) + 1 :]
    if not value:
        raise GateError(
            f"Cannot normalise an empty {kind} name", field=f"{kind}.name", bad_value=name
        )
    return f"{kind}-{value}"


def normalise_reading_ids(reading: AIPlanReading) -> AIPlanReading:
    """Replace AI IDs with type-and-name slugs and update every reference."""
    id_map: dict[str, str] = {}
    normalized_seen: set[str] = set()
    for kind, entities in _entity_groups(reading):
        for entity in entities:
            stable_id = _slug(kind, entity.name)
            if stable_id in normalized_seen:
                raise GateError(
                    f"Duplicate normalised id '{stable_id}'",
                    field=f"{kind}s.name",
                    bad_value=entity.name,
                )
            normalized_seen.add(stable_id)
            id_map[entity.id] = stable_id

    return reading.model_copy(
        update={
            "people": [
                person.model_copy(update={"id": id_map[person.id]}) for person in reading.people
            ],
            "vehicles": [
                vehicle.model_copy(update={"id": id_map[vehicle.id]})
                for vehicle in reading.vehicles
            ],
            "places": [
                place.model_copy(update={"id": id_map[place.id]}) for place in reading.places
            ],
            "deliveries": [
                delivery.model_copy(
                    update={"id": id_map[delivery.id], "place_id": id_map[delivery.place_id]}
                )
                for delivery in reading.deliveries
            ],
            "routes": [
                route.model_copy(
                    update={
                        "id": id_map[route.id],
                        "vehicle_id": id_map[route.vehicle_id],
                        "driver_ids": [id_map[item_id] for item_id in route.driver_ids],
                        "loader_ids": [id_map[item_id] for item_id in route.loader_ids],
                    }
                )
                for route in reading.routes
            ],
            "questions": [
                question.model_copy(update={"item_id": id_map[question.item_id]})
                for question in reading.questions
            ],
        }
    )


def validate_ai_reading(raw: str | bytes | dict[str, Any]) -> AIPlanReading:
    """Parse strict output, check references, then normalise all entity IDs."""
    reading = _validate_shape(_read_json(raw))
    _check_ids_and_references(reading)
    return normalise_reading_ids(reading)


def normalise_plan_map_ids(plan: PlanMap) -> PlanMap:
    """Normalise a server map and all references, preserving metadata and statuses."""
    all_entities: list[tuple[str, list[Any]]] = [
        ("person", plan.people),
        ("vehicle", plan.vehicles),
        ("place", plan.places),
        ("delivery", plan.deliveries),
        ("route", plan.routes),
    ]
    raw_ids: set[str] = set()
    id_map: dict[str, str] = {}
    stable_ids: set[str] = set()
    for kind, entities in all_entities:
        for entity in entities:
            if entity.id in raw_ids:
                raise GateError(
                    f"Duplicate id '{entity.id}'", field=f"{kind}s.id", bad_value=entity.id
                )
            raw_ids.add(entity.id)
            # Existing typed IDs are identities. A later label edit must never rename them.
            stable_id = (
                _slug(kind, entity.id[len(kind) + 1 :])
                if entity.id.startswith(kind + "-")
                else _slug(kind, entity.name)
            )
            if stable_id in stable_ids:
                raise GateError(
                    f"Duplicate normalised id '{stable_id}'",
                    field=f"{kind}s.name",
                    bad_value=entity.name,
                )
            stable_ids.add(stable_id)
            id_map[entity.id] = stable_id

    people = {item.id for item in plan.people}
    vehicles = {item.id for item in plan.vehicles}
    places = {item.id for item in plan.places}
    all_ids = raw_ids
    for route in plan.routes:
        for person_id in route.driver_ids:
            if person_id not in people:
                raise GateError(
                    f"Unknown person id '{person_id}' in {route.id} driver_ids",
                    field=f"{route.id}.driver_ids",
                    bad_value=person_id,
                )
        for person_id in route.loader_ids:
            if person_id not in people:
                raise GateError(
                    f"Unknown person id '{person_id}' in {route.id} loader_ids",
                    field=f"{route.id}.loader_ids",
                    bad_value=person_id,
                )
        if route.vehicle_id not in vehicles:
            raise GateError(
                f"Unknown vehicle id '{route.vehicle_id}' in {route.id} vehicle_id",
                field=f"{route.id}.vehicle_id",
                bad_value=route.vehicle_id,
            )
    for delivery in plan.deliveries:
        if delivery.place_id not in places:
            raise GateError(
                f"Unknown place id '{delivery.place_id}' in {delivery.id} place_id",
                field=f"{delivery.id}.place_id",
                bad_value=delivery.place_id,
            )
    for question in plan.questions:
        if question.item_id not in all_ids:
            raise GateError(
                f"Unknown item id '{question.item_id}' in questions item_id",
                field="questions.item_id",
                bad_value=question.item_id,
            )

    return plan.model_copy(
        update={
            "people": [item.model_copy(update={"id": id_map[item.id]}) for item in plan.people],
            "vehicles": [item.model_copy(update={"id": id_map[item.id]}) for item in plan.vehicles],
            "places": [item.model_copy(update={"id": id_map[item.id]}) for item in plan.places],
            "deliveries": [
                item.model_copy(update={"id": id_map[item.id], "place_id": id_map[item.place_id]})
                for item in plan.deliveries
            ],
            "routes": [
                item.model_copy(
                    update={
                        "id": id_map[item.id],
                        "vehicle_id": id_map[item.vehicle_id],
                        "driver_ids": [id_map[person_id] for person_id in item.driver_ids],
                        "loader_ids": [id_map[person_id] for person_id in item.loader_ids],
                    }
                )
                for item in plan.routes
            ],
            "questions": [
                item.model_copy(update={"item_id": id_map[item.item_id]}) for item in plan.questions
            ],
            "fingerprint": None,
        }
    )


def plan_map_from_reading(
    reading: AIPlanReading, *, provider: str, model: str, timestamp: str
) -> PlanMap:
    """Wrap a validated reading with server-owned status and provider metadata."""
    ai_meta = AIMetadata(provider=provider, model=model, timestamp=timestamp)
    return PlanMap(
        ai_meta=ai_meta,
        people=[MapPerson(**item.model_dump(), status="unconfirmed") for item in reading.people],
        vehicles=[
            MapVehicle(**item.model_dump(), status="unconfirmed") for item in reading.vehicles
        ],
        places=[MapPlace(**item.model_dump(), status="unconfirmed") for item in reading.places],
        deliveries=[
            MapDelivery(**item.model_dump(), status="unconfirmed") for item in reading.deliveries
        ],
        routes=[MapRoute(**item.model_dump(), status="unconfirmed") for item in reading.routes],
        finish_time=reading.finish_time,
        finish_time_source=reading.finish_time_source,
        finish_time_guessed=reading.finish_time_guessed,
        problem_sizes=reading.problem_sizes.model_dump(),
        questions=[MapQuestion(**item.model_dump()) for item in reading.questions],
    )
