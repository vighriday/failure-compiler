# Live reading checkpoint, 17 October 2026

## Status

The measurement was corrected on 19 October: checker equivalence compares only state, lateness_minutes and human_cost. Timelines are excluded because equal-quality schedules can differ. Existing read-v3 responses now score Gemini 100/100 mean verdicts and 94.34% aligned fields, against Groq 55/100 and 84%; Gemini remains primary. No new API calls were made. A reversible place-identity question resolves the extra Hall explicitly. The same one-shot reading now reaches 100% checker-input agreement, 100/100 locked verdict matches and 100 actual scenarios through the UI, without reordering loaders. The raw reading is promoted as-is, with correction actions saved separately. Part 7 was attempted on 19 October: Gemini returned HTTP 503 on every case, including one explicit retry per failed request. No suggestion response or checker verdict exists. The earlier stop evidence is retained below. Slice 6 remains unchecked while live integration and suggestion review are pending; slice 7 has not started.

The provider adapter, strict schemas, versioned prompts, raw-response recording, token logs and offline provider tests are implemented. The running app now uses the saved real reading and displays its provider/model. Live HTTP/UI integration, session keys and reviewed live fix suggestions remain pending; the existing fix suggestions are still labelled hand-written placeholders.

## Verdict-only re-score, 19 October 2026

### Natural schedules verified before further fix capture

The solver now proves the best lateness first, fixes that objective value, and minimises the sum of load/drive starts in a second pass. The unchanged `test_example_locked` and determinism test pass, as does a direct earliest-start regression. No truth or expected verdict was regenerated. Exact optimisation is retained; disabling small-model presolve probing removes overhead.

Five before runs took 5.716 seconds on the first call (including lazy solver import), then 1.376/1.447/1.425/1.850 seconds, a warm median of **1.436 seconds**. Six final after runs took **2.547/1.621/1.773/1.587/1.702/1.644 seconds**, a warm median of **1.644 seconds** and maximum **2.547 seconds including first-call import**. Every final complete 100-scenario run is below three seconds; all verdicts equal the saved before run. First-call import timings also depend on local filesystem caches, so they are reported separately. Local evidence: `devpost/screens/solver-before.json` and `solver-after.json`.

Checker equivalence is exact agreement on **state, lateness_minutes and human_cost** for each of the truth map's 100 scenarios, matching the fields locked by `expected-results.json`. Timelines, chosen people, diagnostic bounds, dim-cause metadata and fingerprints are excluded. Common labels are used only when rendering human-cost text for comparison. Aligned field comparison treats `loader_ids` as sets and keeps `driver_ids` in primary-first order. Fingerprints use the same loader-set semantics without changing the displayed list.

Every saved campaign was re-scored offline, including the original `bakeoff.json`. Each report retains its previous scores and ranking in `measurement_history`; `raw`, provider attempt logs and failed-call history are unchanged. No provider call or prompt revision was made.

| Prompt | Provider | Aligned fields, three runs | Locked verdicts out of 100, three runs | Successful-run tokens |
| --- | --- | --- | --- | --- |
| read-v1 | Groq | 86%, 90%, 86% | 87, 87, 87 | 10,282 |
| read-v1 | Gemini | 100%, 100%, 100% | 100, 100, 100 | 13,047 |
| read-v2 | Groq | 75%, 75.44%, 75.44% | 87, 87, 87 | 11,643 |
| read-v2 | Gemini | 100%, provider error, provider error | 100, unavailable, unavailable | 4,212 |
| read-v3 | Groq | 84%, 84%, 84% | 55, 55, 55 | 10,775 |
| read-v3 | Gemini | 94.34%, 94.34%, 94.34% | 100, 100, 100 | 7,470 |

The incomplete read-v2 Gemini campaign remains excluded from its campaign ranking. Prompt versions are recorded separately; the active read-v3 campaign determines the primary. Loader reordering accounts for no input difference. The extra Hall still lowers Gemini's raw read-v3 field score: three additional place fields yield 50/53 = 94.34%; verdict equivalence alone never hides extra inputs or their additional scenarios.

| Rank | Active provider / model | Mean locked verdicts / 100 | Mean aligned fields | Consistency variance | Successful-run tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | Gemini / gemini-3.8-flash | 100 | 94.34% | 0 | 7,470 |
| 2 | Groq / openai/gpt-oss-120b | 55 | 84% | 0 | 10,775 |

Ranking remains verdict matches, aligned fields, lower population variance across runs, then fewer tokens. Gemini stays primary, dated 19 October in `server/config.py`. `test_reading_matches_truth` now replays only the Hall identity correction plus the required confirmations and questions. It checks all aligned inputs, all 100 locked verdicts and the actual 100-scenario count, while asserting that the provider's loader order is unchanged.

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

## Superseded full-result measurement (historical)

The following scores include arbitrary solver schedules. They are retained as history only; the verdict-only re-score below is authoritative.

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

### Earlier selection, 17 October 2026 (superseded scores)

| Rank | Provider | Mean exact results / 100 | Mean aligned fields | Consistency variance | Successful-run tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | Gemini / gemini-3.8-flash | 43 | 90.57% | 50 | 7,470 |
| 2 | Groq / openai/gpt-oss-120b | 12 | 82% | 0 | 10,775 |

Ranking follows the requested order: exact full-result equivalence, aligned fields, consistency, tokens. The variance is the sum of population variances of those two scores across three runs. Gemini wins on the first criterion. Run 2 puts Ravi first in Route A's loading list; the other runs put Joel first. That evaluator incorrectly treated loader order as meaningful and intentionally included full schedule equality. The verdict-only re-score above supersedes that measurement. `server/config.py` records the date, winner and scores; the adapter reads that order, and each provider keeps its own model ID when primary and fallback switch.

## Part 6: one-shot winner reading and the earlier control gap

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

### Earlier stop and remaining work at that point

The requested reference-result score is reachable, but complete checker-input equivalence and the actual 100-scenario example are not reachable with the current controls. `test_reading_matches_truth.py` has not been added as a passing test by ignoring the extra entity. Regression tests instead prove that the guard retains extra entities and reports this distinction. A decision about handling extra extracted entities is needed before replacing the fixture. No removal control, merge rule, checker change, another successful capture or fix-suggestion call was added to get past the checkpoint.

Part 7 is not eligible yet. Suggestions and checker verdicts for Joel absent, supply delivery late + Ravi absent, van late + Anita leaves early, and van late + Anita absent are therefore **not requested**, rather than represented by placeholder output. The existing hand-written example reading and fix fixtures remain in use and labelled as such. Live HTTP reading, session keys, live suggestions and the remaining slice 6 work are pending.

### Final verification at this checkpoint

- `uv run -- python -m pytest -q`: **126 passed**, with one dependency deprecation warning.
- `uv run -- python -m ruff check .`: passed.
- `npm run build`: passed (TypeScript and production Vite bundle).
- `scripts/verify_saved_reading.py`: real candidate reviewed through visible controls; 100/100 common results, 115 actual cells, no page errors, no suggestion request.
- Existing `scripts/verify_review.py` and `scripts/verify_story.py`: both passed on an isolated local server. The canonical demo, three fixes, 100 survived, linked fingerprints, re-confirmation and reduced motion remain intact.
- Checker constraints, truth fixture, expected results and canonical reading/fix fixtures are unchanged. The preview server shut down after verification. Screenshots remain ignored.

## Continued review: part 6 passes with an explicit place choice

The user continued after the checkpoint. A generic rule question now asks whether an unused place listing is separate or the same place as another listed loading/supply place. Nothing is merged automatically. Choosing the same place preserves the removed listing, its source rows and any question references in server-owned history. The selected place's facts require individual re-confirmation; Change restores the original listing. Bulk confirmation cannot answer this question or accept the newly stale facts.

The original one-shot response was reused. Its bytes have SHA-256 `6f30729d00eb041136d3594a62886ce3ee2dce5dd480fdac9eca39c62b234cfa`, identical in the local candidate and promoted fixture. The review ledger also stores a digest of UTF-8 text with LF line endings and a digest of the exact `raw_text`, so checking out the repository on Windows does not create a false hash failure.

The current demo needs one explicit correction:

1. Hall: **Same place as another listing**, choose **Loading bay**, then individually review the retained place's facts.

The earlier Route A and Route C loader reordering is removed from the review ledger and demo script. Loaders are eligible sets, so their order changes no checker input or verdict. The raw reading and its displayed loader order are preserved.

No fact addition or name edit is needed. Other guessed facts and all four arrival questions still require individual confirmation. After those actions, **every aligned checker input matches, all 100 locked verdicts match exactly, and the real map generates 100 scenarios**: 1 single weak spot, 3 hidden pairs, 12 dimmed, 84 survived.

`fixtures/example-reading.json` is the unedited provider record. `fixtures/example-corrections.json` contains only the separate review ledger and digests. `test_reading_matches_truth.py` replays the same server actions and compares checker inputs plus every locked verdict. Driver order is retained; loader order is ignored. The old hand-written reading is retained only under `tests/fixtures/` for its explicit hardening contracts. The production app identifies the saved reading as Gemini output; the existing fix suggestions remain labelled placeholders while live suggestions await review.

Playwright exercised the place picker, Change/undo, loader arrows, individual confirmations and all 100 cells without page errors or suggestion calls. New evidence is in `devpost/screens/read-v3-merged-before.png`, `read-v3-merged-reviewed.png`, `read-v3-merged-grid.png` and `devpost/screens/live-candidates/read-v3/read-v3-merged-ui-proof.json`. The earlier 115-cell stop evidence remains intact. The full story and re-confirmation browser regressions also pass with the real reading, including all three placeholder fixes and all 100 scenarios surviving. Fix fixture lookup aligns identities to the reviewed map, so the AI's supply-delivery ID does not break the example story.

### Promotion verification, 19 October 2026

- `uv run -- python -m pytest -q`: **137 passed**, one dependency deprecation warning, 124.71 seconds.
- `uv run -- python -m ruff check .`: passed.
- `npm run build`: passed.
- Saved `v2-verification.json`: all 11 browser checks pass at widths 1440/768/390/320, with no page errors. This includes scroll and animation recovery, keyboard navigation, all 105 illustrative sample cells, every driver rule picker, confirmation, live results and scored placeholder fixes. The actual reviewed example has 100 cells.
- Existing story and re-confirmation browser proofs pass with the promoted reading. Submission assets are untouched; screenshots remain ignored.
- No new reading or live fix call was made during verification. Real fix responses must be captured once per cross and remain uncommitted for the requested review.

## Part 7: provider unavailable, 19 October 2026

The confirmed reading passed part 6 before any fix request. The recorder then called the winning Gemini model once for each of the four crosses using unchanged `fix-v1`. Each request returned HTTP 503. One explicit retry per failed case returned the same error; the initial failures remain under `previous_attempts`. No successful response was repeated, and no other provider, model or prompt was substituted.

| Broken case | Attempts | Provider result | Suggestions / checker verdicts |
| --- | --- | --- | --- |
| Joel absent | 2 | HTTP 503 both times | Unavailable |
| Supply truck late + Ravi absent | 2 | HTTP 503 both times | Unavailable |
| Van late + Anita leaves early | 2 | HTTP 503 both times | Unavailable |
| Van late + Anita absent | 2 | HTTP 503 both times | Unavailable |

`fix-v1` has no measurable suggestion score or returned token usage from these attempts. Failure contexts and attempt history are saved locally in ignored `devpost/screens/live-candidates/read-v3/example-fixes.json`; `fix-review.md` contains the full checkpoint report. No real suggestions were received, promoted or committed. The hand-written fixture remains clearly labelled as a placeholder. Do not describe it as the winner's output.

The recording command reuses successful captures and never retries a saved failure by default. Its explicit `--retry-failed` option only permits recorded transient provider errors, preserves their history, and is incompatible with `--score-only`. Both recorder regressions pass, including no successful-call repetition or credential storage. Lint and format checks pass for the recorder. The next action is a failed-request retry after Gemini recovers, followed by gating and all-100 scoring, then the user's review before committing any returned suggestions. Live HTTP/UI integration and the rest of slice 6 remain pending.
