"""In-memory maps and results, addressed by the confirmed checker fingerprint."""

from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock

from server.models import ScenarioResult
from server.ordering import canonical_order
from server.validation.fingerprint import fingerprint_plan_map
from server.validation.models import PlanMap


@dataclass
class MapSession:
    plan: PlanMap
    results: list[ScenarioResult] | None = None
    owner: str | None = None
    source: str = "saved"
    revision: int = 0
    review_evidence: dict = field(default_factory=dict)
    suggestion_batches: list[dict] = field(default_factory=list)
    ancestors: dict = field(default_factory=dict, repr=False)
    lock: RLock = field(default_factory=RLock, repr=False, compare=False)


@dataclass(frozen=True)
class MapSnapshot:
    plan: PlanMap
    results: list[ScenarioResult] | None
    source: str
    revision: int
    review_evidence: dict = field(default_factory=dict)
    suggestion_batches: list[dict] = field(default_factory=list)


def capture_map(session: MapSession) -> MapSnapshot:
    with session.lock:
        return MapSnapshot(
            session.plan.model_copy(deep=True),
            [result.model_copy(deep=True) for result in session.results]
            if session.results is not None
            else None,
            session.source,
            session.revision,
            deepcopy(session.review_evidence),
            deepcopy(session.suggestion_batches),
        )


def map_is_current(session: MapSession, captured: MapSnapshot) -> bool:
    """Caller holds session.lock while checking and installing a result."""
    return (
        session.revision == captured.revision
        and session.plan == captured.plan
        and session.source == captured.source
    )


SESSIONS: dict[str, MapSession] = {}
OWNED_SESSIONS: dict[tuple[str, str], MapSession] = {}


def get_map(fingerprint: str, owner: str | None = None) -> MapSession | None:
    if owner is not None and (owner, fingerprint) in OWNED_SESSIONS:
        return OWNED_SESSIONS[owner, fingerprint]
    # Unowned maps are created only by trusted Python helpers, such as the
    # locked example tests. HTTP readings always have an owner.
    return SESSIONS.get(fingerprint)


def remember_map(
    plan: PlanMap,
    results: list[ScenarioResult] | None = None,
    *,
    owner: str | None = None,
    source: str = "saved",
    review_evidence: dict | None = None,
    ancestors: dict | None = None,
) -> str:
    fingerprint = fingerprint_plan_map(plan)
    plan.fingerprint = fingerprint
    plan = canonical_order(plan)
    store = SESSIONS if owner is None else OWNED_SESSIONS
    key = fingerprint if owner is None else (owner, fingerprint)
    if key not in store:
        store[key] = MapSession(plan.model_copy(deep=True), results, owner, source)
    else:
        # Equivalent inputs can carry different labels or role IDs in a new reading.
        # Regenerate presentation/results rather than pairing old IDs with new metadata.
        session = store[key]
        with session.lock:
            if session.plan != plan or session.source != source:
                session.revision += 1
                session.suggestion_batches = []
                session.ancestors = {}
            if session.plan.checker_data() != plan.checker_data():
                session.results = None
            session.plan = plan.model_copy(deep=True)
            session.source = source
            if results is not None:
                session.results = results
    with store[key].lock:
        if review_evidence is not None:
            store[key].review_evidence = deepcopy(review_evidence)
        if ancestors is not None:
            store[key].ancestors = dict(ancestors)
    return fingerprint
