"""Compare readings by aligned identities and complete checker outcomes, never display labels."""

import re
from statistics import pvariance

from server.checker.runner import _run_one, run_checker
from server.checker.scenarios import _instantiate_problems, generate_scenarios
from server.models import ScenarioResult
from server.ordering import canonical_order
from server.validation.models import PlanMap

COLLECTIONS = ("people", "vehicles", "places", "deliveries", "routes")


def route_letter(entity) -> str:
    for value in (entity.name, entity.id):
        match = re.fullmatch(r"(?:route[\s_-]*)?([a-z])", value.casefold())
        if match:
            return match[1]
    return ""


def align_entities(plan: PlanMap, truth: PlanMap) -> tuple[PlanMap, dict, list[dict]]:
    """Align roles without changing any measured values or borrowing missing truth entities.

    Route letters identify routes. The loading place aligns by its exclusive-loading role.
    Vehicles align by the routes they serve; people by primary driver, key-holder or ordered
    driver roles. Existing identities are retained. Labels are never scored or used to choose
    a match. Ambiguity is reported rather than resolved by maximising the score.
    """
    mapping, unmatched = {}, []
    for collection in ("routes", "people", "vehicles", "places", "deliveries"):
        actual, expected = getattr(plan, collection), getattr(truth, collection)
        used = set()
        entities = actual
        if collection == "people":
            # Resolve distinctive roles before a lone remaining backup volunteer.
            entities = sorted(
                actual,
                key=lambda person: (
                    not (
                        person.holds_key
                        or any(route.driver_ids[:1] == [person.id] for route in plan.routes)
                    )
                ),
            )
        for entity in entities:
            candidates = [target for target in expected if target.id == entity.id]
            if collection == "routes":
                candidates = [
                    target
                    for target in expected
                    if route_letter(entity) and route_letter(entity) == route_letter(target)
                ]
            if not candidates and collection == "places" and entity.one_vehicle_at_a_time:
                candidates = [target for target in expected if target.one_vehicle_at_a_time]
            if (
                not candidates
                and collection in {"places", "deliveries"}
                and len(actual) == len(expected) == 1
            ):
                candidates = expected
            if not candidates and collection in {"vehicles", "people"}:

                def roles(candidate, routes, reading):
                    result = []
                    for route in routes:
                        route_id = mapping.get(route.id, route.id) if reading else route.id
                        if collection == "vehicles" and route.vehicle_id == candidate.id:
                            result.append((route_id, 0))
                        if collection == "people":
                            result.extend(
                                (route_id, index)
                                for index, person_id in enumerate(route.driver_ids)
                                if person_id == candidate.id
                            )
                    return sorted(result)

                signature = roles(entity, plan.routes, True)
                primary = [role for role in signature if role[1] == 0]
                if collection == "people" and primary:
                    candidates = [
                        target
                        for target in expected
                        if primary
                        == [role for role in roles(target, truth.routes, False) if role[1] == 0]
                    ]
                if not candidates and collection == "people" and entity.holds_key:
                    candidates = [target for target in expected if target.holds_key]
                if not candidates:
                    candidates = [
                        target
                        for target in expected
                        if signature and signature == roles(target, truth.routes, False)
                    ]
            if not candidates and len(actual) == len(expected):
                remaining = [target for target in expected if target.id not in used]
                # Only one remaining identity is unambiguous. Never discard an extra entity.
                if len(remaining) == 1:
                    candidates = remaining
            candidates = [target for target in candidates if target.id not in used]
            if len(candidates) == 1:
                mapping[entity.id] = candidates[0].id
                used.add(candidates[0].id)
            else:
                unmatched.append(
                    {
                        "collection": collection,
                        "id": entity.id,
                        "reason": "Ambiguous or unmatched role",
                    }
                )
        for entity in expected:
            if entity.id not in used:
                unmatched.append(
                    {"collection": collection, "id": entity.id, "reason": "Missing role"}
                )
    result = plan.model_copy(deep=True)
    for collection in COLLECTIONS:
        for entity in getattr(result, collection):
            entity.id = mapping.get(entity.id, entity.id)
            if collection == "routes":
                entity.vehicle_id = mapping.get(entity.vehicle_id, entity.vehicle_id)
                entity.driver_ids = [mapping.get(value, value) for value in entity.driver_ids]
                entity.loader_ids = [mapping.get(value, value) for value in entity.loader_ids]
            if collection == "deliveries":
                entity.place_id = mapping.get(entity.place_id, entity.place_id)
    result.questions = []  # Review questions are not checker inputs.
    return canonical_order(result), mapping, unmatched


def checker_fields(plan: PlanMap) -> dict:
    data = plan.checker_data()
    fields = {"finish_time": data.finish_time}
    for collection in COLLECTIONS:
        for entity in getattr(data, collection):
            fields.update(
                {
                    f"{collection}.{entity.id}.{field}": value
                    for field, value in entity.model_dump().items()
                    if field not in {"id", "name"}
                }
            )
    fields.update({f"problem_sizes.{key}": value for key, value in data.problem_sizes.items()})
    return fields


def reference_results(plan: PlanMap, truth: PlanMap) -> list[ScenarioResult]:
    """Run the truth matrix even when extraction omitted a problem-bearing entity.

    A failure targeting an omitted entity is a no-op in the existing solver; the missing role
    remains an explicit field mismatch. No truth value or entity is inserted into the reading.
    Labels are canonicalised only for comparing the result's human-readable cost sentence.
    """
    candidate = canonical_order(plan.checker_data())
    labels = {
        entity.id: entity.name
        for collection in COLLECTIONS
        for entity in getattr(truth, collection)
    }
    for collection in COLLECTIONS:
        for entity in getattr(candidate, collection):
            entity.name = labels.get(entity.id, entity.id)
    reference = truth.checker_data()
    problems = {problem["id"]: problem for problem in _instantiate_problems(reference)}
    singles, pairs = generate_scenarios(reference)
    results, by_id = [], {}
    for scenario in singles + pairs:
        broken = next(
            (
                by_id[value]
                for value in scenario["failures"]
                if value in by_id and by_id[value].state == "cross"
            ),
            None,
        )
        if len(scenario["failures"]) == 2 and broken:
            result = ScenarioResult(
                scenario_id=scenario["scenario_id"],
                failures=scenario["failures"],
                state="dim",
                dim_cause=broken.scenario_id,
                lateness_minutes=broken.lateness_minutes,
                human_cost=broken.human_cost,
            )
        else:
            result = _run_one(candidate, scenario, problems)
        results.append(result)
        by_id[result.scenario_id] = result
    return results


def compare_reading(plan: PlanMap, truth: PlanMap) -> dict:
    aligned, mapping, unmatched = align_entities(plan, truth)
    wanted, actual = checker_fields(truth), checker_fields(aligned)
    mismatches = [
        {
            "field": key,
            "expected": wanted.get(key, "<not in truth>"),
            "actual": actual.get(key, "<missing>"),
        }
        for key in sorted(wanted.keys() | actual.keys())
        if wanted.get(key) != actual.get(key)
    ]
    matches = sum(key in actual and actual[key] == value for key, value in wanted.items())
    expected_results = run_checker(truth.checker_data())
    actual_results = reference_results(aligned, truth)
    different = [
        expected.scenario_id
        for expected, current in zip(expected_results, actual_results)
        if expected != current
    ]
    name_differences = [
        {"collection": collection, "id": entity.id, "actual": entity.name, "expected": target.name}
        for collection in COLLECTIONS
        for entity in getattr(aligned, collection)
        for target in getattr(truth, collection)
        if entity.id == target.id and entity.name != target.name
    ]
    compared_fields = len(wanted.keys() | actual.keys())
    return {
        "aligned_field_matches": matches,
        "truth_fields": len(wanted),
        "compared_fields": compared_fields,
        "aligned_field_match_percent": round(100 * matches / compared_fields, 2),
        "checker_matches": len(expected_results) - len(different),
        "checker_total": len(expected_results),
        "different_scenarios": different,
        "mismatches": mismatches,
        "naming_only": name_differences,
        "alignment": mapping,
        "unmatched_roles": unmatched,
    }


def rank_providers(readings: list[dict]) -> list[dict]:
    ranks = []
    for provider in sorted({row["provider"] for row in readings}):
        rows = [row for row in readings if row["provider"] == provider and "checker_matches" in row]
        if len(rows) != 3:
            continue
        outcomes = [row["checker_matches"] for row in rows]
        fields = [row["aligned_field_match_percent"] for row in rows]
        ranks.append(
            {
                "provider": provider,
                "checker_mean": sum(outcomes) / 3,
                "aligned_field_mean": sum(fields) / 3,
                "consistency_variance": pvariance(outcomes) + pvariance(fields),
                "total_tokens": sum(row["raw"]["total_tokens"] for row in rows),
            }
        )
    return sorted(
        ranks,
        key=lambda row: (
            -row["checker_mean"],
            -row["aligned_field_mean"],
            row["consistency_variance"],
            row["total_tokens"],
        ),
    )
