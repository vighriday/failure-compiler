---
doc: spec
status: approved
---

# Failure Compiler - Technical Spec

## How This Works, In Plain Language

The app is a browser page talking to a small Python server running on your laptop. The server binds to 127.0.0.1 only, because it holds AI keys in memory.

When you paste a plan, the server sends it to an AI (Gemini first, Groq as a fallback). The AI's only job at that point is to read messy text and return a structured description of the plan: who is doing what, in what vehicle, at what place, between what times. That description comes back as JSON, and the server runs it through a strict format check before it touches anything else. If the JSON is wrong in any way - a missing field, an extra field, a name that does not exist - it gets rejected and you are told exactly why. This is the core learning goal made concrete: the AI produces output, the gate decides whether it is usable, and nothing downstream ever sees an unchecked map.

The AI returns an `AIPlanReading`. The server wraps it into a `PlanMap`, adding its own metadata: which provider answered, per-item status, and correction history. The two schemas are separate so Groq strict mode never forces the AI to invent a fingerprint or a fix history.

Once the map passes the format check, the server runs plain rules and surfaces any failures as questions on screen. The browser calls `POST /api/validate-map` on every correction (debounced, fast, same Python code that runs at Confirm). The user confirms or corrects using constrained choices only. Corrections go directly into the map; the AI does not re-read.

When everything is confirmed and all rules pass, the browser sends the map to `POST /api/confirm-map`. The server re-validates and returns a fingerprint: a SHA-256 hash of the canonical sorted checker inputs (people, vehicles, places, deliveries, routes, finish time, problem sizes). Two identical plans get the same fingerprint; changing a problem size changes it. Timestamps and status marks are excluded.

The checker then runs. It is a constraint solver (CP-SAT) that treats the plan as a scheduling problem. Singles run first. Any pair that contains a single already broken is marked dimmed without solving, because every problem type only removes options, so a pair can never be better than its singles. For remaining pairs, the solver tries to find the best possible schedule using only the people and vehicles the plan names. If it can find one where everyone finishes on time, the plan survives. If the best it can find is still late, the plan breaks, and the lateness is the human cost - proved optimal. The time limit is CP-SAT's deterministic limit (`max_deterministic_time`), not wall clock, so results are the same on every machine.

Some scenarios leave a route with no available driver, or the loading area with no key holder. Rather than returning "infeasible" with no number, every route may also be "not delivered," carrying a penalty larger than any possible lateness: households times the full horizon (finish time plus 180 minutes). The solver always returns a schedule. "Not delivered" becomes part of the human cost: "Routes A, B, C: 30 households not delivered. Nobody can open the loading area." Tick, cross, and question mark keep their meaning.

After the format gate, the server normalises all entity ids to stable slugs derived from type and name (e.g. `person-ravi`, `vehicle-van`, `route-c`) and updates every reference. This means two runs of the same plan always produce the same fingerprint regardless of what the AI chose as ids. The gate also rejects duplicate ids.

When you click a cross, one AI call fetches both the plain explanation and up to three fix suggestions together. The server caches the result per fingerprint and scenario, so reopening a cross never calls the AI again. The checker's facts (timeline, late routes, minutes late, or "not delivered") are always shown; the AI sentence sits next to them, labelled as the AI's explanation. Fix suggestions use a fixed list of operations so they can always be gated. Turned-down reasons come from the checker, not the AI.

Preview never re-solves. `suggest-fixes` returns each fix's full per-scenario results, not just counts. Preview draws from that. Accepting a previewed fix replays from cache with the flip animation.

The example plan ships with a saved AI reading and saved fix suggestions, so the full flow runs without an AI key.

## The Core Journey Through the System

PRD ref: `prd.md > The Core Journey`.

1. User pastes a plan (or loads the example). The browser sends the text to `POST /api/read-plan`. In example mode the server returns the saved fixture from `fixtures/example-reading.json` without making any AI call.

2. Server calls the AI. Groq (`openai/gpt-oss-120b`, strict structured output against `AIPlanReading`) gets one attempt. On rate limit, server error, timeout, or format-check failure, the server tries Gemini (`gemini-3.8-flash`). One attempt each. On both failing, the PRD error state returns to the browser.

3. Format gate runs. The raw AI JSON is parsed and validated against `AIPlanReading` (`extra="forbid"`, all fields required). Duplicate ids are rejected. Reference integrity check: every id used in routes and jobs must exist in the entity lists. Failure returns a `422` with the specific rejection reason.

4. Server normalises all entity ids to stable slugs from type and name (`person-ravi`, `vehicle-van`, `route-c`) and updates every reference. Then wraps the reading into a `PlanMap`, setting every item's status to `unconfirmed` and recording the AI's original value for each.

5. Plan map screen renders. The browser displays the checklist view, the structured reading with source lines, and the "What we'll test" list.

6. User confirms or corrects. Every correction triggers `POST /api/validate-map` (debounced 150 ms). The server returns updated item statuses and rule failures. Affected items lose their confirmed mark. The Confirm button state is computed from the current map state, never stored.

7. User hits Confirm. The browser sends the full map to `POST /api/confirm-map`. The server runs the gate and rules one final time. On pass, it returns the fingerprint. On failure, it returns the specific failing rule.

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

Model names live in `server/config.py`. Fallback triggers: rate limit, server error, timeout, or format-check failure on the primary's output. One attempt per provider.

The Gemini adapter uses `google-genai` `models.generate_content` with `response_mime_type` and `response_json_schema`, verified against the installed SDK.

Every AI result records provider and model; shown as "Read by [provider/model]" on the plan map and in the report.

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
| Type sync | `openapi-typescript` from FastAPI's `/openapi.json` | Frontend types generated from backend schema; drift is a compile error. |

Rules are implemented only in Python (`server/validation/rules.py`). The browser never reimplements them; it calls `POST /api/validate-map` instead.

## Where It Runs and How Someone Tries It

Runtime: local, two processes. Started with one cross-platform command (PowerShell-compatible, no `make`).

Start command (after `uv sync` and `npm install`):
```
python scripts/dev.py
```
This starts `uvicorn server.main:app --host 127.0.0.1 --port 8000` and `vite --port 5173` in parallel. The server binds to 127.0.0.1 only because AI keys are held in memory.

What to open: `http://localhost:5173`

Demo recording: load the example plan, walk the full flow (paste / plan map / crash test / open a cross / preview the turned-down fix / accept the real fix / report), record the screen. No deployment needed.

Submission: short demo video plus public GitHub repository. Deployment is optional and explicitly post-PoC.

Environment requirements:
- Python 3.12 (managed by uv)
- Node.js 20+
- `GROQ_API_KEY` and/or `GEMINI_API_KEY` in `.env` (not needed for example mode)
- `.env.example` ships with placeholders; `.env` is gitignored

Free tier constraints:
- Groq: 30 req/min, 1,000 req/day, 8,000 tokens/min, 200,000 tokens/day. Pasted plans capped at ~4,000 characters; visible counter on Screen 1. Prompts kept lean; reasoning at lowest setting.
- Gemini free tier: Google may use content to improve its products. Screen 1 shows one line when a Gemini key is present: "If you use a Gemini key, don't paste personal details - Google may use them to improve its models. The example plan is fictional."

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
- **Routes:** households, `load_minutes` (needs a loader present), `drive_minutes` (needs a driver and a vehicle). Jobs are filled only from `driver_ids` and `loader_ids` in the route - primary first, then listed backups. No one else may fill those jobs. Start times can move freely within people's and vehicles' availability windows.
- **Finish time:** soft deadline. The solver minimises total households-times-minutes-late.

The checker evaluates “Add Maya as backup driver for Route C” and turns it down because the gap is loading, not driving. Its reason is “Van back 10:45. Loading team gone.”

### How the checker decides

- Proven zero lateness: **tick.** Zero is the floor; finding zero proves the plan survives.
- Proven minimum above zero: **cross.** The minimum is the human cost - e.g. “Route A: 10 households not delivered” or “Route C: 8 households not delivered.” Proved optimal.
- **Not delivered** routes use a penalty lateness of households times the full horizon (finish time plus 180 minutes), keeping every scenario feasible. Human cost reads "Routes A, B, C: 30 households not delivered. Nobody can open the loading area" Still a cross; tick and question mark keep their meaning.
- Deterministic time limit hit before either is proved: **question mark.** Uses `max_deterministic_time`, not wall-clock seconds, so results are the same on every machine. Never counted as survived. Listed by name in the report under "What was NOT tested."

### Run order

Singles run first, in problem-id order. Any pair that contains a single already marked as a cross is marked **dimmed** without solving - valid because every problem type only removes options, so a pair can never do better than its worst single. Remaining pairs are solved. This keeps one weak spot from flooding the grid with redundant crosses.

One solver worker, fixed seed. The same confirmed map always gives the same results.

### Correctness test

`test_checker_monotone.py` checks on the example map that every pair's lateness is at least each of its singles'. The locked test also asserts the example has no question marks.

## Explain and Fix

Implements `prd.md > Broken Case Detail Panel`, `prd.md > Fix Cards and Scoring`.

One AI call per broken case: `POST /api/suggest-fixes` sends the confirmed map plus the checker's facts for that case (the two failing problem ids, the timeline, the late routes, lateness in minutes, or "not delivered" if applicable). The AI returns one plain explanation sentence and up to three fix suggestions. The server caches the result keyed by fingerprint and scenario id, so reopening a cross never calls the AI again.

The checker's facts are always shown in the panel. The AI's sentence sits next to them, labelled "AI's explanation."

Turned-down reasons come from the checker, not the AI. “Add Maya as backup driver for Route C” is turned down because the gap is loading, not driving; the checker gives “Van back 10:45. Loading team gone.” The fixes are “Sam loads Route C” and “Sam backs up Route A.” One spare key is turned down because it reveals Joel absent + Maya absent; spare keys for Maya and Sam make all 100 scenarios survive.

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

`fixtures/example-fixes.json` stores the explanation and fix results for each broken case in the example plan. They still pass through the gate and are scored live. If a broken case appears that has no saved suggestion (e.g. a case uncovered after a fix is accepted), the panel says: "No saved suggestions for this case. Add a key to ask the AI." Requesting new suggestions also requires a key.

## Components

### Screen 1: Paste Plan
Implements `prd.md > Paste and Load`, `prd.md > Screen 1`.

Single `<textarea>` with a character counter (cap ~4,000; amber at 3,500, red at 4,000, submit disabled above). "Load example" button. AI key field(s) shown if no key is set in the environment. One-line Gemini data notice when a Gemini key is present.

Connects to: `POST /api/read-plan`.

### Screen 2: Plan Map
Implements `prd.md > AI Reading and Structured Map`, `prd.md > Plain Rules Validation`, `prd.md > Screen 2`.

Three sections stacked vertically:

**Checklist view (top):** computed from the confirmed map - every job with a person and a backup, all ticked. This is the "it looks done" view. The summary "AI read 24 items, 2 corrected by you, 1 added by you" is computed from item `status` fields.

**Structured reading (middle):** one statement per map item, with its `source_line`. Three visual states: default (status `unconfirmed`), corrected (AI's `original_value` struck through, correction marked "corrected by you"), added (no source line, marked "added by you"). Confirmed items get a small confirmed mark. Corrections use constrained inputs only: `<select>` from known entity ids, time picker for times. No free-text fields. Every correction triggers `POST /api/validate-map` (debounced 150 ms). Affected items that depend on the changed item lose their confirmed mark and show "check this, [name] changed."

**Place identity question:** an unused place listing alongside a loading or supply place requires an individual choice: keep separate, or select the same existing place. Only a listing with no loading activity and no delivery references can be merged. The server preserves its entity, source rows and question references for undo, retains the selected place's label and details, and requires its facts to be reviewed individually again. The raw reading is unchanged. This review operation does not change the checker model or infer aliases from the truth fixture.

**"What we'll test" (bottom):** each problem instantiated against confirmed map entities, with preset size picker. Confirmed alongside the plan with the same Confirm button.

Confirm button: disabled until every item is confirmed and all rules pass. "Read by [provider/model]" label. On click, sends map to `POST /api/confirm-map`.

### Screen 3: Crash Test Grid
Implements `prd.md > Live-Filling Grid`, `prd.md > Screen 3`.

CSS grid. Failure types on both axes; one triangle (diagonal + below). Cells update as SSE events arrive. Four states rendered as SVG marks plus CSS classes: `tick`, `cross`, `dim`, `qmark`. Count line updates live. Before/After toggle appears after first accepted fix. Preview banner when a fix is being previewed.

Connects to: `GET /api/run-tests` (SSE stream).

### Screen 4: Broken Case Detail Panel
Implements `prd.md > Broken Case Detail Panel`, `prd.md > Fix Cards and Scoring`, `prd.md > Screen 4`.

Right-side panel; grid stays fully interactive. Contents: checker's facts (failures, timeline, human cost), AI's explanation sentence (labelled), fix cards. Fix cards pre-scored from stored per-scenario results. "Turned down" with checker-derived reason when a fix does not solve the case or creates a new cross. Accept enabled only for eligible fixes. Preview draws from stored results.

Connects to: `POST /api/suggest-fixes`, `POST /api/apply-fix`, new SSE stream.

### Screen 5: Report
Implements `prd.md > Screen 5`, `prd.md > The Checker's Three Honest Answers`.

Six sections as specified in the PRD. "Print or save as PDF" triggers `window.print()` with a `@media print` stylesheet that removes nav and controls. "Read by" attribution included. Fingerprint in the footer.

Connects to: `GET /api/report`.

## Data Model

All shapes defined in `server/models.py` as Pydantic v2 with `extra="forbid"`. TypeScript types generated from FastAPI's OpenAPI output via `openapi-typescript`. Neither side can drift.

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
  finish_time_source:   str             # Source line in the original text
  finish_time_guessed:  bool
  questions:            list[AIQuestion]   # Ambiguities the AI wants to surface
  is_distribution_plan: bool
  not_distribution_reason: str | None   # Non-null if is_distribution_plan is false
```

Each entity in the reading carries `source_line: str` and `guessed: bool`. Example:

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
  guessed:        bool   # True if the AI inferred this person was present

AIRoute
  id:             str
  name:           str
  households:     int
  load_minutes:   int
  drive_minutes:  int
  vehicle_id:     str    # References a Vehicle id
  driver_ids:     list[str]   # Primary first, then backups. References Person ids.
  loader_ids:     list[str]   # Primary first, then backups. References Person ids.
  source_line:    str
  guessed:        bool

AIQuestion
  item_id:        str    # The entity this question is about
  question_text:  str
```

(AIVehicle, AIPlace, AIDelivery follow the same pattern: id, name, timing fields, source_line, guessed. AIPlace also carries `opens_at`.)

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

The summary "AI read 24 items, 2 corrected by you, 1 added by you" is computed from status counts at render time.

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

No database. Confirmed maps, test results, and fix suggestion results are held in server memory keyed by fingerprint. Closing the tab loses the session - by design.

## Fixtures and the Locked Test

`fixtures/example-truth.json`: the correct confirmed map for the Saturday food distribution plan. Written by hand. This is the ground truth.

`fixtures/example-reading.json`: the chosen provider's real output for the example plan, saved as-is. It may have small mistakes; the demo corrects them, which shows the correction trail working.

`fixtures/example-fixes.json`: the saved explanation and per-scenario fix results for each broken case in the example plan.

`fixtures/expected-results.json`: the hand-checked expected verdict and human cost for every cell of the example plan.

### What the tests assert

`test_example_locked.py`: loads `fixtures/example-truth.json`, runs the checker, compares every cell's verdict and human cost against `fixtures/expected-results.json`. The locked test can be built and pass before any AI work. Also asserts the example has no question marks.

`test_checker_monotone.py`: on the example map, asserts that every pair's lateness is at least each of its singles'.

`test_reading_matches_truth.py`: loads the unedited `fixtures/example-reading.json`, checks its saved digest, applies the explicit actions from `example-corrections.json` through the review controls, aligns entities by type and role, then compares every checker input and all 100 full scenario results with `fixtures/example-truth.json`. Names are labels and are excluded. It also asserts that the actual map generates 100 scenarios; extra or missing checker entities must not be silently discarded.

`test_format_gate.py`: bad JSON, extra fields, unknown names, wrong types - all rejected with a specific reason.

`test_rules.py`: missing driver, incoherent times, key holder absent, plan over cap, etc. Includes a case where a person's `can_drive` is flipped after their route assignment is confirmed - asserts the route loses its confirmed mark and a rule fires.

`test_determinism.py`: runs the example truth map twice and compares every result.

`bakeoff.py`: runs the example plan through both providers three times. It aligns entities by type and role, ignores names, compares every checker input (including extra inputs), and runs the truth map's 100 scenarios on the aligned reading. It ranks providers by exact full-result matches, aligned field match, consistency, then tokens. It applies no corrections and preserves raw responses and failed attempts. Every prompt version and its scores are logged in `ai-reading-review.md`; the winner becomes primary in `server/config.py` with the date and scores.

## File Structure

```
failure-compiler/
├── server/
│   ├── main.py                  # FastAPI app; all API routes
│   ├── models.py                # All Pydantic models: AIPlanReading, PlanMap,
│   │                            # ScenarioResult, FixSuggestion, FixOperation
│   ├── config.py                # AI model names, size presets, problem type defs, cap
│   ├── ai/
│   │   ├── adapter.py           # Public interface: read_plan(), suggest_fixes()
│   │   ├── groq_provider.py     # Groq call (AIPlanReading schema, strict mode)
│   │   ├── gemini_provider.py   # Gemini call (verify response_schema param at build)
│   │   └── prompts.py           # Prompt templates; reasoning at lowest setting
│   ├── validation/
│   │   ├── gate.py              # Full gate: parse, Pydantic, references, rules
│   │   └── rules.py             # Plain rules; the only implementation of rules
│   ├── checker/
│   │   ├── runner.py            # Singles then pairs; dimmed pairs skipped; SSE stream
│   │   ├── solver.py            # One CP-SAT run; max_deterministic_time; fixed seed
│   │   └── scenarios.py        # Generates singles + pairs from problem list
│   └── session.py                # In-memory: fingerprint -> {map, results, fix_results, fix_suggestions_cache}
├── web/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── client.ts        # Typed fetch + SSE; types from generated schema
│   │   ├── components/
│   │   │   ├── PastePlan/
│   │   │   ├── PlanMap/
│   │   │   │   ├── ChecklistView.tsx      # Computed from item status counts
│   │   │   │   ├── StructuredReading.tsx
│   │   │   │   ├── CorrectionInput.tsx    # select + time picker only
│   │   │   │   └── WhatWeTest.tsx
│   │   │   ├── CrashTest/
│   │   │   │   ├── Grid.tsx
│   │   │   │   ├── GridCell.tsx           # SVG marks
│   │   │   │   └── CountLine.tsx
│   │   │   ├── BrokenCase/
│   │   │   │   ├── DetailPanel.tsx
│   │   │   │   ├── Timeline.tsx           # SVG; finish line in red
│   │   │   │   └── FixCard.tsx            # Preview draws from stored results
│   │   │   └── Report/
│   │   │       └── ReportPage.tsx
│   │   ├── state/
│   │   │   ├── reducer.ts        # All map mutations; preview state
│   │   │   └── types.ts          # App state wrapping generated API types
│   │   └── styles/
│   │       ├── tokens.css
│   │       └── *.css
│   ├── scripts/
│   │   └── gen-types.ts          # openapi-typescript against live server
│   ├── index.html
│   ├── vite.config.ts
│   └── tsconfig.json
├── fixtures/
│   ├── example-plan.txt          # The Saturday food distribution plan (messy text)
│   ├── example-truth.json        # Correct confirmed map, written by hand
│   ├── example-reading.json      # Chosen provider's real output, saved as-is
│   ├── example-fixes.json        # Saved suggestions for each broken case
│   └── expected-results.json     # Hand-checked verdicts for all 100 cells
├── scripts/
│   ├── dev.py                    # Starts both servers; 127.0.0.1 only
│   └── bakeoff.py                # Compares both providers against example-truth.json
├── tests/
│   ├── test_example_locked.py    # Checker on truth map vs expected-results.json
│   ├── test_checker_monotone.py  # Pair lateness >= each of its singles'
│   ├── test_reading_matches_truth.py  # Reading + corrections == truth map
│   ├── test_format_gate.py       # Gate rejects bad JSON, extra fields, unknown names
│   ├── test_rules.py             # Rules engine; including the cascade test
│   └── test_determinism.py       # Same truth map run twice; identical results
├── devpost/
├── pyproject.toml                # uv project; ruff config
├── package.json
├── .env.example                  # GROQ_API_KEY=, GEMINI_API_KEY=
├── .gitignore
├── LICENSE                       # MIT
└── README.md
```

## External Services and Dependencies

### Groq - Fallback AI provider
- Endpoint: `POST https://api.groq.com/openai/v1/chat/completions`
- Auth: `Authorization: Bearer $GROQ_API_KEY`
- Structured output: `response_format: { type: "json_schema", json_schema: { strict: true, schema: <AIPlanReading JSON schema> } }`
- Rate limits (free tier): 30 req/min, 1,000 req/day, 8,000 tokens/min, 200,000 tokens/day
- Docs: https://console.groq.com/docs/openai
- Key: `GROQ_API_KEY` in `.env`

### Gemini - Primary AI provider
- SDK: `google-genai` (official)
- Model: `gemini-3.8-flash`
- Structured output: `models.generate_content` with `response_mime_type` and `response_json_schema`, verified against the installed SDK.
- Free tier note: content may be used by Google. Screen 1 discloses this.
- Docs: https://googleapis.github.io/python-genai/
- Key: `GEMINI_API_KEY` in `.env`

### OR-Tools 9.15
- Install: `uv add ortools==9.15.*`
- Wheels for Windows, macOS (Intel + Apple Silicon), Linux. No API key; runs locally.
- Docs: https://developers.google.com/optimization/reference/python/sat/python/cp_model

## Important Failure Modes

Implements `prd.md > States and Boundaries`.

- **Both AI providers fail** - clear error message, retry button, "try the example plan instead." Applies to both read-plan and suggest-fixes paths.
- **AI output fails the format gate** - "The AI's reading did not pass the format check" plus the specific reason (e.g. "Unknown person id 'dave' in route_a driver_ids" or "Duplicate id 'person-ravi'") plus a retry button. Nothing unchecked reaches the plan map.
- **A fix suggestion fails the gate** - card shows "Couldn't apply" with the specific reason. Never scored, never acceptable.
- **`is_distribution_plan` is false in the reading** - "This version only supports community distribution plans" plus the AI's reason. Offer to load the example.
- **Solver hits the deterministic time limit** - question mark cell. Listed by name under "What was NOT tested." Never a pass.
- **Plan exceeds 24 problems** - rule message on Screen 2 before Confirm: "This version supports up to 24 problems. This plan has N."
- **Plan text exceeds ~4,000 characters** - counter turns amber at 3,500, red at 4,000, submit disabled above 4,000.
- **AI key invalid or call fails** - clear error message, retry button, suggest example plan.

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
- **Bakeoff result:** Gemini is primary after the 17 October 2026 read-v3 comparison: 43/100 mean exact results and 90.57% aligned fields; Groq has 12/100 and 82%. See `server/config.py` and `ai-reading-review.md`.
