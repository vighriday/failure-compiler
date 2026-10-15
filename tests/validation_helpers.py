"""Factories for validation tests based on the checker truth map."""

from __future__ import annotations

import json
from pathlib import Path

from server.models import PlanMapData
from server.validation.models import AIPlanReading, PlanMap

ROOT = Path(__file__).resolve().parents[1]


def truth_data() -> PlanMapData:
    return PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())


def confirmed_truth_map() -> PlanMap:
    return PlanMap.from_truth_map(truth_data())


def ai_reading_payload() -> dict:
    truth = json.loads((ROOT / "fixtures/example-truth.json").read_text())
    for kind in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in truth[kind]:
            entity["source_line"] = f"Example plan: {entity['name']}"
            entity["guessed"] = False
    for person in truth["people"]:
        person["can_drive_guessed"] = False
    truth.update(
        {
            "finish_time_source": "Everything delivered by noon.",
            "finish_time_guessed": False,
            "questions": [],
            "is_distribution_plan": True,
            "not_distribution_reason": None,
        }
    )
    return truth


def ai_reading() -> AIPlanReading:
    from server.validation.gate import validate_ai_reading

    return validate_ai_reading(ai_reading_payload())
