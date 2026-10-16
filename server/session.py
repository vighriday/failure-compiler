"""In-memory maps and results, addressed by the confirmed checker fingerprint."""

from dataclasses import dataclass

from server.models import ScenarioResult
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
    if fingerprint not in SESSIONS:
        SESSIONS[fingerprint] = MapSession(plan.model_copy(deep=True), results)
    else:
        SESSIONS[fingerprint].plan = plan.model_copy(deep=True)
        if results is not None:
            SESSIONS[fingerprint].results = results
    return fingerprint
