"""Review unused place listings explicitly; preserve the source and support undo."""

from copy import deepcopy

from fastapi import HTTPException

from server.validation.models import MapPlace


def place_has_activity(plan, place_id):
    place = next((place for place in plan.places if place.id == place_id), None)
    return bool(
        place
        and (
            place.needs_key
            or place.one_vehicle_at_a_time
            or any(delivery.place_id == place_id for delivery in plan.deliveries)
        )
    )


def sync_place_questions(review):
    review.questions[:] = [
        q
        for q in review.questions
        if not (
            q.get("kind") == "place_identity"
            and not q.get("merge")
            and q["id"] not in review.answers
            and place_has_activity(review.plan, q["entity_id"])
        )
    ]
    active = [place for place in review.plan.places if place_has_activity(review.plan, place.id)]
    if not active:
        return
    for place in review.plan.places:
        if place_has_activity(review.plan, place.id):
            continue
        question_id = f"rule-{place.id}-identity"
        if any(question["id"] == question_id for question in review.questions):
            continue
        row = next((row for row in review.items if row["entity_id"] == place.id), None)
        review.questions.append(
            {
                "id": question_id,
                "item_id": row["id"] if row else place.id,
                "entity_id": place.id,
                "field": "identity",
                "kind": "place_identity",
                "question_text": f"{place.name} has no loading activity or supply arrival listed. "
                "Is it separate, or the same place as another listing?",
                "source_line": place.source_line or None,
                "choices": ["Keep as a separate place", "Same place as another listing"],
            }
        )


def _invalidate(review, target_id):
    review.plan.fingerprint = None
    review.confirmed, review.out_of_date = False, True
    for row in review.items:
        if row["entity_id"] == target_id or (
            row["entity_type"] == "route" and row["status"] in {"confirmed", "corrected", "added"}
        ):
            row["status"] = "stale"


def answer_place_question(review, question, value):
    source_id = question["entity_id"]
    source = next((place for place in review.plan.places if place.id == source_id), None)
    if source is None or question.get("merge") or place_has_activity(review.plan, source_id):
        raise HTTPException(422, f"Place identity for {source_id!r} must be reopened or reviewed")
    choice = value.get("choice") if isinstance(value, dict) else value
    if choice == "Keep as a separate place":
        review.answers[question["id"]] = choice
        return
    target_id = value.get("place_id") if isinstance(value, dict) else None
    target = next((place for place in review.plan.places if place.id == target_id), None)
    if (
        choice != "Same place as another listing"
        or target is None
        or source_id == target_id
        or not place_has_activity(review.plan, target_id)
    ):
        raise HTTPException(
            422, f"Invalid place_id {target_id!r}; choose a listed loading or supply place"
        )
    target_row = next(row for row in review.items if row["entity_id"] == target_id)
    removed = [deepcopy(row) for row in review.items if row["entity_id"] == source_id]
    removed_ids = {row["id"] for row in removed}
    retargeted = [
        {"id": q["id"], "item_id": q["item_id"]}
        for q in review.questions
        if q is not question and q["item_id"] in removed_ids
    ]
    ai_questions = [
        index for index, q in enumerate(review.plan.questions) if q.item_id == source_id
    ]
    question["merge"] = {
        "source": source.model_dump(mode="json"),
        "items": removed,
        "place_index": review.plan.places.index(source),
        "item_indices": [i for i, row in enumerate(review.items) if row["entity_id"] == source_id],
        "target_id": target_id,
        "review_questions": retargeted,
        "ai_questions": ai_questions,
    }
    for q in review.questions:
        if q["id"] in {old["id"] for old in retargeted}:
            q["item_id"] = target_row["id"]
            review.answers.pop(q["id"], None)
    for index in ai_questions:
        review.plan.questions[index].item_id = target_id
    review.plan.places = [place for place in review.plan.places if place.id != source_id]
    review.items = [row for row in review.items if row["entity_id"] != source_id]
    review.answers[question["id"]] = (
        f"{source.name} is the same place as {target.name}. Use {target.name}'s reviewed details."
    )
    _invalidate(review, target_id)


def reopen_place_question(review, question):
    merge = question.pop("merge", None)
    if merge:
        source = MapPlace.model_validate(merge["source"])
        review.plan.places.insert(merge["place_index"], source)
        for index, row in zip(merge["item_indices"], merge["items"]):
            review.items.insert(index, {**row, "status": "stale"})
        for q in review.questions:
            original = next(
                (old for old in merge["review_questions"] if old["id"] == q["id"]), None
            )
            if original:
                q["item_id"] = original["item_id"]
                review.answers.pop(q["id"], None)
        for index in merge["ai_questions"]:
            review.plan.questions[index].item_id = source.id
        _invalidate(review, merge["target_id"])
