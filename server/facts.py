"""Sentences and constrained editors derived from the current checker inputs."""

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
    "loader_ids": "Loaders (primary first)",
    "vehicle_id": "Vehicle",
    "households": "Households",
    "load_minutes": "Loading minutes",
    "drive_minutes": "Driving minutes",
    "finish_time": "Finish time",
    "loading_team": "Loading team (primary first)",
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
                f"loading cover: {names(plan, entity.loader_ids)}."
            )
        vehicle = next(
            (v.name for v in plan.vehicles if v.id == entity.vehicle_id), entity.vehicle_id
        )
        drivers = entity.driver_ids
        return (
            f"{route_label(entity.name)} serves {entity.households} households by {vehicle}; "
            f"{names(plan, drivers[:1])} drives"
            + (f", with {names(plan, drivers[1:])} as backups" if len(drivers) > 1 else "")
            + f". Loading cover: {names(plan, entity.loader_ids)}."
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
    if item["field"] == "holds_key":
        return max((person.changed_by_fix or 0 for person in plan.people), default=0) or None
    if item["field"] in {"loading", "loading_team"}:
        return max((route.changed_by_fix or 0 for route in plan.routes), default=0) or None
    return getattr(entity_for(plan, item), "changed_by_fix", None)
