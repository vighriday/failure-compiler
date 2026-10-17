"""AI and confirmed-map models used by the validation gate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from server.models import AppliedFix, Delivery, Person, Place, PlanMapData, Route, Vehicle

ItemStatus = Literal["unconfirmed", "confirmed", "corrected", "added"]


class AIPerson(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    can_drive: bool
    can_drive_guessed: bool
    available_from: int
    available_until: int
    holds_key: bool
    source_line: str
    guessed: bool


class AIVehicle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    available_from: int
    source_line: str
    guessed: bool


class AIPlace(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    opens_at: int
    one_vehicle_at_a_time: bool
    needs_key: bool
    source_line: str
    guessed: bool


class AIDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    arrives_at: int
    place_id: str
    source_line: str
    guessed: bool


class AIRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    households: int
    load_minutes: int
    drive_minutes: int
    vehicle_id: str
    driver_ids: list[str]
    loader_ids: list[str]
    source_line: str
    guessed: bool


class AIQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    item_id: str
    question_text: str


class AIProblemSizes(BaseModel):
    """A closed object is required by Groq strict structured output."""

    model_config = ConfigDict(extra="forbid", strict=True)
    volunteer_leaves_early: int
    vehicle_returns_late: int
    supply_delivery_late: int
    place_blocked: int


class AIPlanReading(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    people: list[AIPerson]
    vehicles: list[AIVehicle]
    places: list[AIPlace]
    deliveries: list[AIDelivery]
    routes: list[AIRoute]
    finish_time: int
    finish_time_source: str
    finish_time_guessed: bool
    problem_sizes: AIProblemSizes
    questions: list[AIQuestion]
    is_distribution_plan: bool
    not_distribution_reason: str | None


class AIMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: str
    model: str
    timestamp: str


class MapPerson(Person):
    source_line: str = ""
    guessed: bool = False
    can_drive_guessed: bool = False
    status: ItemStatus = "unconfirmed"
    original_value: dict[str, object] | None = None
    changed_by_fix: int | None = None


class MapVehicle(Vehicle):
    source_line: str = ""
    guessed: bool = False
    status: ItemStatus = "unconfirmed"
    original_value: dict[str, object] | None = None
    changed_by_fix: int | None = None


class MapPlace(Place):
    source_line: str = ""
    guessed: bool = False
    status: ItemStatus = "unconfirmed"
    original_value: dict[str, object] | None = None


class MapDelivery(Delivery):
    source_line: str = ""
    guessed: bool = False
    status: ItemStatus = "unconfirmed"
    original_value: dict[str, object] | None = None


class MapRoute(Route):
    source_line: str = ""
    guessed: bool = False
    status: ItemStatus = "unconfirmed"
    original_value: dict[str, object] | None = None
    changed_by_fix: int | None = None


class MapQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    item_id: str
    question_text: str


class PlanMap(BaseModel):
    """Server-owned map, including UI provenance separate from checker inputs."""

    model_config = ConfigDict(extra="forbid", strict=True)
    fingerprint: str | None = None
    ai_meta: AIMetadata
    people: list[MapPerson]
    vehicles: list[MapVehicle]
    places: list[MapPlace]
    deliveries: list[MapDelivery]
    routes: list[MapRoute]
    finish_time: int
    finish_time_source: str = ""
    finish_time_guessed: bool = False
    problem_sizes: dict[str, int]
    questions: list[MapQuestion] = []
    fix_history: list[AppliedFix] = []

    @classmethod
    def from_truth_map(cls, data: PlanMapData) -> PlanMap:
        """Wrap the hand-authored truth map as an already confirmed map."""
        common = {"status": "confirmed", "source_line": "truth map", "guessed": False}
        return cls(
            ai_meta=AIMetadata(provider="fixture", model="truth-map", timestamp=""),
            people=[MapPerson(**p.model_dump(), **common) for p in data.people],
            vehicles=[MapVehicle(**v.model_dump(), **common) for v in data.vehicles],
            places=[MapPlace(**p.model_dump(), **common) for p in data.places],
            deliveries=[MapDelivery(**d.model_dump(), **common) for d in data.deliveries],
            routes=[MapRoute(**r.model_dump(), **common) for r in data.routes],
            finish_time=data.finish_time,
            finish_time_source="truth map",
            problem_sizes=data.problem_sizes.copy(),
        )

    def checker_data(self) -> PlanMapData:
        """Drop server metadata and return exactly the fields the checker reads."""
        return PlanMapData(
            people=[
                Person.model_validate(p.model_dump(include=set(Person.model_fields)))
                for p in self.people
            ],
            vehicles=[
                Vehicle.model_validate(v.model_dump(include=set(Vehicle.model_fields)))
                for v in self.vehicles
            ],
            places=[
                Place.model_validate(p.model_dump(include=set(Place.model_fields)))
                for p in self.places
            ],
            deliveries=[
                Delivery.model_validate(d.model_dump(include=set(Delivery.model_fields)))
                for d in self.deliveries
            ],
            routes=[
                Route.model_validate(r.model_dump(include=set(Route.model_fields)))
                for r in self.routes
            ],
            finish_time=self.finish_time,
            problem_sizes=self.problem_sizes.copy(),
        )
