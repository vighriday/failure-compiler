"""Raw provider records stay separate from normalised gate output."""

from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from server.models import FixOperation


class AISuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    description: str
    operations: list[FixOperation]


class AIFixResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    explanation: str
    fixes: list[AISuggestion]


@dataclass
class ProviderResponse:
    provider: str
    model: str
    prompt_version: str
    timestamp: str
    raw_text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    response: dict[str, Any]

    def record(self) -> dict:
        return asdict(self)


class AIError(ValueError):
    def __init__(self, code: str, message: str, *, provider: str = "", status: int = 502):
        super().__init__(message)
        self.code, self.provider, self.status = code, provider, status


def compact_schema(schema: dict) -> dict:
    """Drop decorative titles to save tokens, retaining all validation constraints."""
    return {
        key: (
            [compact_schema(row) if isinstance(row, dict) else row for row in value]
            if isinstance(value, list)
            else compact_schema(value)
            if isinstance(value, dict)
            else value
        )
        for key, value in schema.items()
        if key != "title"
    }
