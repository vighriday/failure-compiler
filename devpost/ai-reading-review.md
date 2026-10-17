# Live reading checkpoint, 17 October 2026

## Status

Hardening and revised parts 1 to 5 are complete. The read-v3 bake-off selected Gemini: 43/100 mean exact checker results and 90.57% mean aligned fields, against Groq's 12/100 and 82%. Part 6 reached a new correction checkpoint: two loader-order edits match all 100 reference results, but the one-shot reading includes an extra Hall entity that cannot be removed with the approved controls. Its actual matrix has 115 scenarios and its checker inputs still differ. No example fixture has been replaced and no live fix suggestions were requested. Slice 6 remains unchecked; slice 7 has not started.

The provider adapter, strict schemas, versioned prompts, raw-response recording, token logs and offline provider tests are implemented. The candidate has real-reading browser screenshots; live HTTP/UI integration, session keys and live fix suggestions remain pending. The running app continues to use its labelled hand-written example.

## Original exact-name bake-off (superseded measurement)

All six calls passed the format gate. Responses were retained without editing; see [bakeoff.json](bakeoff.json) for each response, source lines, guessed marks, mismatch list, metadata and token usage. At this earlier checkpoint Groq remained primary; the revised instruction below supersedes that choice.

| Provider | Reading 1 | Reading 2 | Reading 3 | Mean field match | Total tokens |
| --- | --- | --- | --- | --- | --- |
| Groq / openai/gpt-oss-120b | 45.16%, 3,418 tokens | 48.39%, 3,446 tokens | 45.16%, 3,418 tokens | 46.24% | 10,282 |
| Gemini / gemini-3.8-flash | 58.06%, 3,274 tokens | 58.06%, 5,974 tokens | 58.06%, 3,799 tokens | 58.06% | 13,047 |

The comparison checks 62 truth fields after the existing ID normalisation, preserving primary-first assignment order. Entity names are included. For example, `Route A` and `A` normalise to different IDs, which also makes that route's other fields fail exact matching. These percentages describe exact field agreement, not a separate measure of semantic understanding. The prompts contain no expected example answers or desired fixes.

Groq calls were spaced by at least 61 seconds during the bake-off, and each used fewer than 3,500 tokens. Installed SDKs: Groq 1.7.0 and google-genai 2.31.0. Offline tests check Groq's strict schema and low reasoning, disabled SDK retries, Gemini's `response_mime_type` plus `response_json_schema`, the token reservation, and key-free logs.

## Earlier one-shot primary example reading (read-v1, historical)

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

## Verification at the earlier stop (historical)

- 100 offline tests pass; Ruff reports zero issues.
- Hardening's production build and both browser regressions pass, including the unchanged example story and post-run re-confirmation.
- The two required hardening screenshots are in ignored `devpost/screens/`.
- No live fix suggestions were requested after the stop condition. There are no real per-case verdicts or real-reading UI screenshots yet.
- Slice 6 remains unchecked. Continuing requires a decision on missing records and name normalisation or correction before replacing the example fixtures.

## Prompt versions and aligned scores

The revised measurement aligns entity identities by type and role, ignores display names in field comparison, and compares every result field, including numeric costs and schedules. Human-cost wording uses common labels only for this comparison. A missing entity is not filled from truth: failures targeting it are no-ops in the unchanged solver, and its missing inputs remain field mismatches. Ranking is mean exact checker results, mean aligned field percentage, lower variance across those two scores, then fewer total tokens.

| Prompt | Provider | Aligned fields, three runs | Exact results out of 100, three runs | Total tokens |
| --- | --- | --- | --- | --- |
| read-v1, rescored saved responses | Groq | 84%, 88%, 84% | 18, 18, 18 | 10,282 |
| read-v1, rescored saved responses | Gemini | 96%, 96%, 96% | 33, 48, 48 | 13,047 |
| read-v2 | Groq | 73.21%, 73.68%, 73.68% | 17, 18, 18 | 11,643 |
| read-v2 | Gemini | 96%, provider error, provider error | 48, unavailable, unavailable | 4,212 for the successful run |
| read-v3 | Groq | 82%, 82%, 82% | 12, 12, 12 | 10,775 |
| read-v3 | Gemini | 90.57%, 90.57%, 90.57% | 48, 33, 48 | 7,470 |

No new provider calls were made to rescore `read-v1`; [bakeoff-read-v1.json](bakeoff-read-v1.json) preserves the raw records and the new scores. `read-v2` asks for every person, vehicle, place, route and supply arrival, keeps the plan's own names, and marks approximate durations as guessed. Example names, times and preset numbers are absent from the system prompt. Test settings are supplied separately from application configuration. `fix-v1` is unchanged; it contains generic operation instructions and has not yet been called for the new real example.

### Generic revisions and provider settings

`read-v2` confused outbound household routes with incoming supplies in Groq's output. Its Gemini campaign had one successful reading; the other two slots hit truncation (`MAX_TOKENS`) and HTTP 503/504 failures, including retries. [bakeoff-read-v2.json](bakeoff-read-v2.json) retains each attempt under `previous_attempts`. Increasing Gemini's shared thinking/output limit from 6,000 to 16,384 did not complete that campaign. Incomplete providers are excluded from ranking; errors are not treated as successful zero-score readings. The table counts tokens only for scored successful responses; failed HTTP calls have no returned token usage.

`read-v3` adds generic distinctions between distribution vehicles, incoming supply deliveries and outbound household routes. It contains no example-specific facts. Gemini uses LOW thinking and a 16,384 output limit, with one SDK attempt; Groq retains low reasoning and its conservative token reservation. No successful response was rerun. Gemini run 2 initially returned HTTP 503; its single retry and original failure are both saved in [bakeoff-read-v3.json](bakeoff-read-v3.json). Provider settings are part of this campaign, so the difference from earlier versions is not attributed to prompt wording alone.

All saved campaigns use the same final evaluator: route letters, primary-driver/key-holder roles, vehicle use and the exclusive-loading place identify corresponding entities. Names are not compared or used to choose a match. Ambiguous or extra entities stay visible. Field-score denominators include the union of truth and extracted checker fields, so extra entities lower the score. Each reading runs the truth map's 100 scenarios; this is a common comparison matrix, not a claim that a reading with extra entities generates only 100 scenarios itself.

### Selected primary, 17 October 2026

| Rank | Provider | Mean exact results / 100 | Mean aligned fields | Consistency variance | Successful-run tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | Gemini / gemini-3.8-flash | 43 | 90.57% | 50 | 7,470 |
| 2 | Groq / openai/gpt-oss-120b | 12 | 82% | 0 | 10,775 |

Ranking follows the requested order: exact full-result equivalence, aligned fields, consistency, tokens. The variance is the sum of population variances of those two scores across three runs. Gemini wins on the first criterion. Run 2 puts Ravi first in Route A's loading list; the other runs put Joel first. Assignment order is meaningful, and full schedule equality is intentionally included in the score. `server/config.py` records the date, winner and scores; the adapter reads that order, and each provider keeps its own model ID when primary and fallback switch.

## Part 6: one-shot winner reading and the remaining control gap

One separate Gemini call captured the example with read-v3, LOW thinking and 2,480 total tokens. The successful response was not rerun or edited. Local evidence is under ignored `devpost/screens/live-candidates/read-v3/`:

- `example-reading.json`: unedited provider record, exact `raw_text`, model, prompt version, timestamp and token usage.
- `reading-attempts.json`: the single successful attempt.
- `reading-audit.json`: alignment, before/after full results, actual scenario count, exact correction actions and remaining input mismatches.
- `ui-proof.json`: the result of using the visible browser controls against that same saved response.

| Mismatch class | Actual reading | Treatment |
| --- | --- | --- |
| Naming only | `Loading bay` instead of `Loading area`; `Route A/B/C` instead of `A/B/C` | Preserve the AI's labels. Alignment excludes them from scoring. |
| Fixed by a control | Route A loaders: Joel, Anita, Maya, Ravi | Move Maya above Anita: Joel, Maya, Anita, Ravi. |
| Fixed by a control | Route C loaders: Joel, Anita, Maya | Move Anita and Maya above Joel: Anita, Maya, Joel. |
| Not fixable with the approved controls | A separate `Hall` place, in addition to `Loading bay`, with `opens_at=540`, `needs_key=false`, `one_vehicle_at_a_time=false` | No remove/merge rule question exists. Keep it in both the raw response and diagnostic map. |

No supply delivery is missing in this reading, so it needs no addition. The guessed facts still require individual confirmation. The AI's four arrival-time questions require explicit answers after reviewing their associated facts; bulk confirmation answers none of them.

The local browser proof used the existing up-arrow controls, individual guess confirmations and the question buttons. It reached 100/100 exact matches on the common truth matrix, with all 50 truth inputs matching. The three extra Hall fields remain: the complete aligned input score is **50/53 = 94.34%**. The real grid has **115 tests: 1 single weak spot, 3 hidden pairs, 13 already broken by the weak spot, 98 survived**. An extra place introduces one new single and 14 new pairs. Ignoring it would hide a checker input and would not satisfy the requested reading-to-truth test.

Screenshots at a 1440x900 viewport are saved locally as `devpost/screens/read-v3-candidate-before.png`, `read-v3-candidate-reviewed.png` and `read-v3-candidate-grid.png`. The preview overrides the fixture loader only inside its own local server process; canonical fixtures are untouched. There were no page errors or fix-suggestion requests. Map totals now reflect the current entity count instead of always claiming 14 problems and 100 scenarios.

### Stop and remaining work

The requested reference-result score is reachable, but complete checker-input equivalence and the actual 100-scenario example are not reachable with the current controls. `test_reading_matches_truth.py` has not been added as a passing test by ignoring the extra entity. Regression tests instead prove that the guard retains extra entities and reports this distinction. A decision about handling extra extracted entities is needed before replacing the fixture. No removal control, merge rule, checker change, another successful capture or fix-suggestion call was added to get past the checkpoint.

Part 7 is not eligible yet. Suggestions and checker verdicts for Joel absent, supply delivery late + Ravi absent, van late + Anita leaves early, and van late + Anita absent are therefore **not requested**, rather than represented by placeholder output. The existing hand-written example reading and fix fixtures remain in use and labelled as such. Live HTTP reading, session keys, live suggestions and the remaining slice 6 work are pending.

### Final verification at this checkpoint

- `uv run -- python -m pytest -q`: **126 passed**, with one dependency deprecation warning.
- `uv run -- python -m ruff check .`: passed.
- `npm run build`: passed (TypeScript and production Vite bundle).
- `scripts/verify_saved_reading.py`: real candidate reviewed through visible controls; 100/100 common results, 115 actual cells, no page errors, no suggestion request.
- Existing `scripts/verify_review.py` and `scripts/verify_story.py`: both passed on an isolated local server. The canonical demo, three fixes, 100 survived, linked fingerprints, re-confirmation and reduced motion remain intact.
- Checker constraints, truth fixture, expected results and canonical reading/fix fixtures are unchanged. The preview server shut down after verification. Screenshots remain ignored.
