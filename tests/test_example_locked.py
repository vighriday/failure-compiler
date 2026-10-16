"""The hand-authored example's four crosses are its locked story."""

import json
from pathlib import Path

from server.checker.runner import run_checker
from server.models import PlanMapData

ROOT = Path(__file__).resolve().parents[1]

JOEL_ABSENT = "volunteer_absent__person-joel"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supplies"
VAN_ANITA_LEAVES = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
VAN_ANITA_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"


def example_plan() -> PlanMapData:
    return PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())


def test_example_locked() -> None:
    plan = example_plan()
    results = run_checker(plan)
    expected = json.loads((ROOT / "fixtures/expected-results.json").read_text())

    assert len(results) == 100
    assert [
        {"scenario_id": r.scenario_id, "state": r.state,
         "lateness_minutes": r.lateness_minutes, "human_cost": r.human_cost}
        for r in results
    ] == expected
    assert all(result.state != "qmark" for result in results)

    crosses = {result.scenario_id: result for result in results if result.state == "cross"}
    assert set(crosses) == {
        # Single weak spot. Joel holds the only hall key, so without him the
        # loading bay never opens and no route can be loaded.
        JOEL_ABSENT,
        # Hidden pair. The truck is 45 minutes late, so loading starts at 9:45.
        # Ravi is absent. Route A takes an hour, and his backups both leave
        # before it could finish: Maya at 10:45, Joel at 10:30. Each problem
        # alone is fine: on time, Maya finishes Route A by 10:31; with Ravi
        # present, he drives it after the late truck.
        TRUCK_RAVI,
        # Hidden pair, the demo's main case. The van is back from the early
        # pickup 30 minutes late (10:00), so Route B runs 10:10 to 10:45.
        # Anita leaves at 10:30, Joel at 10:30, and Maya at 10:45: when the van
        # returns at 10:45 nobody on the loading team is left to load Route C.
        # Alone, the late van is loaded by Anita at 10:45; alone, Anita's early
        # exit is fine because the on-time van is back by 10:15.
        VAN_ANITA_LEAVES,
        # Follows from the pair above: absent is strictly worse than leaving
        # early, so this must also break.
        VAN_ANITA_ABSENT,
    }
    assert crosses[JOEL_ABSENT].human_cost == (
        "Routes A, B, C: 30 households not delivered. Nobody can open the loading area"
    )
    assert crosses[TRUCK_RAVI].human_cost == "Route A: 10 households not delivered"
    assert crosses[VAN_ANITA_LEAVES].human_cost == "Route C: 8 households not delivered"
    assert crosses[VAN_ANITA_ABSENT].human_cost == "Route C: 8 households not delivered"
    assert sum(result.state == "dim" for result in results) == 12
    assert sum(result.state == "tick" for result in results) == 84
