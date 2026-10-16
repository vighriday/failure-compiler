"""Gate fixed operations, score every scenario, and apply only server-approved fixes."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

from server.checker.explain import route_reasons
from server.checker.runner import run_checker
from server.models import AppliedFix, FixOperation, FixSuggestion, ScenarioResult
from server.session import SESSIONS, remember_map
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.gate import GateError, normalise_plan_map_ids
from server.validation.models import PlanMap
from server.validation.rules import validate_plan_rules

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]


class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str
    scenario_id: str


class ApplyRequest(SuggestRequest):
    fix_id: str


class FixGateError(ValueError):
    pass


def apply_operations(plan: PlanMap, operations: list[FixOperation]) -> PlanMap:
    """Apply only the specified operation vocabulary to existing entities."""
    if not operations:
        raise FixGateError("The fix has no operations.")
    updated = plan.model_copy(deep=True)
    people = {person.id: person for person in updated.people}
    vehicles = {vehicle.id: vehicle for vehicle in updated.vehicles}
    routes = {route.id: route for route in updated.routes}
    for operation in operations:
        op, field, value = operation.op, operation.field, operation.value
        collection = (
            routes
            if op
            in {"add_driver", "replace_drivers", "add_loader", "replace_loaders", "move_route"}
            else vehicles
            if op == "set_vehicle_availability"
            else people
        )
        target = collection.get(operation.target_id)
        if target is None:
            raise FixGateError(f"Unknown target id '{operation.target_id}' in fix {op}.")
        before = target.model_dump(mode="json")
        if op in {"add_driver", "replace_drivers", "add_loader", "replace_loaders"}:
            expected = "driver_ids" if op in {"add_driver", "replace_drivers"} else "loader_ids"
            if field != expected:
                raise FixGateError(f"Invalid field '{field}' for fix {op}; expected {expected}.")
            ids = [value] if isinstance(value, str) else value
            if (
                not isinstance(ids, list)
                or not ids
                or not all(isinstance(item, str) for item in ids)
            ):
                raise FixGateError(f"Invalid value {value!r} in {operation.target_id} {field}.")
            for person_id in ids:
                if person_id not in people:
                    raise FixGateError(
                        f"Unknown person id '{person_id}' in {operation.target_id} {field}."
                    )
            values = (
                list(dict.fromkeys([*getattr(target, field), *ids]))
                if op.startswith("add_")
                else list(dict.fromkeys(ids))
            )
            setattr(target, field, values)
        elif op == "move_route":
            if field != "vehicle_id" or not isinstance(value, str) or value not in vehicles:
                raise FixGateError(
                    f"Invalid vehicle value {value!r} in {operation.target_id} {field}."
                )
            target.vehicle_id = value
        elif op == "give_spare_key":
            if field != "holds_key" or value is not True:
                raise FixGateError(
                    f"Invalid value {value!r} for spare key {field}; expected holds_key true."
                )
            target.holds_key = True
        else:
            allowed = (
                {"available_from"}
                if op == "set_vehicle_availability"
                else {"available_from", "available_until"}
            )
            if field not in allowed or type(value) is not int or not 0 <= value <= 1440:
                raise FixGateError(f"Invalid value {value!r} in {operation.target_id} {field}.")
            setattr(target, field, value)
        target.original_value = target.original_value or before
        target.status = "corrected"
    updated.fingerprint = None
    # The same ID/reference gate and consistency rules used for a plan reading.
    normalise_plan_map_ids(updated)
    issues = validate_plan_rules(updated)
    if issues:
        raise FixGateError(" ".join(issue.message for issue in issues))
    return updated


@dataclass
class ScoredFix:
    suggestion: FixSuggestion
    plan: PlanMap | None


SCORED: dict[tuple[str, str], list[ScoredFix]] = {}


def score_fix(
    plan: PlanMap, current: list[ScenarioResult], scenario_id: str, raw: dict[str, Any]
) -> ScoredFix:
    try:
        suggestion = FixSuggestion.model_validate(raw)
        candidate = apply_operations(plan, suggestion.operations)
    except (ValidationError, FixGateError, GateError) as error:
        suggestion = FixSuggestion(
            id=str(raw.get("id", "unusable-fix")),
            description=str(raw.get("description", "Suggested change")),
            operations=[],
            gate_status="couldnt_apply",
            gate_reason=str(error),
        )
        return ScoredFix(suggestion, None)
    fingerprint = fingerprint_plan_map(candidate)
    results = [
        r.model_copy(update={"map_fingerprint": fingerprint})
        for r in run_checker(candidate.checker_data())
    ]
    current_crosses = {r.scenario_id for r in current if r.state == "cross"}
    after_crosses = {r.scenario_id for r in results if r.state == "cross"}
    states = {r.scenario_id: r.state for r in results}
    suggestion.scenario_results = results
    suggestion.new_crosses = sorted(after_crosses - current_crosses)
    suggestion.new_crosses_n = len(suggestion.new_crosses)
    suggestion.still_broken_n = len(current_crosses & after_crosses)
    suggestion.fixes_n = len(current_crosses) - suggestion.still_broken_n
    suggestion.eligible = states.get(scenario_id) == "tick" and not suggestion.new_crosses
    if suggestion.new_crosses:
        from server.checker.scenarios import _instantiate_problems
        from server.grid import problem_labels

        labels = {
            p["id"]: p["label"] for p in problem_labels(_instantiate_problems(plan.checker_data()))
        }
        name = " + ".join(labels[p] for p in suggestion.new_crosses[0].split("+"))
        suggestion.rejection_reason = f"This reveals a new hidden pair: {name}."
    elif not suggestion.eligible:
        result = next(r for r in results if r.scenario_id == scenario_id)
        reasons = route_reasons(candidate.checker_data(), result)
        suggestion.rejection_reason = (
            " ".join(dict.fromkeys(reasons.values()))
            or result.human_cost
            or "The checker could not prove that this fixes the selected case."
        )
    return ScoredFix(suggestion, candidate)


@router.post("/api/suggest-fixes")
def suggest_fixes(request: SuggestRequest) -> dict[str, Any]:
    session = SESSIONS.get(request.fingerprint)
    if session is None or session.results is None:
        raise HTTPException(409, "Run this confirmed map before asking for fixes.")
    result = next((r for r in session.results if r.scenario_id == request.scenario_id), None)
    if result is None or result.state != "cross":
        raise HTTPException(404, "That broken case is not on the current grid.")
    fixture = json.loads((ROOT / "fixtures/example-fixes.json").read_text(encoding="utf-8"))
    saved = fixture["cases"].get(request.scenario_id, {})
    key = (request.fingerprint, request.scenario_id)
    if key not in SCORED:
        SCORED[key] = [
            score_fix(session.plan, session.results, request.scenario_id, raw)
            for raw in saved.get("fixes", [])
        ]
    reasons = route_reasons(session.plan.checker_data(), result)
    return {
        "placeholder": True,
        "explanation": saved.get("explanation"),
        "result": result.model_dump(mode="json"),
        "route_reasons": reasons,
        "alone_results": [
            r.model_dump(mode="json") for r in session.results if r.scenario_id in result.failures
        ],
        "suggestions": [entry.suggestion.model_dump(mode="json") for entry in SCORED[key]],
    }


@router.post("/api/apply-fix")
def apply_fix(request: ApplyRequest) -> dict[str, Any]:
    session = SESSIONS.get(request.fingerprint)
    entry = next(
        (
            entry
            for entry in SCORED.get((request.fingerprint, request.scenario_id), [])
            if entry.suggestion.id == request.fix_id
        ),
        None,
    )
    if session is None or entry is None or entry.plan is None or not entry.suggestion.eligible:
        raise HTTPException(
            409, "This fix cannot be accepted. Preview an eligible, checked suggestion first."
        )
    plan = entry.plan.model_copy(deep=True)
    fingerprint = fingerprint_plan_map(plan)
    applied = AppliedFix(
        fix_id=entry.suggestion.id,
        description=entry.suggestion.description,
        operations=entry.suggestion.operations,
        from_fingerprint=request.fingerprint,
        to_fingerprint=fingerprint,
    )
    plan.fix_history = [*session.plan.fix_history, applied]
    number = len(plan.fix_history)
    targets = {operation.target_id for operation in applied.operations}
    for entity in [*plan.people, *plan.vehicles, *plan.routes]:
        if entity.id in targets:
            entity.changed_by_fix = number
    remember_map(plan, entry.suggestion.scenario_results)
    return {
        "fingerprint": fingerprint,
        "plan_map": plan.model_dump(mode="json"),
        "applied_fix": applied.model_dump(mode="json"),
    }
