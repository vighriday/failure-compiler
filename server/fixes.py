"""Gate fixed operations, score every scenario, and apply only server-approved fixes."""

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from server.ai import adapter
from server.ai.types import AIError
from server.checker.explain import route_reasons
from server.checker.runner import run_checker
from server.credentials import CLIENTS, available_keys, public_attempts
from server.evaluation import align_entities
from server.models import AppliedFix, FixOperation, FixSuggestion, PlanMapData, ScenarioResult
from server.session import (
    MapSession,
    MapSnapshot,
    capture_map,
    get_map,
    map_is_current,
    remember_map,
)
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
    live: bool = False
    retry: bool = False


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


SCORED: dict[tuple, list[ScoredFix]] = {}
DETAILS: dict[tuple, dict] = {}
RAW_FIXES: dict[tuple, list[dict]] = {}
FIX_LOCKS: dict[tuple, Lock] = {}
RETRIED: set[tuple] = set()


def cache_key(
    session: MapSession, fingerprint: str, scenario_id: str, revision: int | None = None
) -> tuple:
    if session.owner is None:
        return (fingerprint, scenario_id)
    return (
        session.owner,
        fingerprint,
        session.revision if revision is None else revision,
        scenario_id,
    )


def require_current(session: MapSession, captured: MapSnapshot, fingerprint: str) -> None:
    if get_map(fingerprint, session.owner) is not session or not map_is_current(session, captured):
        raise HTTPException(409, "This reading changed. Run the current confirmed map again.")


def fix_context(plan: PlanMap, result: ScenarioResult, results: list[ScenarioResult]) -> dict:
    from server.checker.scenarios import _instantiate_problems

    problems = {problem["id"]: problem for problem in _instantiate_problems(plan.checker_data())}
    return {
        "confirmed_map": plan.checker_data().model_dump(mode="json"),
        "selected_case": result.model_dump(mode="json"),
        "selected_problems": [problems[pid] for pid in result.failures],
        "checker_reasons": route_reasons(plan.checker_data(), result),
        "each_alone": [
            row.model_dump(mode="json")
            for row in results
            if len(row.failures) == 1 and row.scenario_id in result.failures
        ],
    }


def example_case(plan: PlanMap, scenario_id: str, fixture: dict) -> dict:
    """Align hand-written example suggestions to the reviewed map's entity identities."""
    truth = PlanMap.from_truth_map(
        PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    )
    _, mapping, unmatched = align_entities(plan, truth)
    if unmatched:
        return {}

    def aligned_problem(value):
        kind, entity_id = value.split("__", 1)
        return f"{kind}__{mapping.get(entity_id, entity_id)}"

    aligned_case = {aligned_problem(value) for value in scenario_id.split("+")}
    saved = next(
        (value for key, value in fixture["cases"].items() if set(key.split("+")) == aligned_case),
        {},
    )
    saved = deepcopy(saved)
    inverse = {target: source for source, target in mapping.items()}
    for fix in saved.get("fixes", []):
        for operation in fix["operations"]:
            operation["target_id"] = inverse.get(operation["target_id"], operation["target_id"])
            value = operation["value"]
            if isinstance(value, str):
                operation["value"] = inverse.get(value, value)
            elif isinstance(value, list):
                operation["value"] = [inverse.get(item, item) for item in value]
    return saved


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
        category = (
            "single weak spot" if len(suggestion.new_crosses[0].split("+")) == 1 else "hidden pair"
        )
        suggestion.rejection_reason = f"This reveals a new {category}: {name}."
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
def suggest_fixes(request: SuggestRequest, http_request: Request) -> dict[str, Any]:
    session = get_map(request.fingerprint, http_request.state.owner)
    if session is None:
        raise HTTPException(409, "Run this confirmed map before asking for fixes.")
    captured = capture_map(session)
    if captured.results is None:
        raise HTTPException(409, "Run this confirmed map before asking for fixes.")
    plan, results = captured.plan, captured.results
    result = next((r for r in results if r.scenario_id == request.scenario_id), None)
    if result is None or result.state != "cross":
        raise HTTPException(404, "That broken case is not on the current grid.")
    key = cache_key(session, request.fingerprint, request.scenario_id, captured.revision)
    lock = FIX_LOCKS.setdefault(key, Lock())
    with lock:
        with session.lock:
            require_current(session, captured, request.fingerprint)
        cached = DETAILS.get(key)
        upgrade = (
            (request.live or captured.source == "live")
            and cached is not None
            and cached["source"] != "live"
        )
        retry = (
            request.retry
            and cached is not None
            and not any(suggestion["eligible"] for suggestion in cached["suggestions"])
        )
        if retry and key in RETRIED:
            raise HTTPException(409, "The extra suggestion attempt has already been used.")
        if cached is not None and not upgrade and not retry:
            with session.lock:
                require_current(session, captured, request.fingerprint)
                return cached
        live = captured.source == "live" or request.live or retry
        raw_record = None
        if live:
            owner = http_request.state.owner
            try:
                response = adapter.suggest_fixes(
                    fix_context(plan, result, results),
                    available_keys(owner),
                    preferred_provider=CLIENTS[owner].selected_provider,
                )
            except AIError as error:
                with session.lock:
                    require_current(session, captured, request.fingerprint)
                error.case_detail = {
                    "placeholder": False,
                    "source": "live",
                    "suggested_by": None,
                    "fallback_used": False,
                    "attempts": public_attempts(getattr(error, "attempts", [])),
                    "explanation": None,
                    "suggestions": [],
                    "can_retry": False,
                    "result": result.model_dump(mode="json"),
                    "route_reasons": route_reasons(plan.checker_data(), result),
                    "alone_results": [
                        r.model_dump(mode="json")
                        for r in results
                        if r.scenario_id in result.failures
                    ],
                }
                raise
            with session.lock:
                require_current(session, captured, request.fingerprint)
            raw_record = response.raw.record()
            saved = response.fixes.model_dump(mode="json")
            source = "live"
            suggested_by = f"{response.raw.provider} / {response.raw.model}"
            attempts = public_attempts(response.attempts)
        else:
            fixture = json.loads((ROOT / "fixtures/example-fixes.json").read_text(encoding="utf-8"))
            saved = example_case(plan, request.scenario_id, fixture)
            source, suggested_by, attempts = "placeholder", None, []
        scored = [
            score_fix(plan, results, request.scenario_id, raw) for raw in saved.get("fixes", [])
        ]
        details = {
            "placeholder": source == "placeholder",
            "source": source,
            "suggested_by": suggested_by,
            "fallback_used": len(attempts) > 1,
            "attempts": attempts,
            "explanation": saved.get("explanation"),
            "result": result.model_dump(mode="json"),
            "route_reasons": route_reasons(plan.checker_data(), result),
            "alone_results": [
                r.model_dump(mode="json") for r in results if r.scenario_id in result.failures
            ],
            "suggestions": [entry.suggestion.model_dump(mode="json") for entry in scored],
            "can_retry": live and not retry and key not in RETRIED,
        }
        with session.lock:
            require_current(session, captured, request.fingerprint)
            if raw_record is not None:
                RAW_FIXES.setdefault(key, []).append(raw_record)
            if retry:
                RETRIED.add(key)
            SCORED[key] = scored
            DETAILS[key] = details
            return details


@router.post("/api/apply-fix")
def apply_fix(request: ApplyRequest, http_request: Request) -> dict[str, Any]:
    session = get_map(request.fingerprint, http_request.state.owner)
    captured = capture_map(session) if session else None
    key = (
        cache_key(session, request.fingerprint, request.scenario_id, captured.revision)
        if session
        else ()
    )
    entry = next(
        (entry for entry in SCORED.get(key, []) if entry.suggestion.id == request.fix_id),
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
    plan.fix_history = [*captured.plan.fix_history, applied]
    number = len(plan.fix_history)
    targets = {operation.target_id for operation in applied.operations}
    for entity in [*plan.people, *plan.vehicles, *plan.routes]:
        if entity.id in targets:
            entity.changed_by_fix = number
    with session.lock:
        require_current(session, captured, request.fingerprint)
        remember_map(
            plan, entry.suggestion.scenario_results, owner=session.owner, source=captured.source
        )
        return {
            "fingerprint": fingerprint,
            "plan_map": plan.model_dump(mode="json"),
            "applied_fix": applied.model_dump(mode="json"),
        }
