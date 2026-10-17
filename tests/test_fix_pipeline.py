"""Gate, score, reject, and stack the example fixes against all real scenarios."""

from pathlib import Path

from fastapi.testclient import TestClient

from server.checker.runner import run_checker
from server.facts import changed_by, statement
from server.fixes import SCORED, score_fix
from server.main import app
from server.models import PlanMapData
from server.session import SESSIONS, remember_map
from server.validation.models import PlanMap

ROOT = Path(__file__).resolve().parents[1]
VAN_ANITA = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supplies"
JOEL = "volunteer_absent__person-joel"
JOEL_MAYA = "volunteer_absent__person-joel+volunteer_absent__person-maya"


def truth() -> PlanMap:
    return PlanMap.from_truth_map(
        PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
    )


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
    reason = van["route_reasons"]["route-c"]
    assert reason.startswith("Van back 10:45. Loading team gone.")
    assert "Anita left 10:30" in reason
    assert "Maya leaves 10:45" in reason
    assert "Joel left 10:30" in reason
    assert all(r["state"] == "tick" for r in van["alone_results"])
    maya, sam = van["suggestions"]
    assert (maya["fixes_n"], maya["eligible"]) == (0, False)
    assert maya["rejection_reason"].startswith("Van back 10:45.")
    assert (sam["fixes_n"], sam["new_crosses_n"], sam["eligible"]) == (2, 0, True)
    apply(original, VAN_ANITA, maya["id"], expected=409)
    with monkeypatch.context() as cached:
        cached.setattr(
            "server.fixes.run_checker",
            lambda _: (_ for _ in ()).throw(
                AssertionError("cached suggestions must not solve again")
            ),
        )
        assert suggestions(original, VAN_ANITA) == van
    first = apply(original, VAN_ANITA, sam["id"])
    fp1 = first["fingerprint"]
    assert fp1 != original

    truck = suggestions(fp1, TRUCK_RAVI)["suggestions"][0]
    assert (truck["fixes_n"], truck["still_broken_n"], truck["new_crosses_n"]) == (1, 1, 0)
    second = apply(fp1, TRUCK_RAVI, truck["id"])
    fp2 = second["fingerprint"]

    joel = suggestions(fp2, JOEL)
    assert set(joel["route_reasons"].values()) == {"Nobody can open the loading area."}
    one, two = joel["suggestions"]
    assert (one["fixes_n"], one["still_broken_n"], one["new_crosses_n"], one["eligible"]) == (
        1,
        0,
        1,
        False,
    )
    assert one["new_crosses"] == [JOEL_MAYA]
    assert "Joel absent + Maya absent" in one["rejection_reason"]
    assert (
        next(r for r in one["scenario_results"] if r["scenario_id"] == JOEL_MAYA)["state"]
        == "cross"
    )
    apply(fp2, JOEL, one["id"], expected=409)
    final = apply(fp2, JOEL, two["id"])
    final_fp = final["fingerprint"]
    assert len(SESSIONS[final_fp].results) == 100
    assert all(r.state == "tick" for r in SESSIONS[final_fp].results)
    chain = final["plan_map"]["fix_history"]
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
    assert changed_by(final_plan, key_item) == 3
    for route_id, fix_number in [("route-c", 1), ("route-a", 2)]:
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
