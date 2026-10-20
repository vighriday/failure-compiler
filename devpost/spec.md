---
doc: spec
status: approved
---

# Failure Compiler - Technical Spec

## How This Works, In Plain Language

The app is a browser page talking to a small Python server running on your laptop. The server binds to 127.0.0.1 only, because it holds AI keys in memory.

When you paste a plan, the server sends it to an AI (Gemini first, Groq as a fallback). The AI's only job at that point is to read messy text and return a structured description of the plan: who is doing what, in what vehicle, at what place, between what times. That description comes back as JSON, and the server runs it through a strict format check before it touches anything else. If the JSON is wrong in any way - a missing field, an extra field, a name that does not exist - it gets rejected and you are told exactly why. This is the core learning goal made concrete: the AI produces output, the gate decides whether it is usable, and nothing downstream ever sees an unchecked map.

The AI returns an `AIPlanReading`. The server wraps it into a `PlanMap`, adding its own metadata: which provider answered, per-item status, and correction history. The two schemas are separate so Groq strict mode never forces the AI to invent a fingerprint or a fix history.

Once the map passes the format check, the server runs plain rules and surfaces any failures as questions on screen. The browser sends constrained actions to `POST /api/update-map`; the server updates its own reading draft and validates with the same rules used at Confirm. The user confirms or corrects using constrained choices only. The AI does not re-read.

When everything is confirmed and all rules pass, the browser sends the map to `POST /api/confirm-map`. The server re-validates and returns a fingerprint: a SHA-256 hash of the canonical sorted checker inputs (people, vehicles, places, deliveries, routes, finish time, problem sizes). Two identical plans get the same fingerprint; changing a problem size changes it. Timestamps and status marks are excluded.

The checker then runs. It is a constraint solver (CP-SAT) that treats the plan as a scheduling problem. Singles run first. Any pair that contains a single already broken is marked dimmed without solving, because every problem type only removes options, so a pair can never be better than its singles. For remaining pairs, the solver tries to find the best possible schedule using only the people and vehicles the plan names. If it can find one where everyone finishes on time, the plan survives. If the best it can find is still late, the plan breaks, and the lateness is the human cost - proved optimal. The time limit is CP-SAT's deterministic limit (`max_deterministic_time`), not wall clock, so results are the same on every machine.

Some scenarios leave a route with no available driver, or the loading area with no key holder. Rather than returning "infeasible" with no number, every route may also be "not delivered," carrying a penalty larger than any possible lateness: households times the full horizon (finish time plus 180 minutes). The solver always returns a schedule. "Not delivered" becomes part of the human cost: "Routes A, B, C: 30 households not delivered. Nobody can open the loading area." Tick, cross, and question mark keep their meaning.

After the format gate, the server normalises all entity ids to stable slugs derived from type and name (e.g. `person-ravi`, `vehicle-van`, `route-c`) and updates every reference. This means two runs of the same plan always produce the same fingerprint regardless of what the AI chose as ids. The gate also rejects duplicate ids.

When you click a cross, one AI call fetches both the plain explanation and up to three fix suggestions together. The server caches the result per fingerprint and scenario, so reopening a cross never calls the AI again. The checker's facts (timeline, late routes, minutes late, or "not delivered") are always shown; the AI sentence sits next to them, labelled as the AI's explanation. Fix suggestions use a fixed list of operations so they can always be gated. Turned-down reasons come from the checker, not the AI.

Preview never re-solves. `suggest-fixes` returns each fix's full per-scenario results, not just counts. Preview draws from that. Accepting a previewed fix replays from cache with the flip animation.

The example plan ships with a saved AI reading and saved fix suggestions, so the full flow runs without an AI key.

## The Core Journey Through the System

PRD ref: `prd.md > The Core Journey`.

1. User pastes a plan (or loads the example). The browser sends `{text, example, api_key?, key_provider?}` to `POST /api/read-plan`. The server reads environment keys from the ignored `.env`; a typed key is held only in the session's private server memory. In example mode the server returns the saved fixture from `fixtures/example-reading.json` without making any AI call.

2. Server calls the AI. Gemini (`gemini-3.8-flash`, structured output against `AIPlanReading`) is the default primary. On rate limit, server error including HTTP 503, timeout, or format-check failure, the server tries Groq (`openai/gpt-oss-120b`, strict structured output). One attempt each, using available keys. An explicitly selected typed-key provider is tried first, with the other provider as fallback. Invalid keys fail clearly without silently switching providers. On both failing, the browser receives a clear error and a retry action.

3. Format gate runs. The raw AI JSON is parsed and validated against `AIPlanReading` (`extra="forbid"`, all fields required). Duplicate ids are rejected. Reference integrity check: every id used in routes and jobs must exist in the entity lists. Failure returns a `422` with the specific rejection reason.

4. Server normalises all entity ids to stable slugs from type and name (`person-ravi`, `vehicle-van`, `route-c`) and updates every reference. Then wraps the reading into a `PlanMap`, setting every item's status to `unconfirmed` and recording the AI's original value for each.

5. Plan map screen renders. The browser displays the checklist view, the structured reading with labelled field citations or entity mentions, and the "What we'll test" list.

6. User confirms or corrects. Each constrained action goes to `POST /api/update-map` with the server-issued reading ID. The server updates its own draft and returns item statuses and rule failures; `POST /api/validate-map` can return the current validation snapshot. Affected items lose their confirmed mark. The Confirm button state is computed from the current map state, never stored.

7. User hits Confirm. The browser sends its reading ID to `POST /api/confirm-map`. The server checks its own confirmations, answers, gate and rules one final time. Browser confirmation lists cannot bypass this check. On pass, it returns the fingerprint. On failure, it returns the specific missing review or failing rule.

8. Crash test begins. Browser calls `GET /api/run-tests?map={fingerprint}`. The server opens an SSE stream. Singles run first; dimmed pairs are marked without solving. Each result (`scenario_id, state, lateness_minutes, timeline`) is sent as it finishes.

9. User clicks a cross. Browser calls `POST /api/suggest-fixes` with the scenario id and map fingerprint. One AI call returns a plain explanation sentence and up to three fix suggestions, each with its full per-scenario results already scored. All pass the gate before the response is sent.

10. User previews a fix. The browser draws the projected grid from the fix's stored per-scenario results. No re-solve. One preview at a time.

11. User accepts a fix. Browser sends `POST /api/apply-fix`. Server validates the fix operations (format gate + rules), applies them to the stored map, produces a new fingerprint, and starts a new SSE test run. Cells that changed replay from the cached scored results with the flip animation; any cell not in the cache re-solves.

12. User opens the report. `GET /api/report?map={fingerprint}` returns the full run record. Browser print produces the PDF.

## Stack

### Backend

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Solver and AI SDK support; learner's preference. |
| Package manager | uv | Lockfile installs; identical across Windows, macOS, Linux. |
| Web framework | FastAPI | Native SSE, async, OpenAPI schema for type-sync with the frontend. |
| Solver | OR-Tools 9.15 CP-SAT | Wheels for all target platforms; proves lateness minimums. |
| Validation | Pydantic v2 (`extra="forbid"`) | Single source of truth for every data shape; strict-mode compatible. |
| Linter | ruff | Fast; configured in `pyproject.toml`. |
| Test runner | pytest | Locked example test, format gate tests, rules tests, determinism test. |

### AI Layer

| Role | Provider | Model | SDK |
|---|---|---|---|
| Primary | Gemini | `gemini-3.8-flash` | `google-genai` (official) |
| Fallback | Groq | `openai/gpt-oss-120b` | `groq` (official) |

Model names live in `server/config.py`. Fallback triggers: rate limit, server error including HTTP 503, timeout, or format-check failure on the primary's output. One attempt per available provider. Explicitly choosing a provider for a typed key changes the order only for that session. Invalid-key and unsupported-plan responses stop with their specific error.

The Gemini adapter uses `google-genai` `models.generate_content` with `response_mime_type` and `response_json_schema`, verified against the installed SDK.

Every reading records provider and model; shown as "Read by provider / model" on the plan map, results and report. Suggestion responses identify their answering provider/model separately. Safe response metadata includes source (`live`, `saved` or `placeholder`), whether fallback answered and provider/status/error attempt summaries. API responses never contain keys or raw private provider requests. The report preserves reading and suggestion attribution separately.

`GET /api/ai-status` exposes configured provider/model names, the session's selected provider and key-availability booleans only. A random HttpOnly, SameSite=Lax cookie identifies the session; its value contains no key. Typed keys stay in a private server-memory store, outside maps, fingerprints, logs, disk and response bodies. Confirming a map or applying a fix preserves its owner and session key scope. Successful suggestion caches are scoped to that owner, fingerprint and case.

Doc links:
- FastAPI: https://fastapi.tiangolo.com/
- OR-Tools CP-SAT: https://developers.google.com/optimization/reference/python/sat/python/cp_model
- Pydantic v2: https://docs.pydantic.dev/latest/
- groq SDK: https://console.groq.com/docs/openai
- google-genai SDK: https://googleapis.github.io/python-genai/

### Frontend

| Component | Choice | Rationale |
|---|---|---|
| Framework | React + Vite + TypeScript (strict) | Learner's preference; Vite starts in one command; strict TS catches drift early. |
| State | `useReducer` + context | Sufficient for the app's state shape; no external library. |
| Styling | Plain CSS with CSS custom properties | Full control over the grid and timeline; no utility-class overhead. |
| Fonts | `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono` | Self-hosted; no runtime call to Google Fonts. |
| Grid and timeline | CSS grid + SVG, hand-built | Exact visual control over all four cell states and the timeline. |
| Landing conversion and motion | htmlparser2 at development time; GSAP, ScrollTrigger and `@gsap/react` in the UI | Converts the supplied v2 templates to typed React; scoped animation cleanup, scroll progress and source highlights. No editor runtime or HTML interpreter in production. |
| Client contracts | `web/src/types.ts` and the production TypeScript build | Contracts are maintained alongside the API client. Automatic OpenAPI generation is deferred. |

Rules are implemented only in Python (`server/validation/rules.py`). The browser never reimplements them; it calls `POST /api/validate-map` instead.

## Where It Runs and How Someone Tries It

Runtime: local, two processes. Started with one cross-platform command (PowerShell-compatible, no `make`).

Start command (after `uv sync --extra dev --extra ai` and `npm install`):
```
uv run -- python scripts/dev.py
```
This starts `uvicorn server.main:app --host 127.0.0.1 --port 8000` and `vite --port 5173` in parallel. The server binds to 127.0.0.1 only because AI keys are held in memory.

What to open: `http://localhost:5173`

Demo recording: load the example plan, walk the full flow (paste / plan map / crash test / open a cross / preview the turned-down fix / accept the real fix / report), record the screen. No deployment needed.

Submission: short demo video plus public GitHub repository. Deployment is optional and explicitly post-PoC.

Environment requirements:
- Python 3.12 (managed by uv)
- Node.js 20+
- `GEMINI_API_KEY` in `.env` for the default primary and `GROQ_API_KEY` for fallback; either provider may be used alone. Keys are not needed for the saved example.
- `.env.example` ships with placeholders; `.env` is gitignored
- Alternatively, expand "Use your own AI key" on Screen 1, choose the provider and enter a session-only key. A typed key overrides that provider's environment key without editing `.env`.

Free tier constraints:
- Groq: 30 req/min, 1,000 req/day, 8,000 tokens/min, 200,000 tokens/day. Pasted plans capped at ~4,000 characters; visible counter on Screen 1. Prompts kept lean; reasoning at lowest setting.
- Gemini free tier: Google may use content to improve its products. Screen 1 always displays a Gemini data notice now that Gemini is the default primary: "If you use a Gemini key, don't paste personal details - Google may use them to improve its models. The example plan is fictional."

## Look and Feel

Implements `prd.md > Look and Feel`.

The supplied Landing v2 design is the visual source. Warm off-white background (`#F6F4EE`), paper sheets (`#FBFAF6`), near-black ink (`#1A1916`), and neutral rules (`#DAD6CB`).

CSS custom properties:
- `--color-tick`: deep green `#1E6B47`
- `--color-cross`: brick red `#B23A2E`
- `--color-amber`: `#8A6410`
- `--color-dim`: medium grey `#8E8A80`
- `--color-action`: same as `--color-tick` for the primary button

Typography:
- Body, labels, UI: IBM Plex Sans (self-hosted via `@fontsource`)
- Times, counts, numbers needing alignment: IBM Plex Mono

Grid cells: tick and cross are clean stroke SVG marks, not emoji, not Unicode characters. Colour plus shape so the grid is readable without colour.

Timeline: SVG. Routes as horizontal bars. Finish-time deadline as a solid red vertical line labelled “Noon: families waiting.” Late segments extend past it in `--color-cross`. A not-delivered route is drawn as never leaving, with the reason shown, e.g. “Van back 10:45. Loading team gone.”

Motion: cells fill in sequence as the SSE stream delivers results. Accepted-fix cells flip with a short CSS transition. Both effects check `prefers-reduced-motion` and skip animation if set.

V2 implementation: `design/landing-v2/` preserves both supplied templates. `scripts/convert_landing.mjs` generates React markup and hover/focus styles. `web/src/landing/` owns the typed interactions, responsive layout, example illustrations and animation cleanup. Six tabs share the same shell; real reading and crash-test views replace their illustrative counterparts once a plan is loaded. The Start editor uses the existing API; confirmation, fingerprints, SSE results, previews and fixes retain their existing server paths. A changed source or map cannot reuse an old confirmed result. GSAP restores the page-break fragments on completion, navigation and unmount. Reduced motion uses immediate end states.

## Problem Type Taxonomy

Fixed list. Each type is applied to every matching entity in the confirmed map, producing one concrete label per entity. Sizes from preset choices only: 15, 30, 45, 60, 90 minutes.

| Type | Applies to | Size | Default |
|---|---|---|---|
| Volunteer absent | Each volunteer | None | - |
| Volunteer leaves early | Each volunteer | Minutes before planned end | 90 |
| Vehicle returns late | Each vehicle | Minutes late | 30 |
| Supply delivery arrives late | Each incoming delivery | Minutes late | 45 |
| Place blocked | Each place | Minutes blocked from loading start | 30 |

Example plan: Route A has 10 households, Route B has 12, and Route C has 8. The van returns from an early pickup at 9:30; Joel has the only key and leaves at 10:30; Maya leaves at 10:45; Sam is not on the loading team. Hidden pairs: Supply truck late + Ravi absent; Van late + Anita leaves early; Van late + Anita absent. Count: 5 volunteers x 2 types + 2 vehicles + 1 delivery + 1 loading area = 14 problems; 14 singles + 86 pairs = 100 tests, with 1 single weak spot, 3 hidden pairs, 12 dimmed, and 84 survived.

Hall key: not a separate problem type. Joel holds the only key, so "Joel absent (only key holder)" is the single weak spot. The loading area rule checks `holds_key` on the `Person` model.

Cap: 24 problems. A larger plan shows a rule message before Confirm: "This version supports up to 24 problems. This plan has N."

Deliberately out of scope: volunteer arrives late. Listed under "What was NOT tested" in every report.

## The Validation Gate

Implements `prd.md > Plain Rules Validation`, `prd.md > AI Reading and Structured Map`.

The learning goal made concrete: AI produces output, gate checks it, human confirms, checker acts. Every AI output - initial map reading and every fix suggestion - passes through the same gate.

Order:

1. Parse JSON. Malformed JSON rejected immediately.
2. Pydantic validation. `extra="forbid"`, all fields required. Missing field, extra field, wrong type - rejected with the field name.
3. Reference integrity. Every id used in routes and jobs must exist in the entity lists. Duplicate ids within the reading are also rejected. Unknown or duplicate id rejected with the offending value.

4. Id normalisation. After the integrity check, the server rewrites all entity ids to stable slugs derived from type and name (`person-ravi`, `vehicle-van`, `route-c`) and updates every reference. Two runs of the same plan produce the same ids regardless of what the AI chose, which means they produce the same fingerprint.

5. Plain rules. Every route has a driver id and a vehicle id. Every id in a route's `driver_ids` belongs to someone with `can_drive: true`. Every time is coherent. Finish time is explicit. Problem count within cap. Rule failures surface as questions on Screen 2, never silently.

6. Human confirms. Constrained inputs only. Every correction triggers `POST /api/validate-map` (debounced 150 ms, same Python code). Affected items lose their confirmed mark. Confirm button computed from live map state, never stored.

7. Server re-validates on Confirm. The browser call is for speed and feedback; the server is the authority. The checker endpoint refuses any map that fails.

Rules are implemented once, in `server/validation/rules.py`, and tested in pytest. No TypeScript reimplementation.

Map fingerprint: SHA-256 of the canonical, sorted checker inputs - people, vehicles, places, deliveries, routes, finish time, and problem sizes. Timestamps, AI metadata, and status marks are excluded. Two identical plans get the same fingerprint; changing a problem size changes it. Grid shows "out of date" if the map changes after a run. Report carries the fingerprint.

## Checker: What It Models and How It Decides

Implements `prd.md > Features and Behavior`, `prd.md > The Checker's Three Honest Answers`.

### What the checker models

- **People:** available from / until. Can drive or not. Holds the key or not. A person cannot be in two places at once.
- **Vehicles:** available from a time. One route at a time.
- **Places:** one vehicle loading at a time. The loading area has an `opens_at` time (planned loading start). It can only be used from the later of `opens_at` and the earliest time a key holder is present (if `needs_key` is true). "Place blocked" means blocked from `opens_at` for the chosen minutes.
- **Deliveries:** loading cannot start before the delivery arrives.
- **Routes:** households, `load_minutes` (needs a loader present), `drive_minutes` (needs a driver and a vehicle). Jobs are filled only from `driver_ids` and `loader_ids` in the route - drivers primary first, then listed backups; loader lists are eligible sets with no priority. No one else may fill those jobs. Start times can move freely within people's and vehicles' availability windows.
- **Finish time:** soft deadline. The solver minimises total households-times-minutes-late.

The checker evaluates the real Ravi driver card and turns it down: Ravi already drives Route C and loading still fails. Its reason includes “Van back 10:45. Loading team gone.”

### How the checker decides

After proving the minimum lateness cost, a second solve holds that cost fixed and minimises the sum of loading and driving start times. This removes arbitrary idle time from timelines without trading away the proven verdict. Both passes share the deterministic solver budget. If the second pass reaches its limit, retain the proven lateness verdict and the best valid timeline; earliest-start optimality is then not claimed. A question mark means the primary lateness verdict could not be proved. Small-model presolve probing is disabled to keep the full example run below three seconds.

- Proven zero lateness: **tick.** Zero is the floor; finding zero proves the plan survives.
- Proven minimum above zero: **cross.** The minimum is the human cost - e.g. “Route A: 10 households not delivered” or “Route C: 8 households not delivered.” Proved optimal.
- **Not delivered** routes use a penalty lateness of households times the full horizon (finish time plus 180 minutes), keeping every scenario feasible. Human cost reads "Routes A, B, C: 30 households not delivered. Nobody can open the loading area" Still a cross; tick and question mark keep their meaning.
- Deterministic time limit hit before the minimum lateness is proved: **question mark.** Uses `max_deterministic_time`, not wall-clock seconds, so results are the same on every machine. Never counted as survived. Listed by name in the report under "What was NOT tested."

### Run order

Singles run first, in problem-id order. Any pair that contains a single already marked as a cross is marked **dimmed** without solving - valid because every problem type only removes options, so a pair can never do better than its worst single. Remaining pairs are solved. This keeps one weak spot from flooding the grid with redundant crosses.

One solver worker, fixed seed. The same confirmed map always gives the same results.

### Correctness test

`test_checker_monotone.py` checks on the example map that every pair's lateness is at least each of its singles'. The locked test also asserts the example has no question marks.

## Explain and Fix

Implements `prd.md > Broken Case Detail Panel`, `prd.md > Fix Cards and Scoring`.

One AI request per uncached broken case: `POST /api/suggest-fixes` uses the session-owned confirmed map plus the checker's facts for that case (the failing problem ids, the timeline, the late routes, lateness in minutes, or "not delivered" if applicable). Gemini is primary by default, with one Groq fallback attempt on a transient provider or output-format failure. The AI returns one plain explanation sentence and up to three fix suggestions. The server gates each operation and scores every allowed fix against the complete scenario grid. Successful responses are cached by session owner, fingerprint and scenario ID, so reopening a cross reuses its scored results. Provider failures do not become successful cache entries.

Request fields are `fingerprint`, `scenario_id`, optional `live: true` to ask AI instead of saved responses, and optional `retry: true` for the single explicit retry after a live response has no eligible AI card. Live-pasted maps use live suggestions by default. Responses expose `can_retry`; provider errors include checker-only `case_detail` so the timeline and costs remain visible even when the AI is unavailable.

The checker's facts are always shown in the panel. The AI's sentence sits next to them, labelled "AI's explanation."

Turned-down reasons come from operations and checker outcomes, not the AI. All three van + Anita leaves early cards are turned down: shortening Anita's finish to 11:00 versus planned 12:00, adding Ravi who already drives C while loading still fails at 10:45, and moving vehicles which fixes three crosses but creates a supply-late single. The Sam loader card on van + Anita absent fixes both van crosses. Joel's one-spare-key AI card reveals Joel + Ravi absent. Coordinator-built spare keys for Maya and Sam, then Sam as Route A backup, finish the real-card story with all 100 survived.

### Fix operations (fixed list, always gateable)

Fixes are composed of one or more of these operations. No new people or vehicles may be invented; references always resolve.

| Operation | What it does |
|---|---|
| Add or replace a driver on a route | Changes `driver_ids` on a `Route`, using existing `Person` ids |
| Add or replace a loader on a route | Changes `loader_ids` on a `Route`, using existing `Person` ids |
| Move a route to another vehicle | Changes `vehicle_id` on a `Route`, using existing `Vehicle` ids |
| Change a person's availability | Updates `available_from` or `available_until` on a `Person` |
| Change a vehicle's availability | Updates `available_from` on a `Vehicle` |
| Give a spare key to a person | Sets `holds_key: true` on a `Person`; existing holders keep theirs |

### Scoring before the user sees the card

`suggest-fixes` returns each fix's full per-scenario results (`list[ScenarioResult]`), not just counts. The browser derives `fixes_n`, `still_broken_n`, `new_crosses_n` from those results. Preview draws the projected grid directly from the stored results - no re-solve in the browser. Accepting a previewed fix replays from the cached results with the flip animation; any cell not in the cache (e.g. new cross) re-solves.

### Example mode saved fixes

`fixtures/example-fixes.json` stores the four user-approved unedited Groq fallback records, with Gemini's 503/504 history intact. The app labels the provider/model and fallback reason. Each suggestion passes the gate and is scored live against the current map. A separate runtime copy aligns references without editing the capture. Saved mode never requests or captures a second round; live suggestions require a session/environment key.

## Components

### Screen 1: Paste Plan
Implements `prd.md > Paste and Load`, `prd.md > Screen 1`.

Single `<textarea>` with a character counter (cap ~4,000; amber at 3,500, red at 4,000, submit disabled above). "Load the example plan" fills the textarea; saved-example mode makes no provider request. "Use your own AI key" expands a provider picker and password field. `GET /api/ai-status` reports availability without exposing keys. A Gemini data notice is visible on Screen 1. Read plan sends text and any typed key; after success the browser clears the key and further calls use the HttpOnly session cookie. On failure the entered value stays only in React memory for correction or retry; it is never persisted in the browser.

Connects to: `POST /api/read-plan`.

### Screen 2: Plan Map
Implements `prd.md > AI Reading and Structured Map`, `prd.md > Plain Rules Validation`, `prd.md > Screen 2`.

Three sections stacked vertically:

**Checklist view (top):** computed from the reviewed map - every job with a person and a backup, all ticked. This is the "it looks done" view. Confirmation progress counts current items and open questions. Original AI item counts, corrections, additions and explicit decisions are retained as review evidence; merging an identity does not erase the original AI count.

**Structured reading (middle):** one statement per map item, with `source_tags: Array<{label, source_line, kind}>`. A `fact` tag displays the field citation, for example "Loaders · L13"; a `mention` tag displays "Ravi · mentioned on L8" and does not claim support for that field's value. Every tag's hover/focus highlights its own line. A row without a fact tag never treats an entity mention as field proof; missing sources display "No source line". Legacy `source_line` remains for compatibility, not as a fact-proof fallback. Three visual states: default (status `unconfirmed`), corrected (AI's `original_value` struck through, correction marked "corrected by you"), added (no source line, marked "added by you"). Retained source tags describe the original reading, not proof of a corrected value. Confirmed items get a small confirmed mark. Corrections use constrained inputs only: `<select>` from known entity ids, time picker for times. No free-text fields. Every correction goes through `POST /api/update-map` against the server-owned draft and returns validation. Affected items that depend on the changed item lose their confirmed mark and show "check this, [name] changed."

**Place identity question:** an unused place listing alongside a loading or supply place requires an individual choice: keep separate, or select the same existing place. Only a listing with no loading activity and no delivery references can be merged. The server preserves its entity, source rows and question references for undo, retains the selected place's label and details, and requires its facts to be reviewed individually again. The raw reading is unchanged. This review operation does not change the checker model or infer aliases from the truth fixture.

**"What we'll test" (bottom):** each problem instantiated against confirmed map entities, with preset size picker. Confirmed alongside the plan with the same Confirm button.

Confirm button: disabled until every item is confirmed and all rules pass. "Read by [provider/model]" label. On click, sends map to `POST /api/confirm-map`.

### Screen 3: Crash Test Grid
Implements `prd.md > Live-Filling Grid`, `prd.md > Screen 3`.

CSS grid. Failure types on both axes; one triangle (diagonal + below). Cells update as SSE events arrive. Four states rendered as SVG marks plus CSS classes: `tick`, `cross`, `dim`, `qmark`. Count line updates live. Before/After toggle appears after first accepted fix. Preview banner when a fix is being previewed.

`CrashTest.tsx` fetches the session-owned report snapshot for Before/After after an accepted change. Before uses original metadata, results and counts and is read-only; After uses the current run. Switching cancels an active preview and never re-solves or calls AI. Historical marks remain focusable for their explanations.

Connects to: `GET /api/run-tests` (SSE stream).

### Screen 4: Broken Case Detail Panel
Implements `prd.md > Broken Case Detail Panel`, `prd.md > Fix Cards and Scoring`, `prd.md > Screen 4`.

Right-side panel; grid stays fully interactive. Contents: checker's facts (failures, timeline, human cost), AI's explanation sentence (labelled), fix cards. Fix cards pre-scored from stored per-scenario results. "Turned down" with checker-derived reason when a fix does not solve the case or creates a new cross. Accept enabled only for eligible fixes. Preview draws from stored results.

Below the AI cards, `ChangeBuilder.tsx` offers only selects for existing people/routes/vehicles and time pickers for person hours. A change contains one to three operations: `add_driver`, `add_loader`, `give_spare_key`, `set_person_availability`, or `move_route`. Each driver/loader operation picks one person. No free-text description: the server derives a label from the gated operations.

`POST /api/test-change` accepts `{fingerprint, scenario_id, operations}` only. It resolves the session-owned confirmed snapshot, enforces the operation limit and vocabulary, runs the same `apply_operations` gate and `score_fix` scorer against all 100 scenarios, and stores the scored candidate under an unpredictable server-issued ID. It rechecks the snapshot after solving. The browser cannot submit eligibility, origin or counts. Results appear as "Your change" with the same preview and acceptance rules as AI cards. AI retry preserves coordinator cards and considers only AI eligibility. `AppliedFix.origin` records `ai` or `yours`, shown as "Fix N (AI)" or "Fix N (yours)".

When all AI cards are ineligible, show "None of these suggestions worked". Only live cases with a key offer "Ask for new suggestions", once per session, fingerprint and case. Saved fixtures never trigger a second capture.

Connects to: `POST /api/suggest-fixes`, `POST /api/test-change`, `POST /api/apply-fix`, new SSE stream.

### Screen 5: Report
Implements `prd.md > Screen 5`, `prd.md > The Checker's Three Honest Answers`.

`web/src/screens/Report.tsx` renders the six PRD sections using descriptive `report-*` classes and `report.css`. `GET /api/report?map=<fingerprint>` in `server/report.py` resolves the session owner and requires a completed first run. Unknown or foreign maps return 404; unrun maps or missing history return 409. It calls neither a provider nor a solver. Reports remain available while cases are broken.

The opening `overview` derives accepted AI/yours counts, requested AI-card verdict counts and the largest original household cost from stored evidence. Confirmed review answers resolve the real reviewed value at confirmation time. Facts include `entity_id` for concise grouping, without dropping fields or citations. Failed operations expose plain `gate_reason` separately from technical `gate_detail`. Read-by names are formatted consistently on the map, SSE results and report. The existing stylesheet is unchanged; text grouping removes repetition. The full example is five pages on A4 and Letter, with every fix card verified to remain on one page by `verify_report_pdf.py`.

Confirmation stores review evidence outside checker inputs: original AI item count, corrected/added counts, item bindings and sources, and explicit answers. The example has 32 AI items, one place-identity correction, zero additions and 30 remaining facts. Current statements come from the accepted map. Fix provenance matches operation fields, so changing a key cannot label unrelated hours as changed.

Report facts use the same explicit `source_tags` distinction as the plan map: field citations, labelled entity mentions, or "No source line". An entity mention is not proof of a field value, and retained citations describe the original reading when the value was corrected.

Successful suggestion rounds and coordinator changes append summaries to the map session: scenario, provider label, gate/verdict reason and scores. Accepting a fix freezes the parent snapshot and its evidence in the child's ancestor store. The report follows `AppliedFix.from_fingerprint` / `to_fingerprint` through these snapshots. Accepted scores compare old/new cross sets; earlier rejected cards survive retries and later fixes. Raw private responses and keys are excluded. Re-confirmed map edits are identified separately rather than invented as fixes.

The response contains original/current metadata and results, confirmed facts and review summary, original breaks and grouped dimmed pairs, accepted operations and scores, rejected/couldn't-apply cards with attribution, final count and explicit limits. Unknown results are named for the original/current run and never counted as survived. The example has its exact 14 problems and 100 scenarios; other maps use actual counts and sizes.

The limits name three or more simultaneous problems; types outside the list (bad weather, partway illness, wrong addresses, food shortages and volunteers arriving late); other sizes of the same problems; anything the plan omitted; and question-mark results. The saved-example notice and fingerprint remain visible.

"Print or save as PDF" calls `window.print()`. `@media print` uses automatic A4/Letter paper size, hides navigation and controls, prints text and SVG marks black, keeps cards intact and keeps limitations with the fingerprint. `scripts/capture_report.py` plays the real full story in an isolated offline preview and prints `docs/sample-report.pdf`; the Letter proof stays ignored. `scripts/verify_report_pdf.py` checks text, bounds, minimum size, sections and provenance, and renders every page for inspection.

Connects to: `GET /api/report`.

## Data Model

Checker/fix shapes are Pydantic v2 models with `extra="forbid"`; review/report payloads are built by their server modules. Client contracts are maintained in `web/src/types.ts` beside the API client and checked by the production TypeScript build. Automatic OpenAPI type generation remains deferred.

### AIPlanReading (AI output only)

What the AI returns. Never contains a fingerprint, fix history, or metadata invented by the server.

```
AIPlanReading
  people:               list[AIPerson]
  vehicles:             list[AIVehicle]
  places:               list[AIPlace]
  deliveries:           list[AIDelivery]
  routes:               list[AIRoute]
  finish_time:          int             # Minutes from midnight
  finish_time_source:   str | None      # Actual deadline citation, or null if unsupported
  finish_time_guessed:  bool
  questions:            list[AIQuestion]   # Ambiguities the AI wants to surface
  is_distribution_plan: bool
  not_distribution_reason: str | None   # Non-null if is_distribution_plan is false
```

Each entity in the reading carries `source_line: str` for an entity mention, `guessed: bool`, and a closed `fact_sources` object for that entity type. Each defined field source is a nullable line: cite the line for that particular value or assignment, or return null. `reading-v2` / `read-v4` require every `fact_sources` object and all its nullable fields in outgoing structured-output schemas, including Groq's strict schema. Unknown source fields are rejected. Parsing older raw captures that omit `fact_sources` supplies null per-field sources; it never promotes their entity mention into evidence. Examples:

```
AIPerson
  id:             str    # Stable internal id assigned by the AI
  name:           str
  can_drive:      bool
  can_drive_guessed: bool
  available_from: int
  available_until: int
  holds_key:      bool
  source_line:    str
  fact_sources:   PersonSources  # Fixed fields, each str | None
  guessed:        bool   # True if the AI inferred this person was present

AIRoute
  id:             str
  name:           str
  households:     int
  load_minutes:   int
  drive_minutes:  int
  vehicle_id:     str    # References a Vehicle id
  driver_ids:     list[str]   # Primary first, then backups. References Person ids.
  loader_ids:     list[str]   # Eligible set, with no priority. References Person ids.
  source_line:    str
  fact_sources:   RouteSources   # Fixed fields, each str | None
  guessed:        bool

AIQuestion
  item_id:        str    # The entity this question is about
  question_text:  str
```

(AIVehicle, AIPlace, AIDelivery follow the same pattern: id, name, timing fields, entity-mention `source_line`, the corresponding closed `fact_sources` object, and guessed. AIPlace also carries `opens_at`.)

### PlanMap (server-owned)

Wraps the reading, adds server metadata. Never sent to the AI.

```
PlanMap
  fingerprint:    str | None           # SHA-256 of canonical checker inputs; None pre-confirm
  ai_meta:        AIMeta               # Provider, model, timestamp
  people:         list[MapPerson]
  vehicles:       list[MapVehicle]
  places:         list[MapPlace]
  deliveries:     list[MapDelivery]
  routes:         list[MapRoute]
  finish_time:    int
  problem_sizes:  dict[str, int]       # problem_type -> minutes; keyed by problem type id
  fix_history:    list[AppliedFix]     # Empty until fixes are accepted
```

`AppliedFix` records `from_fingerprint` and `to_fingerprint` so the report and the Before/After toggle can rebuild the full chain from the original plan to the current state:

```
AppliedFix
  fix_id:           str
  origin:           "ai" | "yours"  # Server-owned source of the accepted change
  description:      str
  operations:       list[FixOperation]
  from_fingerprint: str
  to_fingerprint:   str
```

Each `Map*` entity wraps the `AI*` entity and adds server-owned provenance:

```
MapPerson
  ...AI fields...
  status:         "unconfirmed" | "confirmed" | "corrected" | "added"
  original_value: AIPerson | None      # The AI's original reading, for the strikethrough
  # (status "added" means this item was created by a rule question, not the AI)
```

The summary "AI read N items, N corrected by you, N added by you" uses confirmation evidence rather than mutable post-fix status counts. For the approved example it is 32 AI items, one correction and zero additions; merging the duplicate place leaves 30 current fact rows.

### Checker entity shapes

These are the shapes the CP-SAT solver reads. Derived from `PlanMap` at run time; not a separate stored model.

```
Person
  id:             str
  name:           str
  available_from: int
  available_until: int
  holds_key:      bool

Vehicle
  id:             str
  name:           str
  available_from: int

Place
  id:             str
  name:           str
  opens_at:       int               # Minutes from midnight; planned loading start
  one_vehicle_at_a_time: bool   # Always true for the loading area
  needs_key:      bool

Delivery
  id:             str
  name:           str
  arrives_at:     int           # Minutes from midnight
  place_id:       str

Route
  id:             str
  name:           str
  households:     int
  load_minutes:   int
  drive_minutes:  int
  vehicle_id:     str
  driver_ids:     list[str]     # Checker may only assign from this list
  loader_ids:     list[str]     # Checker may only assign from this list
```

### ScenarioResult

```
ScenarioResult
  scenario_id:           str
  failures:              list[str]       # Problem ids
  state:                 "tick" | "cross" | "dim" | "qmark"
  dim_cause:             str | None      # Problem id of the single that causes dimming
  lateness_minutes:      int | None
  lower_bound_minutes:   int | None      # Known lower bound if qmark
  timeline:              list[TimelineEvent]
  human_cost:            str | None      # "Route C: 8 households not delivered"
  map_fingerprint:       str
```

### FixSuggestion

```
FixSuggestion
  id:                    str
  origin:                "ai" | "yours"      # Assigned by the server
  description:           str
  operations:            list[FixOperation]   # From the fixed operations list
  scenario_results:      list[ScenarioResult] # Full results; browser derives counts
  fixes_n:               int                  # Derived by server before sending
  still_broken_n:        int
  new_crosses_n:         int
  eligible:              bool
  rejection_reason:      str | None           # Checker-derived, not AI-written
  gate_status:           "passed" | "format_error" | "rules_error" | "couldnt_apply"
  gate_reason:           str | None
```

### State storage

No database. Review drafts, confirmed maps, test results, fix suggestions and typed keys stay in server memory, associated with the session owner. Maps/results use fingerprints; successful suggestions additionally use scenario IDs. Keys never enter map data, fingerprints, logs, files or responses. Closing a tab does not clear server memory. Restarting the server clears these sessions; environment keys remain in the local ignored `.env` file.

Review evidence and frozen ancestors also live only in this store. They preserve the accepted-fix chain and suggestions checked at each stage independently of later registry revisions. They do not affect checker fingerprints or locked verdicts.

## Fixtures and the Locked Test

`fixtures/example-truth.json`: the correct confirmed map for the Saturday food distribution plan. Written by hand. This is the ground truth.

`fixtures/example-reading.json`: the chosen provider's real output for the example plan, saved as-is. It may have small mistakes; the demo corrects them, which shows the correction trail working.

`fixtures/example-fixes.json`: four unedited real Groq / openai/gpt-oss-120b responses with raw provider metadata, raw-text digests, contexts and the previous Gemini 503/504 attempts. Approved on 20 October 2026. Label: "Suggested by Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)". Runtime parsing and ID alignment happen on a separate copy; original responses stay untouched. The gate and checker score these suggestions live against the current map. No second round is captured. Ten cards are turned down, one fails the gate, and only the Sam loader card is initially eligible.

`fixtures/expected-results.json`: the hand-checked expected verdict and human cost for every cell of the example plan.

### What the tests assert

`test_example_locked.py`: loads `fixtures/example-truth.json`, runs the checker, compares every cell's verdict and human cost against `fixtures/expected-results.json`. The locked test can be built and pass before any AI work. Also asserts the example has no question marks.

`test_checker_monotone.py`: on the example map, asserts that every pair's lateness is at least each of its singles'.

`test_reading_matches_truth.py`: loads the unedited `fixtures/example-reading.json`, checks its saved digest, applies the explicit actions from `example-corrections.json` through the review controls, aligns entities by type and role, then compares every checker input and all 100 locked scenario verdicts (`state`, `lateness_minutes`, `human_cost`) with `fixtures/example-truth.json`. Names are labels and are excluded. It also asserts that the actual map generates 100 scenarios; extra or missing checker entities must not be silently discarded.

`test_format_gate.py`: bad JSON, extra fields, unknown names, wrong types - all rejected with a specific reason.

`test_rules.py`: missing driver, incoherent times, key holder absent, plan over cap, etc. Includes a case where a person's `can_drive` is flipped after their route assignment is confirmed - asserts the route loses its confirmed mark and a rule fires.

`test_determinism.py`: runs the example truth map twice and compares every result.

`test_live_api.py` replays the saved real provider reading through Read plan, the gate, review, confirmation, all scenarios, a cross, scored suggestions and application. Four offline cases replay the approved actual Groq responses from `fixtures/example-fixes.json` with simulated Gemini 503 fallback. `RECORDED_AI_FIXES_PATH` can override that path for local capture review. A separate explicitly synthetic response exercises transport failures. `test_fix_pipeline.py` plays the real-card story and the two coordinator-built changes to all 100 survived; `test_change_builder.py` checks all five operation types, bounds, invalid picks, score forgery and concurrent edits.

`test_live_network.py` requires both explicit `RUN_LIVE_AI_TESTS=1` and the matching provider key from `.env` or the process environment. Its two provider reading smoke tests skip in the ordinary `uv run -- python -m pytest -q` run, even if `.env` contains keys. Deterministic offline tests cover primary HTTP 503 to fallback success, both-provider failures, missing/invalid keys, malformed output, unsupported plans, attribution, successful-response caching and key privacy. `test_live_transport.py` covers read timeouts and connection failures as safe retryable errors.

`bakeoff.py`: runs the example plan through both providers three times. It aligns entities by type and role, ignores names, compares every checker input (including extra inputs), and runs the truth map's 100 scenarios on the aligned reading. It ranks providers by exact verdict matches (state, lateness_minutes and human_cost; timelines excluded), aligned field match, consistency, then tokens. It applies no corrections and preserves raw responses and failed attempts. Every prompt version and its scores are logged in `ai-reading-review.md`; the winner becomes primary in `server/config.py` with the date and scores.

## File Structure

The paths below describe the implementation through slice 7. `Report.tsx`, `CrashTest.tsx`, `CasePanel.tsx` and `ChangeBuilder.tsx` keep descriptive classes for the separate mockup design pass.

```
failure-compiler/
├── server/
│   ├── main.py                  # FastAPI routes, gate, confirmation, SSE and fixes
│   ├── models.py                # Reading, plan, scenario and fix models
│   ├── config.py                # Gemini primary, Groq fallback, sizes and caps
│   ├── ai/                      # Provider adapters, prompts and safe metadata
│   ├── validation/              # Gate, normalization, fingerprint and rules
│   ├── checker/                 # Scenarios, two-pass natural schedules, explanations
│   ├── review.py                # Server-owned confirmations and explicit decisions
│   ├── facts.py                 # Fact bindings, sources and operation-level provenance
│   ├── fixes.py                 # Fixed operations, gate and all-scenario scoring
│   ├── report.py                # Six report sections and frozen history traversal
│   ├── credentials.py           # Private memory-only session keys
│   └── session.py               # Owner-scoped maps, evidence, runs and ancestors
├── web/src/
│   ├── main.tsx
│   ├── App.tsx                  # Paste, review and confirmation flow
│   ├── api/client.ts            # Typed fetch and SSE
│   ├── types.ts                 # Maintained client contracts
│   ├── landing/                 # Approved v2 tabs, source story and illustrative grid
│   ├── components/
│   │   ├── FactEditor.tsx       # Constrained fact corrections
│   │   ├── MissingFactQuestion.tsx
│   │   ├── CrashGrid.tsx        # SVG states and keyboard-readable explanations
│   │   ├── CasePanel.tsx        # Scored AI and coordinator cards
│   │   ├── CaseTimeline.tsx
│   │   └── ChangeBuilder.tsx    # One to three fixed-choice operations
│   ├── screens/
│   │   ├── CrashTest.tsx        # Current run, preview and Before/After
│   │   ├── Report.tsx           # Screen 5 and browser print action
│   │   └── report.css           # Semantic sections and A4/Letter print styles
│   └── styles.css
├── fixtures/
│   ├── example-plan.txt
│   ├── example-truth.json
│   ├── example-reading.json     # Real unedited Gemini reading
│   ├── example-corrections.json # Approved review controls and decisions
│   ├── example-fixes.json       # Real unedited Groq fallback suggestions
│   └── expected-results.json    # Locked verdicts for all 100 scenarios
├── scripts/
│   ├── dev.py                   # Local API and web launcher
│   ├── bakeoff.py               # Recorded provider comparison
│   ├── local_preview.py         # Isolated offline browser verification
│   ├── browser_story.py         # Shared full example flow
│   ├── capture_report.py        # Real A4 and Letter browser printing
│   ├── verify_report_pdf.py     # PDF text, bounds and rendered proof
│   ├── capture_gallery.py       # 1500x1000 actual-app images and Before/After GIF
│   ├── check_readme_links.py
│   └── verify_accessibility.py  # Keyboard story, axe and computed text checks
├── tests/                       # Locked solver, API, review, fix, report and asset tests
├── docs/
│   ├── sample-report.pdf
│   └── images/                  # Six gallery PNGs, thumbnail and actual-results GIF
├── devpost/                     # Planning docs; ignored local verification proofs
├── pyproject.toml
├── package.json
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

### Slice 7 verification and submission assets

`uv run -- python -m pytest -q`, Ruff and the production build cover the server contracts and client compilation. `scripts/verify_story.py`, `verify_review.py` and `verify_landing.py` exercise the real saved flow, original/current comparison, preview cancellation, reconfirmation, responsive layouts and animation recovery without provider calls.

`scripts/verify_accessibility.py` completes the story using native Tab, Enter and select keys, checks visible focus, scans with the development-only `axe-core` dependency, and measures rendered text contrast and size. It covers the actual screens and all illustrative tabs with reduced motion. Text must be at least 12px with contrast at least 4.5:1. The current look is retained; a separate mockup design pass is deferred.

`scripts/capture_gallery.py` produces six actual-app 1500x1000 PNGs using the README filenames under `docs/images`. `scripts/check_readme_links.py` verifies local targets, heading anchors and optionally external URLs. The demo video is explicitly pending, with no fabricated video link. The committed A4 sample report follows the full example story; Letter and rendered page proofs remain ignored under `devpost/screens`.

## External Services and Dependencies

### Groq - Fallback AI provider
- Endpoint: `POST https://api.groq.com/openai/v1/chat/completions`
- Auth: `Authorization: Bearer $GROQ_API_KEY`
- Structured output: `response_format: { type: "json_schema", json_schema: { strict: true, schema: <AIPlanReading JSON schema> } }`
- Rate limits (free tier): 30 req/min, 1,000 req/day, 8,000 tokens/min, 200,000 tokens/day
- Docs: https://console.groq.com/docs/openai
- Key: `GROQ_API_KEY` in `.env`, or a Groq key typed into the session-only input.

### Gemini - Primary AI provider
- SDK: `google-genai` (official)
- Model: `gemini-3.8-flash`
- Structured output: `models.generate_content` with `response_mime_type` and `response_json_schema`, verified against the installed SDK.
- Free tier note: content may be used by Google. Screen 1 discloses this.
- Docs: https://googleapis.github.io/python-genai/
- Key: `GEMINI_API_KEY` in `.env`, or a Gemini key typed into the session-only input.

### OR-Tools 9.15
- Install: `uv add ortools==9.15.*`
- Wheels for Windows, macOS (Intel + Apple Silicon), Linux. No API key; runs locally.
- Docs: https://developers.google.com/optimization/reference/python/sat/python/cp_model

## Important Failure Modes

Implements `prd.md > States and Boundaries`.

- **Both AI providers fail** - clear error message, retry button, "try the example plan instead." Applies to both read-plan and suggest-fixes paths.
- **Primary returns HTTP 503, times out or is rate limited** - one attempt on the available fallback provider, then display the provider/model that actually answered. If neither succeeds, return stable `error_code` plus a safe plain `detail`; never reveal a key or raw provider request.
- **AI output fails the format gate** - "The AI's reading did not pass the format check" plus the specific reason (e.g. "Unknown person id 'dave' in route_a driver_ids" or "Duplicate id 'person-ravi'") plus a retry button. Nothing unchecked reaches the plan map.
- **A fix suggestion fails the gate** - card shows "Couldn't apply" with the specific reason. Never scored, never acceptable.
- **`is_distribution_plan` is false in the reading** - "This version only supports community distribution plans" plus the AI's reason. Offer to load the example.
- **Solver hits the deterministic time limit** - question mark cell. Listed by name under "What was NOT tested." Never a pass.
- **Plan exceeds 24 problems** - rule message on Screen 2 before Confirm: "This version supports up to 24 problems. This plan has N."
- **Plan text exceeds ~4,000 characters** - counter turns amber at 3,500, red at 4,000, submit disabled above 4,000.
- **AI key invalid or call fails** - clear error message, retry button, suggest example plan.
- **No eligible AI fixes** - keep checker facts visible, show "None of these suggestions worked" and offer "Ask for new suggestions" once for a live case with a key. Saved cases never retry AI automatically. Coordinator-built changes remain available in either mode. Failed provider requests can be retried; successful cached responses are not silently regenerated when a cross is reopened.

## What Was Simplified and Why

- **No persistence** instead of accounts and saved sessions. The fingerprint makes a single session reproducible within itself. Persistence is post-PoC.
- **In-memory session store** instead of a database. Same shape of data, zero infrastructure. Server restart loses the session; acceptable for a demo.
- **Browser print for the report** instead of custom export. Covers the submission requirement. Nicer download is in scope.md > Later.
- **Fixed failure-type taxonomy** instead of AI-suggested types. Keeps results reproducible and the example story reliable. Deferred in scope.md.
- **No deployment** - local recording satisfies submission. Live public link is in scope.md > Later.
- **Volunteer arrives late out of scope** - listed under "What was NOT tested." Modelling a departure delay differently from a duration cut adds complexity without serving the demo's three hidden pairs.
- **Hall key as a person attribute** (`holds_key: true` on Joel) rather than a separate problem type. "Joel absent (only key holder)" is the single weak spot. Keeps the taxonomy clean without losing the story.
- **Preview never re-solves** - fix results are cached by fingerprint at scoring time. The browser draws from them. One less round trip; one less failure mode during the demo.

## Decisions and Open Issues

### Decisions

**CP-SAT for the checker.** Lateness is a proved minimum, not a found example. "Zero lateness proven" means the plan genuinely survives. A heuristic solver could find a good schedule but not prove it is the best; CP-SAT's optimality proof is what makes the three honest answers possible. Tradeoff: heavier dependency than a hand-written scheduler. At 14 problems / 100 tests with the deterministic limit, the full run completes in well under a minute.

**Every scenario is kept feasible with a "not delivered" penalty.** Routes that cannot run (no driver available, loading area cannot open) are modelled as delivered with lateness equal to households times the full horizon (finish time plus 180 minutes). This means the solver always returns a number rather than "infeasible", the human cost can always be stated concretely, and tick/cross/question mark keep their meaning.

**Pydantic `extra="forbid"` with nullable fields, not Optional.** Satisfies Groq strict mode (all fields required, no extra properties) while working identically for Gemini. One schema serves both. Tradeoff: every field must always be present in AI output; prompts must make this explicit.

**AIPlanReading and PlanMap are separate schemas.** The AI never sees the server's fingerprint, fix history, or status marks. This makes Groq strict mode workable and keeps the boundary between AI output and server state explicit.

**Id normalisation after the gate.** The server rewrites AI-assigned ids to stable type-and-name slugs and updates every reference. Two runs of the same plan always produce the same ids and the same fingerprint, regardless of what the AI chose. The gate also rejects duplicate ids within a reading.

**Rules implemented only in Python.** One implementation, tested in pytest. The browser calls `POST /api/validate-map` for immediate feedback. No drift possible. The explicit rule that every id in a route's `driver_ids` must belong to someone with `can_drive: true` is what the cascade test in `test_rules.py` relies on: flipping `can_drive` to false makes the route's driver assignment immediately invalid.

**Fingerprint hashes only checker inputs.** People, vehicles, places (including `opens_at`), deliveries, routes, finish time, problem sizes - sorted canonically. Excludes timestamps and status marks so two identical plans always get the same fingerprint, and changing a problem size always changes it.

**`suggest-fixes` results cached per fingerprint and scenario.** Reopening a cross never makes a second AI call. The cache lives in the server's session store alongside the map and results.

**`AppliedFix` records `from_fingerprint` and `to_fingerprint`.** The report and the Before/After toggle can reconstruct the full chain from the original plan to the current state by following the chain of fingerprints through `fix_history`.

**Singles before pairs; dimmed pairs skipped without solving.** Every problem type only removes options. A pair can never do better than its worst single. Skipping is correct and cheap; a test asserts this on the example.

**Deterministic time limit (`max_deterministic_time`) not wall clock.** Results are machine-independent. The locked test asserts the example produces no question marks.

**One AI call returns both the explanation and the fix suggestions.** Fewer round trips; the explanation and fixes are consistent because they came from the same context. The checker's facts are always shown regardless; the AI adds only the plain sentence.

**Turned-down reasons from the checker, not the AI.** The checker shows the loading gap directly: “Van back 10:45. Loading team gone.” This is more honest and more useful than a generated reason.

**Preview draws from stored fix results.** `suggest-fixes` returns full per-scenario results, not counts. The browser draws the projected grid without re-solving. Accepting a previewed fix replays from the cache.

**`example-truth.json` is hand-authored; `test_example_locked.py` runs against it.** The locked test does not depend on the AI. Checker and locked test can be built and pass before any AI work. The bakeoff compares providers against the truth map, not against each other's output.

### One Genuine Uncertainty Discussed

**Correction cascades in the validation gate.** When a user corrects Ravi's role to "can't drive," any route with Ravi as driver should lose its confirmed mark. The question was how the rules handle this without re-running the AI.

Agreed answer: entities are referenced by internal `id`, never by name. The rules engine walks the whole map on every change and flags any item whose constraints are no longer satisfied. No partial re-run; the whole map is re-validated from scratch every time. Simple to reason about and correct by construction.

Verified by: `test_rules.py` includes a case where a person's `can_drive` is set to false after their route assignment is confirmed. The test asserts the route loses its confirmed mark and a rule fires reporting a missing driver.

### Open Issues

- **Gemini structured output parameter name, resolved.** The installed SDK supports `models.generate_content` with `response_mime_type` and `response_json_schema`. The finding is recorded in `gemini_provider.py` and covered by the provider tests.
- **`openapi-typescript` generation step** is manual for the PoC. A CI step would catch drift; out of scope.
- **Bakeoff result:** Gemini is primary after the 19 October 2026 read-v3 verdict-only re-score: 100/100 mean verdicts and 94.34% aligned fields; Groq has 55/100 and 84%. See `server/config.py` and `ai-reading-review.md`.
