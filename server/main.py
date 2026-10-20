"""HTTP boundary for saved and live readings, with server-owned review sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from server.ai import adapter
from server.ai.types import AIError
from server.config import FALLBACK_MODEL, FALLBACK_PROVIDER, PRIMARY_MODEL, PRIMARY_PROVIDER
from server.credentials import (
    CLIENTS,
    COOKIE_NAME,
    available_keys,
    browser_session,
    remember_key,
    safe_message,
)
from server.demo import RESET_MESSAGE, STATE_LOCK, clear_browser, require_active_owner
from server.demo import router as demo_router
from server.fixes import router as fixes_router
from server.grid import router as grid_router
from server.labels import read_by_label
from server.models import PlanMapData
from server.reading import items_for_plan, plan_from_record, questions_for_plan
from server.report import router as report_router
from server.review import check_owner, confirm_review, create_review, snapshot, update_review
from server.validation.gate import GateError, normalise_plan_map_ids, plan_map_from_reading
from server.validation.models import PlanMap
from server.validation.rules import validate_plan_rules

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Failure Compiler")
app.include_router(grid_router)
app.include_router(fixes_router)
app.include_router(report_router)
app.include_router(demo_router)


@app.middleware("http")
async def session_cookie(request: Request, call_next):
    owner = browser_session(request.cookies.get(COOKIE_NAME))
    request.state.owner = owner
    try:
        response = await call_next(request)
    except Exception:
        if request.state.owner in CLIENTS:
            raise
        return expired_response(request.state.owner)
    owner = request.state.owner
    if owner not in CLIENTS:
        # An old fix request may have allocated its per-case lock immediately
        # after reset. Its stale check rejects the write; discard that lock too.
        return expired_response(owner)
    if request.cookies.get(COOKIE_NAME) != owner:
        response.set_cookie(COOKIE_NAME, owner, httponly=True, samesite="lax")
    return response


def expired_response(owner: str) -> JSONResponse:
    clear_browser(owner)
    return JSONResponse(
        status_code=409,
        content={"detail": RESET_MESSAGE},
        headers={"Cache-Control": "no-store"},
    )


def session_message(owner: str, message: str) -> str:
    with STATE_LOCK:
        return safe_message(owner, message) if owner in CLIENTS else RESET_MESSAGE


@app.exception_handler(AIError)
def ai_error(request: Request, error: AIError) -> JSONResponse:
    content = {
        "detail": session_message(request.state.owner, str(error)),
        "error_code": error.code,
    }
    if getattr(error, "case_detail", None) is not None:
        content["case_detail"] = error.case_detail
    return JSONResponse(
        status_code=error.status,
        content=content,
    )


@app.exception_handler(GateError)
def gate_error(request: Request, error: GateError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": session_message(request.state.owner, str(error))}
    )


@app.exception_handler(RequestValidationError)
def request_error(request: Request, error: RequestValidationError) -> JSONResponse:
    issue = error.errors()[0]
    field = ".".join(str(part) for part in issue["loc"])
    return JSONResponse(
        status_code=422,
        content={
            "detail": session_message(request.state.owner, f"Invalid request field {field}."),
            "error_code": "invalid_request",
        },
    )


@app.exception_handler(HTTPException)
def http_error(request: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": session_message(request.state.owner, str(error.detail))},
        headers=error.headers,
    )


@app.exception_handler(ValidationError)
def shape_error(request: Request, error: ValidationError) -> JSONResponse:
    issue = error.errors(include_url=False)[0]
    field = ".".join(str(part) for part in issue["loc"])
    return JSONResponse(
        status_code=422,
        content={
            "detail": session_message(
                request.state.owner,
                f"Invalid {field}: {issue.get('input')!r}. {issue['msg']}",
            )
        },
    )


def _fixture(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ai-status")
def ai_status(request: Request) -> dict[str, Any]:
    with STATE_LOCK:
        require_active_owner(request.state.owner)
        keys = available_keys(request.state.owner)
        return {
            "primary_provider": PRIMARY_PROVIDER,
            "primary_model": PRIMARY_MODEL,
            "fallback_provider": FALLBACK_PROVIDER,
            "fallback_model": FALLBACK_MODEL,
            "selected_provider": CLIENTS[request.state.owner].selected_provider,
            "key_available": {name: bool(key) for name, key in keys.items()},
        }


def create_current_review(*args, owner: str, **kwargs) -> dict[str, Any]:
    # Provider requests run outside this lock. Only persistence is serialized
    # with reset, so an old request cannot reintroduce an expired browser.
    with STATE_LOCK:
        require_active_owner(owner)
        return create_review(*args, owner=owner, **kwargs)


@app.post("/api/read-plan")
def read_plan(request: dict[str, Any], http_request: Request) -> dict[str, Any]:
    owner = http_request.state.owner
    if set(request) - {"example", "text", "api_key", "key_provider"}:
        raise AIError("invalid_request", "Unknown read-plan request field.", status=422)
    if type(request.get("example", False)) is not bool:
        raise AIError("invalid_request", "example must be true or false.", status=422)
    provider = request.get("key_provider", PRIMARY_PROVIDER)
    if not isinstance(provider, str) or provider not in {"gemini", "groq"}:
        raise AIError("invalid_request", "Choose Gemini or Groq for the AI key.", status=422)
    with STATE_LOCK:
        require_active_owner(owner)
        if "api_key" in request:
            remember_key(owner, request.get("key_provider", PRIMARY_PROVIDER), request["api_key"])
        keys = available_keys(owner)
        preferred_provider = CLIENTS[owner].selected_provider
    if not request.get("example"):
        text = request.get("text", "")
        if not isinstance(text, str):
            raise AIError("invalid_plan", "Enter a plan of 1 to 4,000 characters.", status=422)
        result = adapter.read_plan(text, keys, preferred_provider=preferred_provider)
        plan = plan_map_from_reading(
            result.reading,
            provider=result.raw.provider,
            model=result.raw.model,
            timestamp=result.raw.timestamp,
        )
        items = items_for_plan(plan)
        return {
            "plan_text": text,
            **create_current_review(
                plan,
                items,
                questions_for_plan(plan, items),
                owner=owner,
                source="live",
                attempts=result.attempts,
                raw_record=result.raw.record(),
            ),
            "problem_types": plan.problem_sizes,
        }
    truth = PlanMapData.model_validate(_fixture("fixtures/example-truth.json"))
    reading = _fixture("fixtures/example-reading.json")
    if "raw_text" in reading:
        plan = plan_from_record(reading)
        items = items_for_plan(plan)
        return {
            "plan_text": (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8"),
            **create_current_review(
                plan,
                items,
                questions_for_plan(plan, items),
                owner=owner,
                source="saved",
                raw_record=reading,
            ),
            "placeholder": False,
            "read_by": read_by_label(plan),
            "problem_types": plan.problem_sizes,
        }
    plan = PlanMap.from_truth_map(truth)
    for collection in (plan.people, plan.vehicles, plan.places, plan.deliveries, plan.routes):
        for entity in collection:
            entity.status = "unconfirmed"
    # The one deliberately guessed value is already equal to the truth map.
    return {
        "plan_text": (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8"),
        **create_current_review(
            plan, reading["items"], reading["questions"], owner=owner, source="placeholder"
        ),
        "placeholder": reading["placeholder"],
        "read_by": reading["provider"],
        "problem_types": _fixture("fixtures/example-truth.json")["problem_sizes"],
    }


@app.post("/api/validate-map")
def validate_map(request: dict[str, Any], http_request: Request) -> dict[str, Any]:
    if request.get("reading_id"):
        with STATE_LOCK:
            require_active_owner(http_request.state.owner)
            check_owner(request["reading_id"], http_request.state.owner)
            return snapshot(request["reading_id"])
    try:
        plan = PlanMap.model_validate(request["plan_map"])
    except (KeyError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    normalise_plan_map_ids(plan)
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
        "open_questions": sum(not answers.get(question.get("id")) for question in questions),
    }


@app.post("/api/confirm-map")
def confirm_map(request: dict[str, Any], http_request: Request) -> dict[str, Any]:
    with STATE_LOCK:
        require_active_owner(http_request.state.owner)
        check_owner(request.get("reading_id"), http_request.state.owner)
        return confirm_review(request)


@app.post("/api/update-map")
def update_map(request: dict[str, Any], http_request: Request) -> dict[str, Any]:
    with STATE_LOCK:
        require_active_owner(http_request.state.owner)
        check_owner(request.get("reading_id"), http_request.state.owner)
        return update_review(request)


if (ROOT / "web/dist").is_dir():
    app.mount("/assets", StaticFiles(directory=ROOT / "web/dist/assets"), name="assets")

    @app.get("/{path:path}")
    def serve_app(path: str) -> FileResponse:
        return FileResponse(ROOT / "web/dist/index.html")
