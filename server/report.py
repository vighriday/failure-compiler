"""Read-only reports assembled from confirmed snapshots and scored fix history."""

from copy import deepcopy

from fastapi import APIRouter, HTTPException, Query, Request

from server.checker.scenarios import _instantiate_problems, generate_scenarios
from server.facts import changed_by, statement
from server.grid import count_results, problem_labels
from server.labels import route_label
from server.reading import items_for_plan
from server.session import MapSnapshot, capture_map, get_map

router = APIRouter()


def run_view(fingerprint: str, snapshot: MapSnapshot) -> dict:
    plan = snapshot.plan.checker_data()
    singles, pairs = generate_scenarios(plan)
    return {
        "fingerprint": fingerprint,
        "total": len(singles) + len(pairs),
        "problems": problem_labels(_instantiate_problems(plan)),
        "scenarios": [
            {"scenario_id": row["scenario_id"], "failures": row["failures"]}
            for row in singles + pairs
        ],
        "results": [row.model_dump(mode="json") for row in snapshot.results],
        "count": count_results(snapshot.results, len(singles) + len(pairs)).model_dump(),
    }


def history_for(fingerprint: str, owner: str) -> list[tuple[str, MapSnapshot]]:
    """Follow AppliedFix links through frozen ancestor snapshots, never re-solving."""
    session = get_map(fingerprint, owner)
    if session is None:
        raise HTTPException(404, "Confirmed map not found. Confirm the plan again.")
    with session.lock:
        current = capture_map(session)
        ancestors = dict(session.ancestors)
    if current.results is None:
        raise HTTPException(409, "Finish the first checker run before opening the report.")
    fixes = current.plan.fix_history
    if not fixes:
        return [(fingerprint, current)]
    expected = fixes[0].from_fingerprint
    chain = []
    for fix in fixes:
        if fix.from_fingerprint != expected:
            raise HTTPException(409, "The accepted fix history is incomplete. Run the plan again.")
        previous = ancestors.get(expected)
        if previous is None:
            stored = get_map(expected, owner)
            previous = capture_map(stored) if stored else None
        if previous is None or previous.results is None:
            raise HTTPException(409, "The original run is unavailable. Run the plan again.")
        chain.append((expected, previous))
        expected = fix.to_fingerprint
    if expected != fingerprint:
        # Re-confirmed map edits are part of the current plan, not a fabricated fix.
        previous = ancestors.get(expected)
        if previous is None:
            stored = get_map(expected, owner)
            previous = capture_map(stored) if stored else None
        if previous is None or previous.results is None:
            raise HTTPException(409, "The last accepted fix run is unavailable.")
        chain.append((expected, previous))
    return [*chain, (fingerprint, current)]


def operation_labels(plan, operations) -> list[str]:
    labels = {p.id: p.name for p in [*plan.people, *plan.vehicles]}
    labels.update({r.id: route_label(r.name) for r in plan.routes})
    lines = []
    for op in operations:
        target = labels.get(op.target_id, op.target_id)
        values = op.value if isinstance(op.value, list) else [op.value]
        names = ", ".join(labels.get(value, str(value)) for value in values)
        if op.op in {"add_driver", "add_loader", "replace_drivers", "replace_loaders"}:
            role = "driver" if "driver" in op.op else "loader"
            lines.append(
                f"{target}: {'add' if op.op.startswith('add') else 'set'} {role} cover: {names}."
            )
        elif op.op == "give_spare_key":
            lines.append(f"Give {target} a spare loading-area key; existing holders keep theirs.")
        elif op.op == "move_route":
            lines.append(f"{target} uses {names}.")
        else:
            when = "start" if op.field == "available_from" else "finish"
            lines.append(f"Set {target}'s {when} to {op.value // 60}:{op.value % 60:02d}.")
    return lines


def build_report(chain: list[tuple[str, MapSnapshot]]) -> dict:
    original_fp, original = chain[0]
    fingerprint, current = chain[-1]
    before, after = run_view(original_fp, original), run_view(fingerprint, current)
    labels = {p["id"]: p["label"] for p in before["problems"]}

    def name(scenario):
        return " + ".join(labels.get(pid, pid) for pid in scenario.split("+"))

    dimmed = {}
    for row in original.results:
        if row.state == "dim":
            dimmed.setdefault(row.dim_cause, []).append(name(row.scenario_id))
    batches, accepted = [], []
    for index, (fp, snapshot) in enumerate(chain):
        for batch in snapshot.suggestion_batches:
            batches.append(
                {**deepcopy(batch), "fingerprint": fp, "scenario_label": name(batch["scenario_id"])}
            )
        if index == 0 or index > len(current.plan.fix_history):
            continue
        fix = current.plan.fix_history[index - 1]
        previous = chain[index - 1][1]
        old = {r.scenario_id for r in previous.results if r.state == "cross"}
        new = {r.scenario_id for r in snapshot.results if r.state == "cross"}
        provider = next(
            (
                batch["provider_label"]
                for batch in previous.suggestion_batches
                if any(
                    s["id"] == fix.fix_id
                    and s["operations"] == [op.model_dump(mode="json") for op in fix.operations]
                    for s in batch["suggestions"]
                )
            ),
            "Your change" if fix.origin == "yours" else "AI provider not recorded",
        )
        accepted.append(
            {
                **fix.model_dump(mode="json"),
                "number": index,
                "provider_label": provider,
                "changes": operation_labels(previous.plan, fix.operations),
                "fixes_n": len(old - new),
                "still_broken_n": len(old & new),
                "new_crosses_n": len(new - old),
            }
        )
    evidence = current.review_evidence or original.review_evidence
    rows = evidence.get("items") or items_for_plan(current.plan)
    facts = [
        {
            "id": row["id"],
            "group": row["group"],
            "statement": statement(current.plan, row),
            "source_line": row.get("source_line"),
            "status": row["status"],
            "original_statement": row.get("original_statement"),
            "changed_by_fix": changed_by(current.plan, row),
        }
        for row in rows
    ]
    unknown = {}
    for phase, snapshot in [("Before", original), ("After", current)]:
        for row in snapshot.results:
            if row.state == "qmark":
                unknown.setdefault(name(row.scenario_id), []).append(phase)
    return {
        "fingerprint": fingerprint,
        "source": current.source,
        "read_by": f"{current.plan.ai_meta.provider} / {current.plan.ai_meta.model}",
        "summary": {
            key: evidence.get(key, default)
            for key, default in [("ai_read", len(rows)), ("corrected", 0), ("added", 0)]
        },
        "facts": facts,
        "review_answers": evidence.get("answers", []),
        "before": before,
        "after": after,
        "broken_before": [
            {**row.model_dump(mode="json"), "label": name(row.scenario_id)}
            for row in original.results
            if row.state == "cross"
        ],
        "dimmed_groups": [
            {"weak_spot": labels.get(root, root), "count": len(pairs), "pairs": pairs}
            for root, pairs in dimmed.items()
        ],
        "accepted_fixes": accepted,
        "confirmed_edits_after_fixes": bool(
            current.plan.fix_history and current.plan.fix_history[-1].to_fingerprint != fingerprint
        ),
        "suggestion_batches": batches,
        "not_tested": [
            "Three or more problems at once.",
            "Problem types outside the list: bad weather, someone getting sick partway through, "
            "wrong addresses, running short of food, volunteers arriving late.",
            "Other sizes of the same problems. Only the sizes listed above were tested.",
            "Anything the plan did not mention.",
        ],
        "unknown_results": [
            {"label": label, "phases": phases} for label, phases in unknown.items()
        ],
    }


@router.get("/api/report")
def report(request: Request, fingerprint: str = Query(..., alias="map")) -> dict:
    return build_report(history_for(fingerprint, request.state.owner))
