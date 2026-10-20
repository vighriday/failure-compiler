"""Server-owned reading drafts and explicit review actions. Browser lists are never trusted."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import TypeAdapter

from server.facts import changed_by, controls, entity_for, loading_team, statement
from server.place_review import answer_place_question, reopen_place_question
from server.rule_questions import answer_rule_question, sync_rule_questions
from server.session import capture_map, get_map, remember_map
from server.validation.gate import normalise_plan_map_ids
from server.validation.models import PlanMap
from server.validation.rules import validate_plan_rules

ACCEPTED = {"confirmed", "corrected", "added"}


@dataclass
class Review:
    plan: PlanMap
    items: list[dict]
    questions: list[dict]
    answers: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False
    out_of_date: bool = False
    owner: str | None = None
    source: str = "saved"
    attempts: list[dict] = field(default_factory=list)
    raw_record: dict | None = field(default=None, repr=False)
    ai_read_n: int = 0


REVIEWS: dict[str, Review] = {}


def create_review(
    plan: PlanMap,
    items: list[dict],
    questions: list[dict],
    *,
    owner: str | None = None,
    source: str = "saved",
    attempts: list[dict] | None = None,
    raw_record: dict | None = None,
) -> dict:
    reading_id = uuid4().hex
    review = Review(
        plan.model_copy(deep=True),
        deepcopy(items),
        deepcopy(questions),
        owner=owner,
        source=source,
        attempts=attempts or [],
        raw_record=raw_record,
        ai_read_n=len(items),
    )
    for item in review.items:
        item["original_statement"] = statement(review.plan, item)
    REVIEWS[reading_id] = review
    return snapshot(reading_id)


def get_review(reading_id: str | None) -> Review:
    if not isinstance(reading_id, str) or not reading_id or reading_id not in REVIEWS:
        raise HTTPException(422, "Missing or unknown reading_id; review confirmations are required")
    return REVIEWS[reading_id]


def check_owner(reading_id: str | None, owner: str) -> None:
    review = get_review(reading_id)
    if review.owner is not None and review.owner != owner:
        raise HTTPException(404, "This reading is not part of the current session.")


def snapshot(reading_id: str) -> dict:
    review = get_review(reading_id)
    sync_rule_questions(review)
    issues = validate_plan_rules(review.plan)
    items = [
        {
            **item,
            "statement": statement(review.plan, item),
            "controls": controls(review.plan, item),
            "changed_by_fix": changed_by(review.plan, item),
        }
        for item in review.items
    ]
    return {
        "reading_id": reading_id,
        "plan_map": review.plan.model_dump(mode="json"),
        "items": items,
        "questions": review.questions,
        "answers": review.answers,
        "issues": [
            issue.__dict__
            for issue in issues
            if not any(
                question.get("entity_id") == issue.item_id and question.get("field") == issue.field
                for question in review.questions
                if question.get("kind")
            )
        ],
        "valid": not issues,
        "unconfirmed_items": sum(item["status"] not in ACCEPTED for item in items),
        "open_questions": sum(q["id"] not in review.answers for q in review.questions),
        "confirmed": review.confirmed,
        "out_of_date": review.out_of_date,
        "read_by": f"{review.plan.ai_meta.provider} / {review.plan.ai_meta.model}",
        "source": review.source,
        "placeholder": review.source == "placeholder",
        "fallback_used": len(review.attempts) > 1,
        "attempts": [
            {key: row[key] for key in ("provider", "status", "error") if key in row}
            for row in review.attempts
        ],
    }


def _cascade(review: Review, edited: dict, previous: PlanMap) -> None:
    """Invalidate dependent routes, including when a changed driver is only a backup."""
    kind, entity_id = edited["entity_type"], edited["entity_id"]
    if kind == "route":
        affected = {entity_id}
    elif kind == "person":
        affected = {
            route.id
            for route in [*previous.routes, *review.plan.routes]
            if entity_id in [*route.driver_ids, *route.loader_ids]
        }
    elif kind == "vehicle":
        affected = {route.id for route in review.plan.routes if route.vehicle_id == entity_id}
    else:
        affected = {route.id for route in review.plan.routes}
    for item in review.items:
        if (
            item is not edited
            and item["entity_type"] == "route"
            and item["entity_id"] in affected
            and item["status"] in ACCEPTED
        ):
            item["status"] = "stale"
    for route in review.plan.routes:
        if route.id in affected:
            route.status = "unconfirmed"


def _sync_entity_statuses(review: Review) -> None:
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for entity in getattr(review.plan, collection):
            items = [item for item in review.items if item["entity_id"] == entity.id]
            entity.status = (
                "confirmed"
                if items and all(item["status"] in ACCEPTED for item in items)
                else "unconfirmed"
            )


def _correct(review: Review, item: dict, field_name: str, value: Any) -> None:
    allowed = [control["field"] for control in controls(review.plan, item)]
    if field_name not in allowed:
        raise HTTPException(422, f"Unknown correction field {field_name!r} for {item['id']}")
    previous = review.plan.model_copy(deep=True)
    candidate = review.plan.model_copy(deep=True)
    target = entity_for(candidate, item)
    before = (
        loading_team(candidate) if field_name == "loading_team" else getattr(target, field_name)
    )
    if (field_name in {"driver_ids", "loader_ids", "vehicle_id"} and not before) or (
        field_name == "finish_time" and before <= 0
    ):
        raise HTTPException(422, f"Add missing {field_name} through its rule question")
    expected = list[str] if isinstance(before, list) else type(before)
    value = TypeAdapter(expected).validate_python(value, strict=True)
    if isinstance(value, list) and (
        len(value) != len(set(value))
        or any(person_id not in {person.id for person in candidate.people} for person_id in value)
    ):
        raise HTTPException(
            422, f"Invalid {field_name} value {value!r}; pick distinct existing people"
        )
    if field_name == "loading_team":
        for route in candidate.routes:
            route.loader_ids = [
                *value,
                *[pid for pid in route.loader_ids if pid not in before and pid not in value],
            ]
    else:
        setattr(target, field_name, value)
    # Gate reference errors before installing a draft. Plain rules remain visible for correction.
    normalise_plan_map_ids(candidate)
    review.plan = candidate
    item["status"] = "corrected"
    item["value"] = value
    if before != value:
        _cascade(review, item, previous)
        review.plan.fingerprint = None
        review.confirmed = False
        review.out_of_date = True


def update_review(request: dict) -> dict:
    reading_id = request.get("reading_id")
    original = get_review(reading_id)
    # Transactional edits: a rejected action cannot partly mutate server review state.
    review = deepcopy(original)
    sync_rule_questions(review)
    action = request.get("action")
    item = next((item for item in review.items if item["id"] == request.get("item_id")), None)
    if action == "confirm_all":
        for row in review.items:
            if row["status"] == "unconfirmed" and not row.get("guessed"):
                row["status"] = "confirmed"
    elif action in {"confirm_item", "correct"}:
        if item is None:
            raise HTTPException(422, f"Unknown item_id {request.get('item_id')!r}")
        if action == "confirm_item":
            item["status"] = "confirmed"
        else:
            _correct(review, item, request.get("field"), request.get("value"))
    elif action in {"answer", "reopen_question"}:
        question = next(
            (q for q in review.questions if q["id"] == request.get("question_id")), None
        )
        if question is None:
            raise HTTPException(422, f"Unknown question_id {request.get('question_id')!r}")
        if action == "reopen_question":
            if question.get("kind") == "place_identity":
                reopen_place_question(review, question)
            review.answers.pop(question["id"], None)
            review.confirmed = False
            review.out_of_date = True
        else:
            answer = request.get("value")
            if question.get("kind") == "place_identity":
                answer_place_question(review, question, answer)
                _sync_entity_statuses(review)
                REVIEWS[reading_id] = review
                return snapshot(reading_id)
            if question.get("kind", "").startswith("missing_"):
                answer_rule_question(review, question, answer)
                _sync_entity_statuses(review)
                REVIEWS[reading_id] = review
                return snapshot(reading_id)
            if not isinstance(answer, str) or answer not in question["choices"]:
                raise HTTPException(422, f"Invalid answer {answer!r} for {question['id']}")
            if question["id"].startswith("reading-question-"):
                associated = next(row for row in review.items if row["id"] == question["item_id"])
                if any(
                    row["status"] not in ACCEPTED
                    for row in review.items
                    if row["entity_id"] == associated["entity_id"]
                ):
                    raise HTTPException(
                        422, "Review the associated facts individually before answering"
                    )
            if question["id"] == "ravi-van-loading-question":
                for route in list(review.plan.routes):
                    if route.vehicle_id != "vehicle-van":
                        continue
                    loaders = [pid for pid in route.loader_ids if pid != "person-ravi"]
                    if answer == "The van too":
                        loaders.append("person-ravi")
                    row = next(row for row in review.items if row["entity_id"] == route.id)
                    if route.loader_ids != loaders:
                        _correct(review, row, "loader_ids", loaders)
            review.answers[question["id"]] = answer
    elif action == "problem_size":
        from server.config import SIZE_PRESETS

        problem_type, value = request.get("field"), request.get("value")
        if (
            problem_type not in review.plan.problem_sizes
            or type(value) is not int
            or value not in SIZE_PRESETS
        ):
            raise HTTPException(422, f"Invalid problem size {problem_type!r}: {value!r}")
        if review.plan.problem_sizes[problem_type] != value:
            review.plan.problem_sizes[problem_type] = value
            review.plan.fingerprint = None
            review.confirmed = False
            review.out_of_date = True
    elif action == "restore_fixed":
        fingerprint = request.get("fingerprint")
        session = get_map(fingerprint, review.owner)
        if session is None or not any(
            fix.from_fingerprint == review.plan.fingerprint for fix in session.plan.fix_history
        ):
            raise HTTPException(422, "The accepted fix does not belong to this confirmed reading")
        review.plan = session.plan.model_copy(deep=True)
        review.confirmed = True
    else:
        raise HTTPException(422, f"Unknown review action {action!r}")
    _sync_entity_statuses(review)
    REVIEWS[reading_id] = review
    return snapshot(reading_id)


def confirm_review(request: dict) -> dict:
    reading_id = request.get("reading_id")
    review = get_review(reading_id)
    sync_rule_questions(review)
    normalise_plan_map_ids(review.plan)
    missing = [item["id"] for item in review.items if item["status"] not in ACCEPTED]
    missing += [q["id"] for q in review.questions if q["id"] not in review.answers]
    messages = [issue.message for issue in validate_plan_rules(review.plan)]
    if missing or messages:
        raise HTTPException(422, "Review required: " + "; ".join([*missing, *messages]))
    _sync_entity_statuses(review)
    evidence = {
        "ai_read": review.ai_read_n,
        "corrected": sum(item["status"] == "corrected" for item in review.items)
        + sum(bool(q.get("merge")) for q in review.questions),
        "added": sum(item["status"] == "added" for item in review.items),
        "items": deepcopy(review.items),
        "answers": [
            {"question": q["question_text"], "answer": review.answers[q["id"]]}
            for q in review.questions
            if q["id"] in review.answers
        ],
    }
    ancestors = None
    if review.plan.fix_history:
        last = review.plan.fix_history[-1].to_fingerprint
        previous = get_map(last, review.owner)
        if previous:
            with previous.lock:
                ancestors = {**previous.ancestors, last: capture_map(previous)}
    review.plan.fingerprint = remember_map(
        review.plan,
        owner=review.owner,
        source=review.source,
        review_evidence=evidence,
        ancestors=ancestors,
    )
    review.confirmed, review.out_of_date = True, False
    return {**snapshot(reading_id), "fingerprint": review.plan.fingerprint}
