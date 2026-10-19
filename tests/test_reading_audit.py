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


def test_audit_uses_rule_addition_and_ignores_entity_labels():
    plan = confirmed_truth_map()
    plan.deliveries = []
    plan.routes[0].name = "Route A"
    plan.vehicles[0].name = "van"
    audit = correction_audit(plan)
    assert audit["correctable"] is True
    assert audit["after"]["checker_matches"] == 100
    assert audit["naming_only"]
    assert audit["scripted_corrections"][0]["value"]["choice"] == "Add a delivery"


def test_audit_stops_for_an_extra_entity_without_a_removal_control():
    plan = confirmed_truth_map()
    plan.vehicles.append(
        plan.vehicles[0].model_copy(update={"id": "vehicle-extra", "name": "Extra"})
    )
    audit = correction_audit(plan)
    assert audit["correctable"] is False
    assert audit["not_fixable"]


def test_extra_hall_cannot_be_silently_dropped_despite_matching_reference_results():
    plan = confirmed_truth_map()
    plan.places.append(
        plan.places[0].model_copy(
            update={
                "id": "place-hall",
                "name": "Hall",
                "needs_key": False,
                "one_vehicle_at_a_time": False,
            }
        )
    )
    plan.routes[0].loader_ids = ["person-ravi", "person-joel", "person-anita", "person-maya"]
    audit = correction_audit(plan)
    assert audit["correctable"] is False
    assert audit["after"]["checker_matches"] == 100
    assert audit["after"]["aligned_field_match_percent"] < 100
    assert audit["actual_scenario_count"] == 115
    assert not audit[
        "fixed_by_control"
    ]  # Reordering the same eligible loaders is not a correction.
    assert len(audit["corrected_plan"]["places"]) == 2


def test_explicit_place_identity_answer_reaches_all_inputs_and_actual_100_scenarios():
    plan = confirmed_truth_map()
    plan.places.append(
        plan.places[0].model_copy(
            update={
                "id": "place-extra",
                "name": "Hall",
                "needs_key": False,
                "one_vehicle_at_a_time": False,
            }
        )
    )
    audit = correction_audit(plan, place_aliases={"place-extra": "place-loading-area"})
    assert audit["correctable"]
    assert audit["after"]["aligned_field_match_percent"] == 100
    assert audit["after"]["checker_matches"] == audit["actual_scenario_count"] == 100
    assert len(plan.places) == 2  # Original reading stays untouched.
    assert audit["actions"][0]["question_id"] == "rule-place-extra-identity"


def test_audit_never_scripts_loader_reordering_as_a_correction():
    plan = confirmed_truth_map()
    for route in plan.routes:
        route.loader_ids.reverse()
    audit = correction_audit(plan)
    assert audit["correctable"]
    assert audit["scripted_corrections"] == []
    assert audit["after"]["checker_matches"] == 100
