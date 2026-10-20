"""Gemini structured JSON using the installed google-genai configuration fields."""

import logging
from datetime import UTC, datetime

import httpx

from server.ai.types import AIError, ProviderResponse
from server.config import PROVIDER_MODELS

MODEL = PROVIDER_MODELS["gemini"]

LOGGER = logging.getLogger(__name__)


def generate(system: str, user: str, schema: dict, key: str, version: str) -> ProviderResponse:
    from google import genai
    from google.genai import errors, types

    try:
        # Verified against google-genai 2.31.0 GenerateContentConfig.model_fields on 2026-10-17:
        # response_mime_type + response_json_schema are supported. response_format is not a field.
        # https://ai.google.dev/gemini-api/docs/structured-output
        with genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=45000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        ) as client:
            result = client.models.generate_content(
                model=MODEL,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0,
                    # Thinking and JSON share this budget. 6,000 truncated structured
                    # responses with MAX_TOKENS in the read-v2 bake-off.
                    max_output_tokens=16384,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    response_mime_type="application/json",
                    response_json_schema=schema,
                ),
            )
    except errors.APIError as error:
        status = error.code or 502
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
            f"Gemini request failed ({status}); "
            + ("check your key." if code == "invalid_key" else "try again later."),
            provider="gemini",
            status=401 if code == "invalid_key" else 502,
        ) from error
    except (TimeoutError, ConnectionError, httpx.TransportError) as error:
        raise AIError(
            "timeout", "Gemini could not be reached before the timeout.", provider="gemini"
        ) from error
    usage = result.usage_metadata
    record = ProviderResponse(
        "gemini",
        MODEL,
        version,
        datetime.now(UTC).isoformat(),
        result.text or "",
        usage.prompt_token_count or 0 if usage else 0,
        (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0) if usage else 0,
        usage.total_token_count or 0 if usage else 0,
        result.model_dump(mode="json"),
    )
    LOGGER.info(
        "AI tokens provider=gemini model=%s prompt=%s input=%d output=%d total=%d",
        MODEL,
        version,
        record.input_tokens,
        record.output_tokens,
        record.total_tokens,
    )
    return record
