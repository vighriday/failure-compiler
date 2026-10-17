"""Prove correctability by replaying only the same actions exposed by the review UI."""

from fastapi import HTTPException

from server.checker.scenarios import generate_scenarios
from server.evaluation import COLLECTIONS, align_entities, checker_fields, compare_reading
from server.reading import items_for_plan, questions_for_plan
from server.review import ACCEPTED, REVIEWS, confirm_review, create_review, update_review
from server.validation.models import PlanMap


def correction_audit(plan: PlanMap, truth: PlanMap, *, place_aliases: dict | None = None) -> dict:
    before = compare_reading(plan, truth)
    aligned, mapping, unmatched = align_entities(plan, truth)
    inverse = {target: source for source, target in mapping.items()}
    unsupported = []
    items = items_for_plan(plan)
    state = create_review(plan, items, questions_for_plan(plan, items))
    reading_id = state["reading_id"]
    actions, data_actions = [], []

    def act(action, **values):
        nonlocal state
        request = {"action": action, **values}
        state = update_review({"reading_id": reading_id, **request})
        actions.append(request)
        if (
            action in {"correct", "problem_size"}
            or action == "answer"
            and any(
                q["id"] == values.get("question_id") and q.get("kind") for q in state["questions"]
            )
        ):
            data_actions.append(request)

    try:
        # These are explicit review choices supplied by the caller, never inferred from truth.
        for source_id, target_id in (place_aliases or {}).items():
            act(
                "answer",
                question_id=f"rule-{source_id}-identity",
                value={
                    "choice": "Same place as another listing",
                    "place_id": target_id,
                },
            )
        aligned, mapping, unmatched = align_entities(REVIEWS[reading_id].plan, truth)
        inverse = {target: source for source, target in mapping.items()}
        unsupported = [
            row
            for row in unmatched
            if not (row["collection"] == "deliveries" and row["reason"] == "Missing role")
        ]
        for delivery in truth.deliveries:
            if delivery.id in inverse:
                continue
            place_id = inverse.get(delivery.place_id)
            question = next(
                (
                    q
                    for q in state["questions"]
                    if q.get("kind") == "missing_delivery" and q["entity_id"] == place_id
                ),
                None,
            )
            if not question:
                unsupported.append(
                    {
                        "collection": "deliveries",
                        "id": delivery.id,
                        "reason": "No missing-delivery rule question",
                    }
                )
                continue
            act(
                "answer",
                question_id=question["id"],
                value={
                    "choice": "Add a delivery",
                    "arrives_at": delivery.arrives_at,
                    "place_id": place_id,
                },
            )
        current = REVIEWS[reading_id].plan
        aligned, mapping, _ = align_entities(current, truth)
        inverse = {target: source for source, target in mapping.items()}
        for collection in COLLECTIONS:
            for expected in getattr(truth.checker_data(), collection):
                actual_id = inverse.get(expected.id)
                if not actual_id:
                    continue
                actual = next(
                    entity for entity in getattr(current, collection) if entity.id == actual_id
                )
                comparable = next(
                    entity for entity in getattr(aligned, collection) if entity.id == expected.id
                )
                for field, value in expected.model_dump().items():
                    if field in {"id", "name"} or getattr(comparable, field) == value:
                        continue
                    control_row = next(
                        (
                            row
                            for row in state["items"]
                            if row["entity_id"] == actual.id
                            and any(control["field"] == field for control in row["controls"])
                        ),
                        None,
                    )
                    if control_row is None:
                        unsupported.append(
                            {
                                "collection": collection,
                                "id": actual.id,
                                "field": field,
                                "reason": "No constrained control",
                            }
                        )
                        continue
                    answer = (
                        [inverse.get(pid, pid) for pid in value]
                        if isinstance(value, list)
                        else (inverse.get(value, value) if isinstance(value, str) else value)
                    )
                    question = next(
                        (
                            q
                            for q in state["questions"]
                            if q.get("kind") == "missing_assignment"
                            and q.get("entity_id") == actual.id
                            and q["field"] == field
                        ),
                        None,
                    )
                    if question and not state["answers"].get(question["id"]):
                        act("answer", question_id=question["id"], value=answer)
                    else:
                        act("correct", item_id=control_row["id"], field=field, value=answer)
        if state["plan_map"]["finish_time"] != truth.finish_time:
            question = next(
                (q for q in state["questions"] if q.get("kind") == "missing_finish"), None
            )
            if question:
                act("answer", question_id=question["id"], value=truth.finish_time)
            else:
                act("correct", item_id="finish-time", field="finish_time", value=truth.finish_time)
        for field, value in truth.problem_sizes.items():
            if state["plan_map"]["problem_sizes"].get(field) != value:
                act("problem_size", field=field, value=value)
        if not unsupported:
            act("confirm_all")
            for row in list(state["items"]):
                if row["status"] not in ACCEPTED:
                    act("confirm_item", item_id=row["id"])
            for question in list(state["questions"]):
                if question["id"] not in state["answers"]:
                    if question.get("kind"):
                        unsupported.append(
                            {"question_id": question["id"], "reason": "Unanswered rule"}
                        )
                    else:
                        act("answer", question_id=question["id"], value="Use the reviewed details")
            if not unsupported:
                state = confirm_review({"reading_id": reading_id})
    except HTTPException as error:
        unsupported.append({"reason": str(error.detail)})
    corrected = REVIEWS[reading_id].plan
    after = compare_reading(corrected, truth)
    singles, pairs = generate_scenarios(corrected.checker_data())
    remaining_fields = {row["field"] for row in after["mismatches"]}
    correctable = (
        not unsupported
        and after["aligned_field_match_percent"] == 100
        and after["checker_matches"] == after["checker_total"] == 100
        and len(singles) + len(pairs) == 100
    )
    return {
        "correctable": correctable,
        "before": before,
        "after": after,
        "actual_scenario_count": len(singles) + len(pairs),
        "naming_only": before["naming_only"],
        "not_fixable": unsupported,
        "fixed_by_control": [
            row for row in before["mismatches"] if row["field"] not in remaining_fields
        ],
        "scripted_corrections": data_actions,
        "actions": actions,
        "corrected_plan": corrected.model_dump(mode="json"),
        "aligned_inputs": checker_fields(align_entities(corrected, truth)[0]),
    }
