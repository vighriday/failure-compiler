"""HTTP boundary for the example-mode plan map."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from server.models import PlanMapData
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.models import PlanMap
from server.validation.rules import validate_plan_rules

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Failure Compiler")


def _fixture(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/read-plan")
def read_plan(request: dict[str, Any]) -> dict[str, Any]:
    if not request.get("example"):
        raise HTTPException(
            status_code=501,
            detail="Live plan reading is added in slice 6. Load the example plan for now.",
        )
    truth = PlanMapData.model_validate(_fixture("fixtures/example-truth.json"))
    reading = _fixture("fixtures/example-reading.json")
    plan = PlanMap.from_truth_map(truth)
    for collection in (plan.people, plan.vehicles, plan.places, plan.deliveries, plan.routes):
        for entity in collection:
            entity.status = "unconfirmed"
    # The one deliberately guessed value is already equal to the truth map.
    return {
        "plan_text": (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8"),
        "plan_map": plan.model_dump(mode="json"),
        "items": reading["items"],
        "questions": reading["questions"],
        "placeholder": reading["placeholder"],
        "read_by": reading["provider"],
        "problem_types": _fixture("fixtures/example-truth.json")["problem_sizes"],
    }


@app.post("/api/validate-map")
def validate_map(request: dict[str, Any]) -> dict[str, Any]:
    try:
        plan = PlanMap.model_validate(request["plan_map"])
    except (KeyError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    issues = validate_plan_rules(plan)
    items = request.get("items", [])
    questions = request.get("questions", [])
    answers = request.get("answers", {})
    return {
        "valid": not issues,
        "issues": [issue.__dict__ for issue in issues],
        "unconfirmed_items": sum(
            item.get("status") not in {"confirmed", "corrected", "added"} for item in items
        ),
        "open_questions": sum(
            not answers.get(question.get("id")) for question in questions
        ),
    }


@app.post("/api/confirm-map")
def confirm_map(request: dict[str, Any]) -> dict[str, Any]:
    try:
        plan = PlanMap.model_validate(request["plan_map"])
    except (KeyError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    items = request.get("items", [])
    questions = request.get("questions", [])
    answers = request.get("answers", {})
    if any(item.get("status") not in {"confirmed", "corrected", "added"} for item in items):
        raise HTTPException(
            status_code=409, detail="Every reading item must be confirmed or corrected"
        )
    if any(not answers.get(question.get("id")) for question in questions):
        raise HTTPException(
            status_code=409, detail="Every open question needs an individual answer"
        )
    issues = validate_plan_rules(plan)
    if issues:
        raise HTTPException(status_code=409, detail=[issue.message for issue in issues])
    plan.fingerprint = fingerprint_plan_map(plan)
    return {"confirmed": True, "fingerprint": plan.fingerprint}


if (ROOT / "web/dist").is_dir():
    app.mount("/assets", StaticFiles(directory=ROOT / "web/dist/assets"), name="assets")

    @app.get("/{path:path}")
    def serve_app(path: str) -> FileResponse:
        return FileResponse(ROOT / "web/dist/index.html")
