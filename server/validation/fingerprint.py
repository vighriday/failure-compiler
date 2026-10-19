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
    # Single-location/delivery roles have equivalent identities across independent readings.
    role_ids = {
        item["id"]: f"{collection}-{index}"
        for collection in ("places", "deliveries")
        for index, item in enumerate(sorted(payload[collection], key=lambda item: item["id"]))
    }
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for item in payload[collection]:
            item.pop("name")
            item["id"] = role_ids.get(item["id"], item["id"])
            if "loader_ids" in item:
                item["loader_ids"] = sorted(set(item["loader_ids"]))
            if "place_id" in item:
                item["place_id"] = role_ids.get(item["place_id"], item["place_id"])
        payload[collection] = sorted(payload[collection], key=lambda item: item["id"])
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
