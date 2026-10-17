"""One read/fix adapter; provider failures and gate failures share a bounded fallback."""

import json
import re
from dataclasses import dataclass
from typing import Callable

from pydantic import ValidationError

from server.ai import gemini_provider, groq_provider
from server.ai.prompts import (
    FIX_PROMPT_VERSION,
    FIX_SYSTEM,
    READ_PROMPT_VERSION,
    READ_SYSTEM,
    numbered_plan,
)
from server.ai.types import AIError, AIFixResponse, ProviderResponse, compact_schema
from server.config import PROBLEM_TYPES
from server.validation.gate import GateError, validate_ai_reading
from server.validation.models import AIPlanReading


@dataclass
class ReadingResult:
    raw: ProviderResponse
    reading: AIPlanReading
    attempts: list[dict]


@dataclass
class FixResult:
    raw: ProviderResponse
    fixes: AIFixResponse
    attempts: list[dict]


def _call(
    system: str,
    user: str,
    schema: dict,
    keys: dict[str, str],
    version: str,
    gate: Callable,
    provider: str | None,
) -> tuple[ProviderResponse, object, list[dict]]:
    attempts = []
    for name in [provider] if provider else ["groq", "gemini"]:
        if name not in {"groq", "gemini"}:
            raise AIError("provider_error", "Unknown AI provider.", status=422)
        key = keys.get(name)
        if not key:
            attempts.append({"provider": name, "error": "missing_key"})
            continue
        raw = None
        try:
            module = groq_provider if name == "groq" else gemini_provider
            raw = module.generate(system, user, compact_schema(schema), key, version)
            parsed = gate(raw.raw_text)
            attempts.append({"provider": name, "status": "passed"})
            return raw, parsed, attempts
        except (GateError, ValidationError, json.JSONDecodeError) as error:
            attempts.append(
                {
                    "provider": name,
                    "error": "format_check_failed",
                    "reason": str(error),
                    "raw": raw.record() if raw else None,
                }
            )
        except AIError as error:
            if error.code in {"invalid_key", "not_distribution", "input_too_large"}:
                raise
            attempts.append({"provider": name, "error": error.code, "reason": str(error)})
    codes = {attempt.get("error") for attempt in attempts}
    if codes == {"missing_key"}:
        raise AIError("missing_key", "Add an AI key, or load the example plan.", status=401)
    reason = "; ".join(
        f"{row['provider']}: {row.get('reason', row.get('error'))}" for row in attempts
    )
    error = AIError(
        "format_check_failed" if "format_check_failed" in codes else "providers_failed",
        "AI reading did not pass the format check: " + reason
        if "format_check_failed" in codes
        else "Both providers failed. " + reason,
    )
    error.attempts = attempts
    raise error


def read_plan(text: str, keys: dict[str, str], *, provider: str | None = None) -> ReadingResult:
    if not text.strip() or len(text) > 4000:
        raise AIError("invalid_plan", "Enter a plan of 1 to 4,000 characters.", status=422)

    def gate(raw: str) -> AIPlanReading:
        reading = validate_ai_reading(raw)
        if not reading.is_distribution_plan:
            raise AIError(
                "not_distribution",
                reading.not_distribution_reason or "This does not look like a distribution plan.",
                status=422,
            )
        for item in [
            *reading.people,
            *reading.vehicles,
            *reading.places,
            *reading.deliveries,
            *reading.routes,
        ]:
            match = re.fullmatch(r"L([1-9][0-9]*)", item.source_line)
            if not match or int(match[1]) > len(text.splitlines()):
                raise GateError(
                    f"Invalid source_line {item.source_line!r} for {item.id}",
                    field="source_line",
                    bad_value=item.source_line,
                )
        return reading

    raw, reading, attempts = _call(
        READ_SYSTEM,
        json.dumps(
            {
                "plan": numbered_plan(text),
                "test_settings": {
                    problem["id"]: problem["default_size"]
                    for problem in PROBLEM_TYPES
                    if problem["has_size"]
                },
            }
        ),
        AIPlanReading.model_json_schema(),
        keys,
        READ_PROMPT_VERSION,
        gate,
        provider,
    )
    return ReadingResult(raw, reading, attempts)


def suggest_fixes(context: dict, keys: dict[str, str], *, provider: str | None = None) -> FixResult:
    def gate(raw: str) -> AIFixResponse:
        result = AIFixResponse.model_validate_json(raw)
        if len(result.fixes) > 3:
            raise GateError(
                "At most three fixes are allowed", field="fixes", bad_value=len(result.fixes)
            )
        return result

    raw, fixes, attempts = _call(
        FIX_SYSTEM,
        json.dumps(context, separators=(",", ":")),
        AIFixResponse.model_json_schema(),
        keys,
        FIX_PROMPT_VERSION,
        gate,
        provider,
    )
    return FixResult(raw, fixes, attempts)
