"""Run all single and pair failures for a confirmed plan."""

from __future__ import annotations

from collections.abc import Iterator

from server.checker.scenarios import _instantiate_problems, generate_scenarios
from server.models import PlanMapData, ScenarioResult
from server.ordering import canonical_order


def run_checker(plan: PlanMapData) -> list[ScenarioResult]:
    """Run singles first, then solve only pairs not already broken by a single."""
    return list(iter_checker(plan))


def iter_checker(plan: PlanMapData) -> Iterator[ScenarioResult]:
    """Yield results in deterministic singles-then-pairs order.

    Singles must be solved first so pairs containing a broken single can be
    marked dim without sending a redundant model to CP-SAT.
    """
    plan = canonical_order(plan)
    problems = {problem["id"]: problem for problem in _instantiate_problems(plan)}
    singles, pairs = generate_scenarios(plan)
    single_results: dict[str, ScenarioResult] = {}

    for scenario in singles:
        result = _run_one(plan, scenario, problems)
        single_results[scenario["scenario_id"]] = result
        yield result

    for scenario in pairs:
        broken_single = next(
            (single_results[problem_id] for problem_id in scenario["failures"]
             if single_results[problem_id].state == "cross"),
            None,
        )
        if broken_single:
            yield ScenarioResult(
                scenario_id=scenario["scenario_id"],
                failures=scenario["failures"],
                state="dim",
                dim_cause=broken_single.scenario_id,
                lateness_minutes=broken_single.lateness_minutes,
                human_cost=broken_single.human_cost,
            )
        else:
            yield _run_one(plan, scenario, problems)


def _run_one(
    plan: PlanMapData,
    scenario: dict,
    problems: dict[str, dict],
) -> ScenarioResult:
    # CP-SAT's native dependencies are only needed when a scenario is checked.
    # Keep them off the API startup path, including the health endpoint.
    from server.checker.solver import solve_scenario

    disabled: dict[str, dict] = {}
    for problem_id in scenario["failures"]:
        problem = problems[problem_id]
        problem_type = problem["type_id"]
        operation = {
            "volunteer_absent": ("absent", True),
            "volunteer_leaves_early": ("leaves_early", problem["size"]),
            "vehicle_returns_late": ("returns_late", problem["size"]),
            "supply_delivery_late": ("arrives_late", problem["size"]),
            "place_blocked": ("blocked", problem["size"]),
        }[problem_type]
        disabled.setdefault(problem["entity_id"], {})[operation[0]] = operation[1]

    state, lateness, timeline, human_cost = solve_scenario(plan, disabled)
    return ScenarioResult(
        scenario_id=scenario["scenario_id"],
        failures=scenario["failures"],
        state=state,
        lateness_minutes=lateness,
        timeline=timeline,
        human_cost=human_cost,
    )
