"""Names and equal-quality schedules cannot change the locked verdict measurement."""

from server.evaluation import align_entities, compare_reading, rank_providers
from tests.validation_helpers import confirmed_truth_map


def test_alignment_ignores_labels_and_compares_locked_verdict_fields():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    reading.routes[0].id = "route-route-a"
    reading.routes[0].name = "Route A"
    reading.places[0].name = "Hall"
    reading.vehicles[0].name = "van"
    result = compare_reading(reading, truth)
    assert result["aligned_field_match_percent"] == 100
    assert result["checker_matches"] == result["checker_total"] == 100
    assert not result["mismatches"]
    assert len(result["naming_only"]) == 3


def test_loader_order_is_a_set_input_but_driver_order_remains_significant():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    for route in reading.routes:
        route.loader_ids.reverse()
    result = compare_reading(reading, truth)
    assert result["aligned_field_match_percent"] == 100
    assert result["checker_matches"] == 100
    reading.routes[0].driver_ids.reverse()
    result = compare_reading(reading, truth)
    assert result["aligned_field_match_percent"] < 100
    assert any(row["field"] == "routes.route-a.driver_ids" for row in result["mismatches"])


def test_schedule_metadata_is_excluded_but_each_locked_verdict_field_is_scored(monkeypatch):
    from server import evaluation

    truth = confirmed_truth_map()
    results = evaluation.run_checker(truth.checker_data())
    variants = [
        result.model_copy(
            update={
                "timeline": [],
                "dim_cause": "irrelevant diagnostic",
                "lower_bound_minutes": 999,
                "map_fingerprint": "different metadata",
            }
        )
        for result in results
    ]
    monkeypatch.setattr(evaluation, "run_checker", lambda _: results)
    monkeypatch.setattr(evaluation, "reference_results", lambda *_: variants)
    assert compare_reading(truth, truth)["checker_matches"] == 100
    for field, value in (
        ("state", "qmark"),
        ("lateness_minutes", 999),
        ("human_cost", "Different"),
    ):
        variants[0] = results[0].model_copy(update={field: value})
        assert compare_reading(truth, truth)["different_scenarios"] == [results[0].scenario_id]
        variants[0] = results[0]


def test_missing_delivery_is_not_borrowed_from_truth_and_all_100_are_run():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    reading.deliveries = []
    aligned, _, missing = align_entities(reading, truth)
    assert aligned.deliveries == []
    assert any(row["collection"] == "deliveries" for row in missing)
    result = compare_reading(reading, truth)
    assert result["checker_total"] == 100
    assert result["checker_matches"] < 100
    assert any(row["field"].startswith("deliveries.") for row in result["mismatches"])


def test_alignment_uses_roles_when_all_entity_ids_and_labels_change():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    mapping = {}
    for collection in ("people", "vehicles", "places", "deliveries", "routes"):
        for index, entity in enumerate(getattr(reading, collection)):
            mapping[entity.id] = f"{collection}-{index}"
            entity.id = mapping[entity.id]
            if collection != "routes":
                entity.name = f"Label {collection} {index}"
            else:
                entity.name = f"Route {entity.name}"
    for route in reading.routes:
        route.vehicle_id = mapping[route.vehicle_id]
        route.driver_ids = [mapping[value] for value in route.driver_ids]
        route.loader_ids = [mapping[value] for value in route.loader_ids]
    for delivery in reading.deliveries:
        delivery.place_id = mapping[delivery.place_id]
    result = compare_reading(reading, truth)
    assert not result["unmatched_roles"]
    assert result["aligned_field_match_percent"] == 100
    assert result["checker_matches"] == 100


def test_loading_role_aligns_with_an_extra_non_loading_place():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    reading.places[0].id = "place-bay"
    reading.places[0].name = "Bay"
    reading.deliveries[0].place_id = "place-bay"
    reading.places.insert(
        0,
        reading.places[0].model_copy(
            update={"id": "place-hall", "name": "Hall", "one_vehicle_at_a_time": False}
        ),
    )
    result = compare_reading(reading, truth)
    assert result["alignment"]["place-bay"] == "place-loading-area"
    assert result["checker_matches"] == 100
    assert result["compared_fields"] == 53
    assert len(result["mismatches"]) == 3


def test_extra_checker_inputs_are_included_in_the_field_score():
    truth = confirmed_truth_map()
    reading = truth.model_copy(deep=True)
    reading.vehicles.append(
        reading.vehicles[0].model_copy(update={"id": "vehicle-extra", "name": "Extra"})
    )
    result = compare_reading(reading, truth)
    assert result["compared_fields"] > result["truth_fields"]
    assert result["aligned_field_match_percent"] < 100


def test_provider_ranking_uses_results_then_fields_then_consistency_then_tokens():
    def rows(provider, outcomes, fields=90, tokens=100):
        return [
            {
                "provider": provider,
                "checker_matches": outcome,
                "aligned_field_match_percent": fields,
                "raw": {"total_tokens": tokens},
            }
            for outcome in outcomes
        ]

    assert rank_providers(rows("a", [90] * 3, 100) + rows("b", [91] * 3, 80))[0]["provider"] == "b"
    assert rank_providers(rows("a", [90] * 3, 90) + rows("b", [90] * 3, 91))[0]["provider"] == "b"
    assert (
        rank_providers(rows("a", [89, 90, 91]) + rows("b", [90] * 3, tokens=200))[0]["provider"]
        == "b"
    )
    assert (
        rank_providers(rows("a", [90] * 3, tokens=200) + rows("b", [90] * 3))[0]["provider"] == "b"
    )
