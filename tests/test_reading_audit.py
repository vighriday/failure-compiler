"""The fixture guard must not silently rename entities or invent missing records."""

from scripts.record_example_reading import correction_audit
from tests.validation_helpers import confirmed_truth_map


def test_audit_accepts_only_supported_corrections():
    plan = confirmed_truth_map()
    plan.people[0].available_from = 0
    plan.routes[0].households = 20
    plan.routes[0].loader_ids = ["person-ravi"]
    plan.problem_sizes["vehicle_returns_late"] = 45
    audit = correction_audit(plan)
    assert audit["correctable"] is True
    assert len(audit["scripted_corrections"]) == 4


def test_audit_stops_for_missing_delivery_or_entity_renaming():
    plan = confirmed_truth_map()
    plan.deliveries = []
    plan.routes[0].name = "Route A"
    plan.vehicles[0].name = "van"
    audit = correction_audit(plan)
    assert audit["correctable"] is False
    assert any(
        item["collection"] == "deliveries" and item["reason"] == "Missing entity"
        for item in audit["uneditable"]
    )
    assert any(
        item.get("field") == "name" and item["id"] == "vehicle-van" for item in audit["uneditable"]
    )
