"""Gate, score, reject, and stack the example fixes against all real scenarios."""

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from server.checker.runner import run_checker
from server.facts import changed_by, statement
from server.fixes import SCORED, score_fix
from server.main import app
from server.models import PlanMapData, ScenarioResult
from server.session import SESSIONS, remember_map
from server.validation.models import PlanMap

ROOT = Path(__file__).resolve().parents[1]
VAN_ANITA = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supplies"
JOEL = "volunteer_absent__person-joel"
JOEL_MAYA = "volunteer_absent__person-joel+volunteer_absent__person-maya"
VAN_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"
JOEL_RAVI = "volunteer_absent__person-ravi+volunteer_absent__person-joel"


def truth() -> PlanMap:
    return PlanMap.from_truth_map(
        PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    )


def test_new_single_is_not_described_as_a_hidden_pair(monkeypatch):
    problem = "supply_delivery_late__delivery-supplies"
    monkeypatch.setattr(
        "server.fixes.run_checker",
        lambda _: [
            ScenarioResult(scenario_id=problem, failures=[problem], state="cross"),
            ScenarioResult(scenario_id=VAN_ANITA, failures=VAN_ANITA.split("+"), state="tick"),
        ],
    )
    result = score_fix(
        truth(),
        [],
        VAN_ANITA,
        {
            "id": "classification-test",
            "description": "Move a route",
            "operations": [
                {
                    "op": "move_route",
                    "target_id": "route-c",
                    "field": "vehicle_id",
                    "value": "vehicle-car",
                }
            ],
        },
    ).suggestion
    assert "new single weak spot" in result.rejection_reason


def test_approved_capture_is_unedited_and_retains_primary_failure_history():
    fixture = json.loads((ROOT / "fixtures/example-fixes.json").read_text(encoding="utf-8"))
    assert (
        fixture["label"] == "Suggested by Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)"
    )
    for scenario, record in fixture["cases"].items():
        raw = record["raw"]
        assert raw["provider"] == "groq" and raw["model"] == "openai/gpt-oss-120b"
        assert (
            hashlib.sha256(raw["raw_text"].encode()).hexdigest()
            == fixture["raw_text_sha256"][scenario]
        )
        assert len(json.loads(raw["raw_text"])["fixes"]) == 3
        assert len(record["previous_attempts"]) == 3
        assert any("503" in str(row) for row in record["previous_attempts"])


def test_fix_story_and_fingerprint_chain(monkeypatch) -> None:
    client = TestClient(app)
    plan = truth()
    SCORED.clear()
    original = remember_map(plan, run_checker(plan.checker_data()))

    def suggestions(fingerprint, scenario):
        response = client.post(
            "/api/suggest-fixes",
            json={
                "fingerprint": fingerprint,
                "scenario_id": scenario,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        for fix in payload["suggestions"]:
            if fix["gate_status"] != "passed":
                assert not fix["eligible"] and not fix["scenario_results"]
                continue
            assert fix["fixes_n"] + fix["still_broken_n"] == sum(
                r.state == "cross" for r in SESSIONS[fingerprint].results
            )
            assert len(fix["scenario_results"]) == 100
        return payload

    def apply(fingerprint, scenario, fix_id, expected=200):
        response = client.post(
            "/api/apply-fix",
            json={
                "fingerprint": fingerprint,
                "scenario_id": scenario,
                "fix_id": fix_id,
            },
        )
        assert response.status_code == expected, response.text
        return response.json()

    van = suggestions(original, VAN_ANITA)
    assert not van["placeholder"] and van["source"] == "saved" and not van["can_retry"]
    assert van["suggested_by"] == "Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)"
    reason = van["route_reasons"]["route-c"]
    assert reason.startswith("Van back 10:45. Loading team gone.")
    assert "Anita left 10:30" in reason
    assert "Maya leaves 10:45" in reason
    assert "Joel left 10:30" in reason
    assert all(r["state"] == "tick" for r in van["alone_results"])
    hours, driver, car = van["suggestions"]
    assert all(not fix["eligible"] for fix in van["suggestions"])
    assert "11:00" in hours["rejection_reason"] and "12:00" in hours["rejection_reason"]
    assert "shortens" in hours["rejection_reason"]
    assert "Ravi is already a driver for Route C" in driver["rejection_reason"]
    assert "10:45" in driver["rejection_reason"]
    assert car["fixes_n"] == 3 and car["new_crosses_n"] == 1
    assert "new single weak spot" in car["rejection_reason"]
    apply(original, VAN_ANITA, driver["id"], expected=409)
    assert (
        client.post(
            "/api/suggest-fixes",
            json={"fingerprint": original, "scenario_id": VAN_ANITA, "retry": True},
        ).status_code
        == 409
    )
    with monkeypatch.context() as cached:
        cached.setattr(
            "server.fixes.run_checker",
            lambda _: (_ for _ in ()).throw(
                AssertionError("cached suggestions must not solve again")
            ),
        )
        assert suggestions(original, VAN_ANITA) == van
    absent = suggestions(original, VAN_ABSENT)
    sam = absent["suggestions"][1]
    assert (sam["fixes_n"], sam["new_crosses_n"], sam["eligible"]) == (2, 0, True)
    assert absent["suggestions"][2]["gate_status"] == "couldnt_apply"
    first = apply(original, VAN_ABSENT, sam["id"])
    fp1 = first["fingerprint"]
    assert fp1 != original

    joel = suggestions(fp1, JOEL)
    assert set(joel["route_reasons"].values()) == {"Nobody can open the loading area."}
    one = joel["suggestions"][0]
    assert (one["fixes_n"], one["still_broken_n"], one["new_crosses_n"], one["eligible"]) == (
        1,
        1,
        1,
        False,
    )
    assert one["new_crosses"] == [JOEL_RAVI]
    assert "Joel absent + Ravi absent" in one["rejection_reason"]
    assert (
        next(r for r in one["scenario_results"] if r["scenario_id"] == JOEL_RAVI)["state"]
        == "cross"
    )
    apply(fp1, JOEL, one["id"], expected=409)

    def own_change(fp, scenario, operations):
        response = client.post(
            "/api/test-change",
            json={"fingerprint": fp, "scenario_id": scenario, "operations": operations},
        )
        assert response.status_code == 200, response.text
        fix = response.json()
        assert fix["origin"] == "yours" and fix["gate_status"] == "passed"
        assert len(fix["scenario_results"]) == 100
        return fix

    keys = own_change(
        fp1,
        JOEL,
        [
            {
                "op": "give_spare_key",
                "target_id": f"person-{name}",
                "field": "holds_key",
                "value": True,
            }
            for name in ("maya", "sam")
        ],
    )
    assert (keys["fixes_n"], keys["still_broken_n"], keys["new_crosses_n"], keys["eligible"]) == (
        1,
        1,
        0,
        True,
    )
    # Reopening a case keeps the coordinator's scored card; it doesn't request AI.
    assert suggestions(fp1, JOEL)["suggestions"][-1]["id"] == keys["id"]
    second = apply(fp1, JOEL, keys["id"])
    fp2 = second["fingerprint"]
    truck = own_change(
        fp2,
        TRUCK_RAVI,
        [
            {
                "op": "add_driver",
                "target_id": "route-a",
                "field": "driver_ids",
                "value": "person-sam",
            }
        ],
    )
    assert (
        truck["fixes_n"],
        truck["still_broken_n"],
        truck["new_crosses_n"],
        truck["eligible"],
    ) == (1, 0, 0, True)
    assert truck["description"] == "Sam backs up Route A."
    final = apply(fp2, TRUCK_RAVI, truck["id"])
    final_fp = final["fingerprint"]
    assert len(SESSIONS[final_fp].results) == 100
    assert all(r.state == "tick" for r in SESSIONS[final_fp].results)
    chain = final["plan_map"]["fix_history"]
    assert [fix["origin"] for fix in chain] == ["ai", "yours", "yours"]
    assert [(fix["from_fingerprint"], fix["to_fingerprint"]) for fix in chain] == [
        (original, fp1),
        (fp1, fp2),
        (fp2, final_fp),
    ]
    assert next(p for p in final["plan_map"]["people"] if p["name"] == "Joel")["holds_key"]
    assert next(r for r in final["plan_map"]["routes"] if r["name"] == "C")["changed_by_fix"] == 1
    # Reading sentences must follow the accepted map rather than stale extraction text.
    final_plan = SESSIONS[final_fp].plan
    key_item = {"entity_type": "person", "entity_id": "person-joel", "field": "holds_key"}
    assert statement(final_plan, key_item) == "Joel, Maya and Sam hold loading-area keys."
    assert changed_by(final_plan, key_item) == 2
    for route_id, fix_number in [("route-c", 1), ("route-a", 3)]:
        route_item = {"entity_type": "route", "entity_id": route_id, "field": "route"}
        assert "Sam" in statement(final_plan, route_item)
        assert changed_by(final_plan, route_item) == fix_number


def test_bad_fix_is_couldnt_apply_and_names_the_bad_reference() -> None:
    plan = truth()
    invalid = score_fix(
        plan,
        [],
        VAN_ANITA,
        {
            "id": "bad-driver",
            "description": "Invent a backup",
            "operations": [
                {
                    "op": "add_driver",
                    "target_id": "route-c",
                    "field": "driver_ids",
                    "value": "person-dave",
                }
            ],
        },
    ).suggestion
    assert invalid.gate_status == "couldnt_apply"
    assert "Unknown person id 'person-dave' in route-c driver_ids" in invalid.gate_reason
    assert invalid.scenario_results == []
    assert not invalid.eligible


def test_client_cannot_supply_its_own_eligible_flag_or_operations() -> None:
    response = TestClient(app).post(
        "/api/apply-fix",
        json={
            "fingerprint": "arbitrary",
            "scenario_id": JOEL,
            "fix_id": "unscored",
            "eligible": True,
            "operations": [],
        },
    )
    assert response.status_code == 422
