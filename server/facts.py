"""Sentences and constrained editors derived from the current checker inputs."""

import re
from typing import Any

from server.labels import route_label
from server.validation.models import PlanMap

COLLECTIONS = {
    "person": "people",
    "vehicle": "vehicles",
    "place": "places",
    "delivery": "deliveries",
    "route": "routes",
}
FIELDS = {
    "person": ["available_from", "available_until", "can_drive", "holds_key"],
    "vehicle": ["available_from"],
    "place": ["opens_at", "needs_key", "one_vehicle_at_a_time"],
    "delivery": ["arrives_at", "place_id"],
    "route": [
        "driver_ids",
        "loader_ids",
        "vehicle_id",
        "households",
        "load_minutes",
        "drive_minutes",
    ],
    "plan": ["finish_time"],
}
LABELS = {
    "available_from": "Available from",
    "available_until": "Available until",
    "can_drive": "Can drive",
    "holds_key": "Holds a key",
    "opens_at": "Opens at",
    "needs_key": "Needs a key",
    "one_vehicle_at_a_time": "One vehicle at a time",
    "arrives_at": "Delivery arrives at",
    "place_id": "Place",
    "driver_ids": "Drivers (primary first)",
    "loader_ids": "Loaders",
    "vehicle_id": "Vehicle",
    "households": "Households",
    "load_minutes": "Loading minutes",
    "drive_minutes": "Driving minutes",
    "finish_time": "Finish time",
    "loading_team": "Loading team",
}


def entity_for(plan: PlanMap, item: dict) -> Any:
    if item["entity_type"] == "plan":
        return plan
    return next(
        entity
        for entity in getattr(plan, COLLECTIONS[item["entity_type"]])
        if entity.id == item["entity_id"]
    )


def names(plan: PlanMap, ids: list[str]) -> str:
    labels = [
        next((person.name for person in plan.people if person.id == item), item) for item in ids
    ]
    return (
        ", ".join(labels[:-1]) + " and " + labels[-1]
        if len(labels) > 1
        else (labels[0] if labels else "Nobody")
    )


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def source_tags(plan: PlanMap, item: dict) -> list[dict]:
    """Keep fact evidence separate from an entity's mention, including legacy captures."""
    if item.get("status") == "added":
        return []
    if item["entity_type"] == "plan":
        line = plan.finish_time_source
        return (
            [{"label": "Finish time", "source_line": line, "kind": "fact"}]
            if line and re.fullmatch(r"L[1-9][0-9]*", line)
            else []
        )
    entity = entity_for(plan, item)
    fields = {
        "available_until": ["available_from", "available_until"],
        "place": ["opens_at", "needs_key"],
        "route": ["households", "vehicle_id", "driver_ids", "loader_ids"],
        "loading": ["load_minutes", "loader_ids"],
    }.get(item["field"], [item["field"]])
    tags, missing = [], False
    for field in fields:
        line = entity.fact_sources.get(field)
        if line:
            tags.append({"label": LABELS.get(field, field), "source_line": line, "kind": "fact"})
        else:
            missing = True
    if missing and re.fullmatch(r"L[1-9][0-9]*", entity.source_line or ""):
        tags.append({"label": entity.name, "source_line": entity.source_line, "kind": "mention"})
    return tags


def loading_team(plan: PlanMap) -> list[str]:
    """Shared route loaders; route-specific loaders remain separate assignments."""
    if not plan.routes:
        return []
    return [
        person_id
        for person_id in plan.routes[0].loader_ids
        if all(person_id in route.loader_ids for route in plan.routes)
    ]


def statement(plan: PlanMap, item: dict) -> str:
    entity = entity_for(plan, item)
    field, kind = item["field"], item["entity_type"]
    if field == "loading_team":
        return f"{names(plan, loading_team(plan))} make up the shared loading team."
    if kind == "person":
        if field == "holds_key":
            if item.get("id") not in {None, "joel-key"}:
                return f"{entity.name} " + (
                    "holds a loading-area key."
                    if entity.holds_key
                    else "does not hold a loading-area key."
                )
            holders = [person.id for person in plan.people if person.holds_key]
            return f"{names(plan, holders)} " + (
                "holds the only loading-area key."
                if len(holders) == 1
                else "hold loading-area keys."
            )
        if field == "can_drive":
            return f"{entity.name} {'can' if entity.can_drive else 'cannot'} drive."
        if field == "loading":
            routes = [route.name for route in plan.routes if entity.id in route.loader_ids]
            return f"{entity.name} " + (
                f"can load Routes {', '.join(routes)}." if routes else "is not on the loading team."
            )
        return (
            f"{entity.name} is available from {clock(entity.available_from)} "
            f"until {clock(entity.available_until)}."
        )
    if kind == "route":
        if field in {"load_minutes", "drive_minutes"}:
            task = "loading" if field == "load_minutes" else "drive"
            return f"{route_label(entity.name)}'s {task} takes {getattr(entity, field)} minutes."
        if field == "loading":
            return (
                f"{route_label(entity.name)} takes {entity.load_minutes} minutes to load; "
                f"Loaders: {names(plan, entity.loader_ids)}."
            )
        vehicle = next(
            (v.name for v in plan.vehicles if v.id == entity.vehicle_id), entity.vehicle_id
        )
        if vehicle.casefold() in {"car", "van", "truck", "bike", "bicycle"}:
            vehicle = vehicle.lower()
        drivers = entity.driver_ids
        return (
            f"{route_label(entity.name)} serves {entity.households} households by {vehicle}; "
            f"{names(plan, drivers[:1])} drives"
            + (f", with {names(plan, drivers[1:])} as backups" if len(drivers) > 1 else "")
            + f". Loaders: {names(plan, entity.loader_ids)}."
        )
    if kind == "vehicle":
        return f"{entity.name} is available from {clock(entity.available_from)}."
    if kind == "place":
        if field == "one_vehicle_at_a_time":
            return (
                "Only one vehicle can load at a time."
                if entity.one_vehicle_at_a_time
                else "Vehicles can load together."
            )
        return (
            f"{entity.name} opens at {clock(entity.opens_at)} and "
            f"{'needs' if entity.needs_key else 'does not need'} a key."
        )
    if kind == "delivery":
        return f"{entity.name} arrives at {clock(entity.arrives_at)}."
    return f"Everything must be delivered by {clock(plan.finish_time)}."


def controls(plan: PlanMap, item: dict) -> list[dict]:
    entity = entity_for(plan, item)
    fields = ["loading_team"] if item["field"] == "loading_team" else FIELDS[item["entity_type"]]
    result = []
    for field in fields:
        value = loading_team(plan) if field == "loading_team" else getattr(entity, field)
        control = {"field": field, "label": LABELS[field], "value": value}
        if field in {"driver_ids", "loader_ids", "loading_team"}:
            control.update(
                type="ordered_people",
                options=[{"value": person.id, "label": person.name} for person in plan.people],
            )
        elif field in {"vehicle_id", "place_id"}:
            control.update(
                type="select",
                options=[
                    {"value": entity.id, "label": entity.name}
                    for entity in (plan.vehicles if field == "vehicle_id" else plan.places)
                ],
            )
        elif isinstance(value, bool):
            control.update(type="boolean")
        elif field in {"load_minutes", "drive_minutes", "households"}:
            control.update(
                type="number",
                min=1 if field == "households" else 5,
                max=500 if field == "households" else 240,
                step=1 if field == "households" else 5,
            )
        else:
            control.update(type="time")
        result.append(control)
    return result


def changed_by(plan: PlanMap, item: dict) -> int | None:
    """Tag only facts a fix actually changed, rather than every row of its entity."""
    field = item["field"]
    for number, fix in reversed(list(enumerate(plan.fix_history, 1))):
        for operation in fix.operations:
            if field == "holds_key" and item.get("id") in {None, "joel-key"}:
                if operation.op == "give_spare_key":
                    return number
            elif field in {"loading", "loading_team"}:
                if operation.field == "loader_ids":
                    return number
            elif operation.target_id == item["entity_id"]:
                fields = {field}
                if field == "route":
                    fields = {"driver_ids", "loader_ids", "vehicle_id", "households"}
                elif field == "available_until":
                    fields = {"available_from", "available_until"}
                if operation.field in fields:
                    return number
    return None
