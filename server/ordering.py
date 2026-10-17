"""Stable checker traversal, preserving the example's published grid order."""

from typing import TypeVar

from server.models import PlanMapData
from server.validation.models import PlanMap

Plan = TypeVar("Plan", PlanMapData, PlanMap)
EXAMPLE_ORDER = {
    "people": ["person-ravi", "person-joel", "person-anita", "person-maya", "person-sam"],
    "vehicles": ["vehicle-van", "vehicle-car"],
    "places": ["place-loading-area"],
    "deliveries": ["delivery-supply-truck"],
    "routes": ["route-a", "route-b", "route-c"],
}


def canonical_order(plan: Plan) -> Plan:
    """Sort entity sets only. Ordered primary/backup assignments stay meaningful."""
    collections = {}
    for field, example_ids in EXAMPLE_ORDER.items():
        ranks = {entity_id: index for index, entity_id in enumerate(example_ids)}
        collections[field] = sorted(
            getattr(plan, field), key=lambda entity: (ranks.get(entity.id, len(ranks)), entity.id)
        )
    return plan.model_copy(update=collections)
