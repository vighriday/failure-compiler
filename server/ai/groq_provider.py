"""Groq strict JSON schema, one SDK attempt, and a conservative one-call/minute budget."""

import json
import logging
import threading
import time
from datetime import UTC, datetime

from server.ai.types import AIError, ProviderResponse
from server.config import PRIMARY_MODEL

LOGGER = logging.getLogger(__name__)
_LOCK = threading.Lock()
_NEXT_CALL = 0.0


def cooldown_seconds() -> float:
    return max(0, _NEXT_CALL - time.monotonic())


def generate(system: str, user: str, schema: dict, key: str, version: str) -> ProviderResponse:
    from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

    global _NEXT_CALL
    # Reserve an upper estimate for ordinary English/JSON (2 bytes/token plus overhead).
    prompt_budget = (len((system + user + json.dumps(schema)).encode()) + 1) // 2 + 512
    output_budget = min(4096, 7900 - prompt_budget)
    if output_budget < 1500:
        raise AIError(
            "input_too_large",
            "Plan and schema exceed the safe token budget.",
            provider="groq",
            status=422,
        )
    with _LOCK:
        remaining = cooldown_seconds()
        if remaining:
            raise AIError(
                "rate_limited",
                f"Rate limited. Try again in {int(remaining) + 1} seconds.",
                provider="groq",
                status=429,
            )
        _NEXT_CALL = time.monotonic() + 61
    try:
        result = Groq(api_key=key, max_retries=0, timeout=45).chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "plan_reading" if version.startswith("read") else "fix_suggestions",
                    "strict": True,
                    "schema": schema,
                },
            },
            reasoning_effort="low",
            temperature=0,
            max_completion_tokens=output_budget,
        )
    except (APITimeoutError, APIConnectionError) as error:
        raise AIError(
            "timeout", "Groq could not be reached before the timeout.", provider="groq"
        ) from error
    except APIStatusError as error:
        status = error.status_code
        code = (
            "invalid_key"
            if status in {401, 403}
            else "rate_limited"
            if status == 429
            else "server_error"
            if status >= 500
            else "provider_error"
        )
        raise AIError(
            code,
            f"Groq request failed ({status}); "
            + ("check your key." if code == "invalid_key" else "try again later."),
            provider="groq",
            status=401 if code == "invalid_key" else 502,
        ) from error
    usage = result.usage
    record = ProviderResponse(
        "groq",
        PRIMARY_MODEL,
        version,
        datetime.now(UTC).isoformat(),
        result.choices[0].message.content or "",
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
        usage.total_tokens if usage else 0,
        result.model_dump(mode="json"),
    )
    LOGGER.info(
        "AI tokens provider=groq model=%s prompt=%s input=%d output=%d total=%d",
        PRIMARY_MODEL,
        version,
        record.input_tokens,
        record.output_tokens,
        record.total_tokens,
    )
    return record
