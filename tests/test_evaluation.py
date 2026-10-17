"""Names cannot inflate or lower the new measurement; full checker outcomes matter first."""

from server.evaluation import align_entities, compare_reading, rank_providers
from tests.validation_helpers import confirmed_truth_map


def test_alignment_ignores_labels_and_compares_all_result_fields():
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
