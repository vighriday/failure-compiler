# Live reading checkpoint, 17 October 2026

## Status

Hardening is complete. Slice 6 stops at the user's required checkpoint: the one-shot primary reading cannot be corrected to the truth map using the approved controls. No example fixture was replaced or committed. Slice 7 has not started.

The provider adapter, strict schemas, versioned prompts, raw-response recording, token logs and offline provider tests are implemented. Live HTTP/UI integration, session keys, live fix suggestions and the real-reading screenshots are still pending. The running app continues to use its labelled hand-written example.

## Bake-off

All six calls passed the format gate. Responses were retained without editing; see [bakeoff.json](bakeoff.json) for each response, source lines, guessed marks, mismatch list, metadata and token usage. The primary remains Groq as requested. Gemini's higher mean is recorded as the bake-off winner in `server/config.py` with today's date.

| Provider | Reading 1 | Reading 2 | Reading 3 | Mean field match | Total tokens |
| --- | --- | --- | --- | --- | --- |
| Groq / openai/gpt-oss-120b | 45.16%, 3,418 tokens | 48.39%, 3,446 tokens | 45.16%, 3,418 tokens | 46.24% | 10,282 |
| Gemini / gemini-3.8-flash | 58.06%, 3,274 tokens | 58.06%, 5,974 tokens | 58.06%, 3,799 tokens | 58.06% | 13,047 |

The comparison checks 62 truth fields after the existing ID normalisation, preserving primary-first assignment order. Entity names are included. For example, `Route A` and `A` normalise to different IDs, which also makes that route's other fields fail exact matching. These percentages describe exact field agreement, not a separate measure of semantic understanding. The prompts contain no expected example answers or desired fixes.

Groq calls were spaced by at least 61 seconds during the bake-off, and each used fewer than 3,500 tokens. Installed SDKs: Groq 1.7.0 and google-genai 2.31.0. Offline tests check Groq's strict schema and low reasoning, disabled SDK retries, Gemini's `response_mime_type` plus `response_json_schema`, the token reservation, and key-free logs.

## One-shot primary example reading

This was a separate, successful Groq call after the bake-off, using 3,418 tokens. It was not rerun. The raw record, attempt log and full comparison are saved locally, under ignored `devpost/screens/live-candidates/`:

- `example-reading.json`: the unedited provider record, including exact content in `raw_text`.
- `reading-attempts.json`: one successful attempt.
- `reading-audit.json`: every mismatch and the correctability decision.

Selected actual output:

```json
{
  "places": [{"id": "pl1", "name": "Hall", "opens_at": 540, "needs_key": true}],
  "deliveries": [],
  "route_names": ["Route A", "Route B", "Route C"],
  "vehicle_names": ["car", "van"]
}
```

This excerpt selects fields for readability; the raw record remains intact. Other differences include four volunteers starting at minute 0 instead of 540, Route A listing only Ravi as a loader, and a different loading order on Route C.

The reading matched 28 of 62 expected fields (45.16%). The current time pickers and ordered person controls can correct availability and loading assignments. They cannot:

1. Add the omitted supply-delivery record.
2. Rename `Hall` to `Loading area`.
3. Rename routes `Route A/B/C` to `A/B/C`, which the current normaliser treats differently.
4. Correct vehicle-name casing to match the truth map exactly.

The missing delivery is a substantive missing checker input; this is more than a display-label mismatch. No names, entities, model constraints or raw responses were changed to make the comparison pass.

## Verification and remaining work

- 100 offline tests pass; Ruff reports zero issues.
- Hardening's production build and both browser regressions pass, including the unchanged example story and post-run re-confirmation.
- The two required hardening screenshots are in ignored `devpost/screens/`.
- No live fix suggestions were requested after the stop condition. There are no real per-case verdicts or real-reading UI screenshots yet.
- Slice 6 remains unchecked. Continuing requires a decision on missing records and name normalisation or correction before replacing the example fixtures.
