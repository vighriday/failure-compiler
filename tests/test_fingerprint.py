"""Fingerprints depend only on canonical checker inputs."""

from server.validation.fingerprint import fingerprint_plan_map
from server.validation.gate import normalise_plan_map_ids
from tests.validation_helpers import confirmed_truth_map


def _rename_to_ai_ids(plan):
    people_map = {item.id: f"p{i + 1}" for i, item in enumerate(plan.people)}
    vehicle_map = {item.id: f"veh_{i + 1}" for i, item in enumerate(plan.vehicles)}
    place_map = {item.id: f"loc_{i + 1}" for i, item in enumerate(plan.places)}
    delivery_map = {item.id: f"del_{i + 1}" for i, item in enumerate(plan.deliveries)}
    route_map = {item.id: f"r-{item.name.lower()}" for item in plan.routes}
    return plan.model_copy(
        update={
            "people": [item.model_copy(update={"id": people_map[item.id]}) for item in plan.people],
            "vehicles": [
                item.model_copy(update={"id": vehicle_map[item.id]}) for item in plan.vehicles
            ],
            "places": [item.model_copy(update={"id": place_map[item.id]}) for item in plan.places],
            "deliveries": [
                item.model_copy(
                    update={"id": delivery_map[item.id], "place_id": place_map[item.place_id]}
                )
                for item in plan.deliveries
            ],
            "routes": [
                item.model_copy(
                    update={
                        "id": route_map[item.id],
                        "vehicle_id": vehicle_map[item.vehicle_id],
                        "driver_ids": [people_map[value] for value in item.driver_ids],
                        "loader_ids": [people_map[value] for value in item.loader_ids],
                    }
                )
                for item in plan.routes
            ],
            "questions": [
                item.model_copy(update={"item_id": route_map.get(item.item_id, item.item_id)})
                for item in plan.questions
            ],
            "fingerprint": None,
        }
    )


def test_shuffled_ai_ids_normalise_to_the_truth_map_fingerprint() -> None:
    truth = confirmed_truth_map()
    renamed = _rename_to_ai_ids(truth)
    varied_form = renamed.model_copy(
        update={
            "people": renamed.people[2:] + renamed.people[:2],
            "vehicles": list(reversed(renamed.vehicles)),
            "routes": list(reversed(renamed.routes)),
            # Driver order retains its meaningful primary-first order.
        }
    )
    normalised = normalise_plan_map_ids(varied_form)
    assert fingerprint_plan_map(normalised) == fingerprint_plan_map(truth)


def test_checker_input_change_changes_fingerprint() -> None:
    truth = confirmed_truth_map()
    sizes = truth.problem_sizes.copy()
    sizes["vehicle_returns_late"] = 45
    changed = truth.model_copy(update={"problem_sizes": sizes})
    assert fingerprint_plan_map(changed) != fingerprint_plan_map(truth)


def test_loader_order_does_not_change_fingerprint_but_driver_order_does() -> None:
    truth = confirmed_truth_map()
    reordered = truth.model_copy(deep=True)
    for route in reordered.routes:
        route.loader_ids.reverse()
    assert fingerprint_plan_map(reordered) == fingerprint_plan_map(truth)
    reordered.routes[0].driver_ids.reverse()
    assert fingerprint_plan_map(reordered) != fingerprint_plan_map(truth)


def test_status_ai_metadata_and_source_lines_do_not_change_fingerprint() -> None:
    truth = confirmed_truth_map()
    changed = truth.model_copy(
        update={
            "ai_meta": truth.ai_meta.model_copy(
                update={
                    "provider": "different-provider",
                    "model": "different-model",
                    "timestamp": "later",
                }
            ),
            "people": [
                item.model_copy(update={"status": "corrected", "source_line": "different line"})
                for item in truth.people
            ],
            "routes": [
                item.model_copy(
                    update={"status": "unconfirmed", "source_line": "changed route line"}
                )
                for item in truth.routes
            ],
            "finish_time_source": "different finish-time statement",
        }
    )
    assert fingerprint_plan_map(changed) == fingerprint_plan_map(truth)
