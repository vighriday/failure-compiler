"""Scenario generator: produces singles and pairs from a problem list."""

from __future__ import annotations

from itertools import combinations

from server.config import PROBLEM_TYPES
from server.models import PlanMapData


def _instantiate_problems(plan: PlanMapData) -> list[dict]:
    """Return a list of concrete problem dicts, one per entity per type.

    Each dict has:
        id:       unique problem id, e.g. "volunteer_absent__person-joel"
        type_id:  problem type id from config
        entity_id: the entity this problem targets
        entity_type: "person" | "vehicle" | "delivery" | "place"
        size:     minutes (from plan.problem_sizes or default), or None for absent
        label:    human-readable label
    """
    entity_lists: dict[str, list] = {
        "person": plan.people,
        "vehicle": plan.vehicles,
        "delivery": plan.deliveries,
        "place": plan.places,
    }

    problems: list[dict] = []
    for pt in PROBLEM_TYPES:
        applies_to = pt["applies_to"]
        entities = entity_lists.get(applies_to, [])
        for entity in entities:
            pid = f"{pt['id']}__{entity.id}"
            if pt["has_size"]:
                size = plan.problem_sizes.get(pt["id"], pt.get("default_size", 30))
            else:
                size = None
            label = pt["label"].format(name=entity.name, size=size)
            problems.append({
                "id": pid,
                "type_id": pt["id"],
                "entity_id": entity.id,
                "entity_type": applies_to,
                "size": size,
                "label": label,
            })
    return problems


def generate_scenarios(
    plan: PlanMapData,
) -> tuple[list[dict], list[dict]]:
    """Generate all single and pair scenarios.

    Returns (singles, pairs) where each scenario is a dict with:
        scenario_id:  str
        failures:     list of problem ids (1 or 2)
        labels:       list of human-readable labels
    """
    problems = _instantiate_problems(plan)

    singles = []
    for p in problems:
        singles.append({
            "scenario_id": p["id"],
            "failures": [p["id"]],
            "labels": [p["label"]],
        })

    pairs = []
    for a, b in combinations(problems, 2):
        scenario_id = f"{a['id']}+{b['id']}"
        pairs.append({
            "scenario_id": scenario_id,
            "failures": [a["id"], b["id"]],
            "labels": [a["label"], b["label"]],
        })

    return singles, pairs
