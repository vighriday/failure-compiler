"""Strict format and reference checks for AI output."""

import pytest

from server.validation.gate import GateError, validate_ai_reading
from tests.validation_helpers import ai_reading_payload


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(GateError, match="Invalid JSON") as exc:
        validate_ai_reading('{"people": [}')
    assert exc.value.field == "$"


def test_extra_fields_are_rejected_with_field_name() -> None:
    payload = ai_reading_payload()
    payload["server_fingerprint"] = "should-not-be-here"
    with pytest.raises(GateError, match="server_fingerprint") as exc:
        validate_ai_reading(payload)
    assert exc.value.field == "server_fingerprint"
    assert exc.value.bad_value == "should-not-be-here"


def test_unknown_person_reference_names_field_and_bad_value() -> None:
    payload = ai_reading_payload()
    route_c = next(route for route in payload["routes"] if route["id"] == "route-c")
    route_c["driver_ids"][0] = "person-dave"
    with pytest.raises(GateError) as exc:
        validate_ai_reading(payload)
    assert str(exc.value) == "Unknown person id 'person-dave' in route-c driver_ids"
    assert exc.value.field == "route-c.driver_ids"
    assert exc.value.bad_value == "person-dave"


def test_duplicate_ids_are_rejected_with_value() -> None:
    payload = ai_reading_payload()
    payload["people"][1]["id"] = payload["people"][0]["id"]
    with pytest.raises(GateError) as exc:
        validate_ai_reading(payload)
    assert str(exc.value) == "Duplicate id 'person-ravi'"
    assert exc.value.bad_value == "person-ravi"


def test_valid_reading_ids_are_normalised_and_references_follow() -> None:
    payload = ai_reading_payload()
    payload["people"][0]["id"] = "p1"
    payload["vehicles"][0]["id"] = "veh_1"
    payload["routes"][0]["id"] = "r-a"
    for route in payload["routes"]:
        route["driver_ids"] = [
            "p1" if value == "person-ravi" else value for value in route["driver_ids"]
        ]
        route["loader_ids"] = [
            "p1" if value == "person-ravi" else value for value in route["loader_ids"]
        ]
        if route["vehicle_id"] == "vehicle-van":
            route["vehicle_id"] = "veh_1"
    result = validate_ai_reading(payload)
    ravi = next(person for person in result.people if person.name == "Ravi")
    van = next(vehicle for vehicle in result.vehicles if vehicle.name == "Van")
    route_a = next(route for route in result.routes if route.name == "A")
    route_b = next(route for route in result.routes if route.name == "B")
    assert ravi.id == "person-ravi"
    assert van.id == "vehicle-van"
    assert route_a.id == "route-a"
    assert route_a.driver_ids[0] == ravi.id
    assert route_a.vehicle_id == "vehicle-car"
    assert route_b.vehicle_id == van.id
