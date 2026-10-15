"""Stable SHA-256 fingerprints over checker inputs only."""

from __future__ import annotations

import hashlib
import json

from server.models import PlanMapData
from server.validation.gate import normalise_plan_map_ids
from server.validation.models import PlanMap


def fingerprint_plan_map(plan: PlanMap | PlanMapData) -> str:
    """Hash canonical checker inputs, excluding UI and AI-owned metadata."""
    if isinstance(plan, PlanMapData):
        plan = PlanMap.from_truth_map(plan)
    data = normalise_plan_map_ids(plan).checker_data()
    payload = data.model_dump(mode="json")
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        payload[collection] = sorted(payload[collection], key=lambda item: item["id"])
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
