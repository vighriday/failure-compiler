"""Fact evidence and entity mentions never silently substitute for each other."""

import json

from server.facts import source_tags
from server.reading import items_for_plan, plan_from_record
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.models import AIPlanReading
from tests.validation_helpers import ROOT


def saved_plan():
    return plan_from_record(
        json.loads((ROOT / "fixtures/example-reading.json").read_text(encoding="utf-8"))
    )


def test_legacy_capture_is_labelled_as_an_entity_mention_without_fabricated_sources():
    plan = saved_plan()
    for person in plan.people:
        person.fact_sources = {}
    item = next(row for row in items_for_plan(plan) if row["id"] == "ravi-driver")
    assert source_tags(plan, item) == [{"label": "Ravi", "source_line": "L8", "kind": "mention"}]
    assert not any(person.fact_sources.get("can_drive") for person in plan.people)


def test_own_fact_lines_are_distinct_and_nullable_facts_use_mentioned_on():
    plan = saved_plan()
    person = next(person for person in plan.people if person.name == "Ravi")
    person.fact_sources = {"available_from": None, "available_until": "L15", "can_drive": "L16"}
    items = items_for_plan(plan)
    driver = next(row for row in items if row["id"] == "ravi-driver")
    availability = next(row for row in items if row["id"] == "ravi-availability")
    assert source_tags(plan, driver) == [
        {"label": "Can drive", "source_line": "L16", "kind": "fact"}
    ]
    assert source_tags(plan, availability) == [
        {"label": "Available until", "source_line": "L15", "kind": "fact"},
        {"label": "Ravi", "source_line": "L8", "kind": "mention"},
    ]
    availability["status"] = "added"
    assert source_tags(plan, availability) == []


def test_sources_do_not_change_checker_inputs_or_fingerprint():
    plan = saved_plan()
    original = plan.checker_data()
    before = fingerprint_plan_map(plan)
    plan.people[0].fact_sources = {"can_drive": "L16"}
    assert plan.checker_data() == original
    assert fingerprint_plan_map(plan) == before


def test_reviewed_example_uses_the_actual_fact_lines():
    plan = saved_plan()
    people = {person.name: person for person in plan.people}
    assert people["Joel"].fact_sources["can_drive"] == "L16"
    assert people["Ravi"].fact_sources["available_until"] == "L15"
    bay = next(place for place in plan.places if place.name == "Loading bay")
    assert bay.fact_sources["one_vehicle_at_a_time"] == "L12"
    for route in plan.routes:
        assert route.fact_sources["loader_ids"] == "L13"
        assert route.fact_sources["load_minutes"] == "L12"


def test_new_schema_requires_closed_nullable_source_objects_for_groq():
    schema = AIPlanReading.model_json_schema()
    for name in ("AIPerson", "AIVehicle", "AIPlace", "AIDelivery", "AIRoute"):
        definition = schema["$defs"][name]
        assert "fact_sources" in definition["required"]
    for name in (
        "PersonSources",
        "VehicleSources",
        "PlaceSources",
        "DeliverySources",
        "RouteSources",
    ):
        definition = schema["$defs"][name]
        assert set(definition["required"]) == set(definition["properties"])
        assert definition["additionalProperties"] is False
        for prop in definition["properties"].values():
            assert {item["type"] for item in prop["anyOf"]} == {"string", "null"}
