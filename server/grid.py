"""Stream the checker's real results and retain completed runs by fingerprint."""

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from server.checker.runner import iter_checker
from server.checker.scenarios import _instantiate_problems, generate_scenarios
from server.labels import read_by_label
from server.models import RunCount, ScenarioResult
from server.session import capture_map, get_map, map_is_current

router = APIRouter()


def count_results(results: list[ScenarioResult], total: int | None = None) -> RunCount:
    total = total if total is not None else len(results)
    weak_spots = sum(r.state == "cross" and len(r.failures) == 1 for r in results)
    hidden_pairs = sum(r.state == "cross" and len(r.failures) == 2 for r in results)
    dimmed = sum(r.state == "dim" for r in results)
    survived = sum(r.state == "tick" for r in results)
    unknown = sum(r.state == "qmark" for r in results)
    pending = total - len(results)
    weak_label = "single weak spot" if weak_spots == 1 else "single weak spots"
    pair_label = "hidden pair" if hidden_pairs == 1 else "hidden pairs"
    root_label = "the weak spot" if weak_spots == 1 else "a weak spot"
    line = (
        f"{total} tests: {weak_spots} {weak_label}, {hidden_pairs} {pair_label}, "
        f"{dimmed} already broken by {root_label}, {survived} survived"
    )
    if unknown:
        line += f", {unknown} unknown"
    if pending:
        line += f", {pending} to go"
    return RunCount(
        total=total,
        completed=len(results),
        weak_spots=weak_spots,
        hidden_pairs=hidden_pairs,
        dimmed=dimmed,
        survived=survived,
        unknown=unknown,
        pending=pending,
        line=line + ".",
    )


def problem_labels(problems: list[dict]) -> list[dict]:
    """Labels use confirmed sizes and names, including when the map is edited."""
    labels = []
    for problem in problems:
        name = (
            problem["label"].split(" absent")[0] if problem["type_id"] == "volunteer_absent" else ""
        )
        if problem["type_id"] == "volunteer_leaves_early":
            name = problem["label"].split(" leaves early")[0]
            label = f"{name} leaves {problem['size']} min early"
        elif problem["type_id"] == "vehicle_returns_late":
            name = problem["label"].split(" returns late")[0]
            label = f"{name} back {problem['size']} min late"
        elif problem["type_id"] == "supply_delivery_late":
            name = problem["label"].split(" arrives late")[0]
            label = f"{name} {problem['size']} min late"
        elif problem["type_id"] == "place_blocked":
            name = problem["label"].split(" blocked")[0]
            label = f"{name} blocked {problem['size']} min"
        else:
            label = f"{name} absent"
        labels.append({**problem, "label": label})
    return labels


def _event(kind: str, **payload: object) -> str:
    return "data: " + json.dumps({"type": kind, **payload}) + "\n\n"


@router.get("/api/run-tests")
def run_tests(
    request: Request, map: str = Query(...), reduced_motion: bool = False
) -> StreamingResponse:
    session = get_map(map, request.state.owner)
    if session is None:
        raise HTTPException(404, "Confirmed map not found. Confirm the plan again.")
    captured = capture_map(session)
    plan = captured.plan.checker_data()
    cached = captured.results
    read_by = read_by_label(captured.plan)
    problems = problem_labels(_instantiate_problems(plan))
    singles, pairs = generate_scenarios(plan)
    scenarios = singles + pairs

    def events() -> Iterator[str]:
        yield _event(
            "start",
            fingerprint=map,
            total=len(scenarios),
            problems=problems,
            scenarios=[
                {"scenario_id": s["scenario_id"], "failures": s["failures"]} for s in scenarios
            ],
            read_by=read_by,
            source=captured.source,
        )
        started = time.monotonic()
        source = cached if cached is not None else iter_checker(plan)
        completed: list[ScenarioResult] = []
        for result in source:
            result = result.model_copy(update={"map_fingerprint": map})
            completed.append(result)
            if not reduced_motion:
                delay = len(completed) / len(scenarios) * 3 - (time.monotonic() - started)
                if delay > 0:
                    time.sleep(delay)
            yield _event(
                "result",
                result=result.model_dump(mode="json"),
                count=count_results(completed, len(scenarios)).model_dump(),
            )
        with session.lock:
            if get_map(map, request.state.owner) is session and map_is_current(session, captured):
                session.results = completed
        yield _event("complete", count=count_results(completed).model_dump())

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
