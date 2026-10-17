"""In-memory maps and results, addressed by the confirmed checker fingerprint."""

from dataclasses import dataclass

from server.models import ScenarioResult
from server.ordering import canonical_order
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.models import PlanMap


@dataclass
class MapSession:
    plan: PlanMap
    results: list[ScenarioResult] | None = None


SESSIONS: dict[str, MapSession] = {}


def remember_map(plan: PlanMap, results: list[ScenarioResult] | None = None) -> str:
    fingerprint = fingerprint_plan_map(plan)
    plan.fingerprint = fingerprint
    plan = canonical_order(plan)
    if fingerprint not in SESSIONS:
        SESSIONS[fingerprint] = MapSession(plan.model_copy(deep=True), results)
    else:
        # Equivalent inputs can carry different labels or role IDs in a new reading.
        # Regenerate presentation/results rather than pairing old IDs with new metadata.
        if SESSIONS[fingerprint].plan.checker_data() != plan.checker_data():
            SESSIONS[fingerprint].results = None
        SESSIONS[fingerprint].plan = plan.model_copy(deep=True)
        if results is not None:
            SESSIONS[fingerprint].results = results
    return fingerprint
