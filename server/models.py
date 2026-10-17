"""All Pydantic models: checker entities, AI reading shapes, PlanMap, results, fixes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Checker entity shapes (what the solver reads)
# ---------------------------------------------------------------------------


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    can_drive: bool
    available_from: int  # minutes from midnight
    available_until: int
    holds_key: bool


class Vehicle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    available_from: int


class Place(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    opens_at: int  # minutes from midnight; planned loading start
    one_vehicle_at_a_time: bool  # always True for the loading area
    needs_key: bool


class Delivery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    arrives_at: int  # minutes from midnight
    place_id: str


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    households: int
    load_minutes: int
    drive_minutes: int
    vehicle_id: str
    driver_ids: list[str]  # primary first, then backups
    loader_ids: list[str]  # primary first, then backups


# ---------------------------------------------------------------------------
# Truth map / checker input bundle
# ---------------------------------------------------------------------------


class PlanMapData(BaseModel):
    """The checker-input subset of a confirmed plan map.

    This is what ``fixtures/example-truth.json`` stores and what the checker
    reads.  It intentionally omits AI metadata, status marks, and correction
    history so the fingerprint is stable.
    """

    model_config = ConfigDict(extra="forbid")

    people: list[Person]
    vehicles: list[Vehicle]
    places: list[Place]
    deliveries: list[Delivery]
    routes: list[Route]
    finish_time: int  # minutes from midnight
    problem_sizes: dict[str, int]  # problem_type_id -> minutes


# ---------------------------------------------------------------------------
# Scenario result (one cell in the grid)
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_id: str
    event: str  # "load_start", "load_end", "drive_start", "drive_end", "not_delivered"
    time: int  # minutes from midnight
    person_id: str | None = None
    vehicle_id: str | None = None


class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    failures: list[str]  # problem ids applied in this scenario
    state: str  # "tick", "cross", "dim", "qmark"
    dim_cause: str | None = None  # problem id that already breaks it alone
    lateness_minutes: int | None = None
    lower_bound_minutes: int | None = None  # known lower bound if qmark
    timeline: list[TimelineEvent] = []
    human_cost: str | None = None
    map_fingerprint: str = ""


class RunCount(BaseModel):
    total: int
    completed: int
    weak_spots: int
    hidden_pairs: int
    dimmed: int
    survived: int
    unknown: int
    pending: int
    line: str


# ---------------------------------------------------------------------------
# Fix operations and suggestions (slice 5 / 6)
# ---------------------------------------------------------------------------


class FixOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal[
        "add_driver",
        "replace_drivers",
        "add_loader",
        "replace_loaders",
        "move_route",
        "set_person_availability",
        "set_vehicle_availability",
        "give_spare_key",
    ]
    target_id: str  # entity id being changed
    field: str  # field name being changed
    value: str | int | bool | list[str]  # new value


class AppliedFix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fix_id: str
    description: str
    operations: list[FixOperation]
    from_fingerprint: str
    to_fingerprint: str


class FixSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    description: str
    operations: list[FixOperation]
    scenario_results: list[ScenarioResult] = []
    fixes_n: int = 0
    still_broken_n: int = 0
    new_crosses_n: int = 0
    new_crosses: list[str] = []
    eligible: bool = False
    rejection_reason: str | None = None
    gate_status: str = "passed"  # "passed" | "format_error" | "rules_error" | "couldnt_apply"
    gate_reason: str | None = None
