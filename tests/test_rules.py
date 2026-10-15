"""Plain rules and correction cascades for confirmed maps."""

from server.validation.rules import set_person_can_drive, validate_plan_rules
from tests.validation_helpers import confirmed_truth_map


def test_truth_map_passes_plain_rules() -> None:
    assert validate_plan_rules(confirmed_truth_map()) == []


def test_ravi_driver_correction_clears_dependent_confirmations_and_names_ravi() -> None:
    plan = confirmed_truth_map()
    affected_before = {route.id for route in plan.routes if "person-ravi" in route.driver_ids}
    assert affected_before == {"route-a", "route-b", "route-c"}

    corrected, issues = set_person_can_drive(plan, "person-ravi", False)
    statuses = {route.id: route.status for route in corrected.routes}

    assert all(statuses[route_id] == "unconfirmed" for route_id in affected_before)
    assert all(
        route.status == "confirmed" for route in corrected.routes if route.id not in affected_before
    )
    assert corrected.people[0].can_drive is False
    assert corrected.people[0].status == "corrected"
    assert len(issues) == 3
    assert all("Ravi" in issue.message for issue in issues)


def test_missing_route_driver_is_a_named_rule_violation() -> None:
    plan = confirmed_truth_map()
    route = plan.routes[0].model_copy(update={"driver_ids": []})
    broken = plan.model_copy(update={"routes": [route, *plan.routes[1:]]})
    issues = validate_plan_rules(broken)
    assert any(
        issue.field == "driver_ids" and "needs at least one driver" in issue.message
        for issue in issues
    )


def test_non_driving_backup_is_a_rule_violation() -> None:
    plan = confirmed_truth_map()
    ravi = plan.people[0].model_copy(update={"can_drive": False})
    broken = plan.model_copy(update={"people": [ravi, *plan.people[1:]]})
    issues = validate_plan_rules(broken)
    assert any(
        "Ravi cannot drive" in issue.message and "route-a" in issue.message for issue in issues
    )


def test_problem_cap_is_enforced() -> None:
    plan = confirmed_truth_map()
    extra_people = [
        *plan.people,
        *[
            plan.people[0].model_copy(update={"id": f"person-extra-{i}", "name": f"Extra {i}"})
            for i in range(20)
        ],
    ]
    oversized = plan.model_copy(update={"people": extra_people})
    issues = validate_plan_rules(oversized)
    assert any("supports up to 24 problems" in issue.message for issue in issues)
