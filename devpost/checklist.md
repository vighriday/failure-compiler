---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast

## Slices

- [x] **1. The checker proves the example plan's story**
  Becomes usable: A CLI command prints the 100-scenario grid and count line: 1 single weak spot, 3 hidden pairs, 12 dimmed, 84 survived. All checker tests pass. The fix story is locked.
  Why now: The checker is the unique kernel. If CP-SAT can't prove the story (the single break, the three hidden pairs, the turned-down fix, the real fix), nothing else matters. This also writes the data models, fixtures, and scenario generator that every later slice builds on.
  PRD ref: `prd.md > The Checker's Three Honest Answers`
  Spec ref: `spec.md > Checker: What It Models and How It Decides`, `spec.md > Problem Type Taxonomy`, `spec.md > Fixtures and the Locked Test`
  Build: uv project (Python 3.12, ortools 9.15, pydantic, pytest, ruff); `server/models.py`; `server/config.py`; `server/checker/scenarios.py`, `server/checker/solver.py` (not-delivered penalty, `max_deterministic_time`, fixed seed, singles then feasible pairs only, skipping same-entity combinations, with dimming), `server/checker/runner.py`; a small CLI (`scripts/check_map.py`) that prints the grid and count line for a map file; `fixtures/example-plan.txt`, `fixtures/example-truth.json`, `fixtures/expected-results.json`; `LICENSE` (MIT); `.env.example`. Apply the spare-key correction to `spec.md` ("Give a spare key to a person": `holds_key` becomes true, existing holders keep theirs) and log it under Revisions. Targets: no problems -> plan survives; exactly 14 problems (5 volunteers x {absent, leaves early} + van returns late + car returns late + supply truck late + loading area blocked); only "Joel absent (only key holder)" breaks as a single (Routes A, B, C: 30 households not delivered. Nobody can open the loading area); three hidden pairs break: "Supply truck late + Ravi absent" (Route A: 10 households not delivered), "Van late + Anita leaves early" (Route C: 8 households not delivered), and "Van late + Anita absent" (Route C: 8 households not delivered); 12 Joel pairs dimmed; 84 scenarios survive; total 1 + 3 + 12 + 84 = 100. The example plan has Route A with 10 households, Route B with 12, and Route C with 8; the van returns from an early pickup at 9:30; Joel has the only key and leaves at 10:30; Maya leaves at 10:45; Sam is not on the loading team. Generate `expected-results.json` from the checker after reasoning through all 4 crosses. `test_example_fixes` outcomes: (a) adding Maya as backup driver for Route C is turned down because the gap is loading, not driving; (b) "Sam loads Route C" and "Sam backs up Route A" fix all three hidden pairs with no new crosses; (c) one spare key is turned down because it reveals "Joel absent + Maya absent"; (d) spare keys for Maya and Sam fix Joel and every re-tested Joel pair survives; (e) all fixes together: all 100 scenarios survive.
  Verify (mechanical): `uv run -- python -m pytest -q` passes; `test_example_locked` includes reasoning comments for all 4 crosses. `uv run python scripts/check_map.py fixtures/example-truth.json` prints exactly "100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak spot, 84 survived."
  Learner check: Run the CLI on the truth map and read the count line.
  Commit: `Add checker, truth map, locked tests, fix-story tests, LICENSE, .env.example`

- [x] **2. The gate rejects bad AI output and the rules catch broken maps**
  Becomes usable: The format gate rejects malformed, extra-field, duplicate-id, and unknown-reference AI output with specific reasons. The rules engine catches missing drivers, incoherent times, key-holder absence, and the 24-problem cap. Dependent items lose confirmed status on upstream changes. The fingerprint function produces stable hashes.
  Why now: The gate is the second half of the learning-goal pipeline. It must work before any AI reading can land safely, and the fingerprint is how every later slice keys cached results.
  PRD ref: `prd.md > Plain Rules Validation`, `prd.md > AI Reading and Structured Map`
  Spec ref: `spec.md > The Validation Gate`, `spec.md > Data Model`
  Build: `server/validation/gate.py` (parse JSON, Pydantic validation with `extra="forbid"`, duplicate and unknown id rejection, id normalisation to stable slugs; gate errors name the field and bad value, e.g. `Unknown person id 'person-dave' in route-c driver_ids`); `server/validation/rules.py` (every route has a driver and vehicle, `driver_ids` entries must have `can_drive: true`, coherent times, explicit finish time, 24-problem cap); dependent items losing confirmed status when an upstream item changes; fingerprint function (SHA-256 of canonical sorted checker inputs, excluding timestamps and status).
  Verify (mechanical): `uv run -- python -m pytest -q` passes, including the cascade case: set Ravi's `can_drive` to false in a confirmed map built from the truth map; every route listing Ravi loses its confirmed mark, and a rule issue names Ravi. Fingerprint assertions: (1) shuffle people, vehicles, and routes, preserve each route's `driver_ids` and `loader_ids` order, rename all IDs to AI-style IDs and update references, then normalise IDs; fingerprint equals the truth map. (2) Change `problem_sizes["vehicle_returns_late"]` from 30 to 45; fingerprint differs. (3) Change item status marks, AI metadata (provider, model, timestamp), or source lines; fingerprint stays the same.
  Learner check: Run the tests and read one rejection message.
  Commit: `Add validation gate, rules engine, fingerprint, and tests`

- [x] **3. Plan map in example mode**
  Becomes usable: Load the example plan, see Screen 1, then Screen 2 with the AI's structured reading, correct an item, watch dependent items lose confirmation, and press Confirm. The full validation pipeline runs end to end in example mode using a hand-made reading fixture.
  Why now: This is the first time the app runs in a browser. Example mode means no AI-provider dependency, so the demo path works with zero keys.
  PRD ref: `prd.md > Screen 1: Paste Plan`, `prd.md > Screen 2: Plan Map`, `prd.md > Look and Feel`
  Spec ref: `spec.md > Components`, `spec.md > Look and Feel`
  Build: FastAPI app on 127.0.0.1 (`server/main.py`): `POST /api/read-plan` returns the saved hand-made example reading, initially 0 of 24 confirmed, one guess and one individual question; `POST /api/validate-map` and `POST /api/confirm-map`. React + Vite + TypeScript (`web/`), IBM Plex fonts, `scripts/dev.py`. Screen 1: paper textarea, line numbers, counter, “Read plan” and a secondary “Load the example plan” that only fills the textarea; collapsed key field and data notice. Screen 2: sticky source plan with source-line highlights; checklist naming each route driver and backups; sourced People, Vehicles, Routes, Times; constrained correction/guess inputs; rule questions; 14 problems with preset sizes. All items start unconfirmed; bulk confirm skips guesses and questions; dependency changes show “Check this: <name> changed”; confirm disabled until all items, questions, and rules pass.
  Verify (mechanical): `uv run -- python -m pytest -q` passes; `npm run build` passes; Playwright at 1440x900 verifies Screen 1 empty and example-loaded, Screen 2 load, bulk-confirm, correction cascade, and ready-to-confirm states with full-page screenshots in `devpost/screens/`, then confirms the map and checks for page errors.
  Learner check: Load the example, correct one item, watch dependent items lose confirmation, confirm.
  Commit: `Add example-mode plan map with Screen 1, Screen 2, and dev server`

- [x] **4. The grid fills live**
  Becomes usable: After confirming the map, the crash-test grid fills cell by cell over SSE. The example plan's story is visible on screen: one cross on the diagonal, three crosses off-diagonal, dimmed marks, ticks. The count line updates live.
  Why now: Connects the confirmed map to the checker from slice 1, streamed to the browser. The grid is the emotional core of the demo.
  PRD ref: `prd.md > Screen 3: Crash Test`, `prd.md > Live-Filling Grid`
  Spec ref: `spec.md > Checker: What It Models and How It Decides`, `spec.md > Components`
  Build: `GET /api/run-tests?map={fingerprint}` SSE endpoint with results cached by fingerprint in `server/session.py`; Screen 3: CSS-grid triangle layout, four SVG cell marks (tick, cross, dim, qmark), live count line, plan-survives-first-run message and "See report" link; `prefers-reduced-motion` check skips cell-fill animation.
  Verify (mechanical): Confirm the example map -> grid fills with exactly 1 cross on diagonal, 3 off-diagonal crosses, 12 dimmed, 84 ticks; count line reads "100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak spot, 84 survived."
  Learner check: Watch the grid fill, check the count line, click around the grid.
  Commit: `Add live SSE crash-test grid`

- [x] **5. Broken case, fixes, flip**
  Becomes usable: Click a cross, and the detail panel slides in with the timeline, human cost, and fix cards. The turned-down fix shows a checker-derived reason. The real fix previews on the grid and, when accepted, flips cells and re-tests. After all fixes, 100 ticks.
  Why now: Completes the core journey narrative. With slices 3 to 5 done the full demo is recordable without any AI provider.
  PRD ref: `prd.md > Screen 4: Broken Case Detail (panel)`, `prd.md > Fix Cards and Scoring`, `prd.md > Fix Preview`, `prd.md > Fix Acceptance and Re-test`
  Spec ref: `spec.md > Explain and Fix`, `spec.md > Components`
  Build: `POST /api/suggest-fixes` in example mode (loads `fixtures/example-fixes.json`, gates and scores each fix live); checker-derived turned-down reasons (which resource the late route was waiting on); "Couldn't apply" state for fixes that fail the gate. Screen 4: right-side panel with grid staying interactive; SVG timeline with routes as horizontal bars and "Noon: families waiting" finish line in red; human cost; labelled "AI's explanation" sentence; fix cards with scores and turned-down labels. Preview from stored per-scenario results (no re-solve); `POST /api/apply-fix` producing new fingerprint and `AppliedFix` chain; flip animation with `prefers-reduced-motion` check. "Next broken case (N left)" button; "All 100 tested scenarios survive" then "See report"; "No saved suggestions for this case. Add a key to ask the AI." state.
  Verify (mechanical): Click each cross, and the panel shows correct facts and fixes; turned-down fix shows reason; preview draws projected grid; accept real fixes in sequence, and the grid reaches 100 ticks; cancelled preview restores grid exactly.
  Learner check: Play the whole demo story through to all ticks.
  Commit: `Add detail panel, fix cards, preview, accept, and flip`

- [x] **5a. Hardening after the Oct 17 audit**
  Becomes usable: Server-owned confirmation, order-independent results and caches, reliable re-confirmation, current facts after fixes, and constrained correction for every supported fact.
  Why now: Repair the verified audit findings before accepting live AI readings.
  PRD ref: `prd.md > Plain Rules Validation`, `prd.md > AI Reading and Structured Map`, `prd.md > Fix Acceptance and Re-test`
  Spec ref: `spec.md > The Validation Gate`, `spec.md > Data Model`, `spec.md > Checker: What It Models and How It Decides`
  Build: Implement the user-approved hardening A through F; preserve landing/design, the example display order, scenario ids, grid and expected-results fixture. Add regressions for every fix; bring full-repository ruff to zero, sync affected docs and report the requested Git-history check.
  Verify (mechanical): `uv run -- python -m pytest -q`, `uv run -- ruff check .`, production frontend build and browser regressions for Read-tab edits, every correction type and facts after all three fixes.
  Learner check: Review the hardening evidence and try corrections before the live AI work.
  Commit: `Harden confirmation, corrections, validation and cached results`

- [ ] **6. Live AI**
  Becomes usable: Paste your own plan with an AI key, and the AI reads it, the gate checks the output, the map renders. Fix suggestions come from the AI, not a fixture. Both providers work with fallback.
  Why now: Provider quirks are contained in one slice. Slices 3 to 5 already give a recordable demo, so AI integration can't block the Oct 20 deadline.
  PRD ref: `prd.md > States and Boundaries`
  Spec ref: `spec.md > External Services and Dependencies`, `spec.md > Important Failure Modes`
  Build: `server/ai/adapter.py` (public `read_plan()`, `suggest_fixes()`), `server/ai/groq_provider.py` (strict structured output against `AIPlanReading`), `server/ai/gemini_provider.py` (verify `response_schema` vs `response_format` against installed SDK), `server/ai/prompts.py`; fallback logic (Groq first, Gemini on rate limit / server error / timeout / format-check failure, one attempt each); `POST /api/read-plan` and `POST /api/suggest-fixes` in live mode; suggestion cache per fingerprint + scenario id; `scripts/bakeoff.py` (both providers x 3, compare raw reading against truth, record winner in `config.py`). Error states: invalid key, failed format check with specific reason and retry, `is_distribution_plan: false` with AI's reason, "None of these fixes worked" with one-retry option. Gemini data notice on Screen 1; "Read by [provider/model]" label on Screen 2 and in the report. Replace `fixtures/example-reading.json` with real AI output; add `tests/test_reading_matches_truth.py` (reading + scripted demo corrections = truth map).
  Verify (mechanical): Paste the example plan with a Groq key: reading returned, gate passes, map renders, corrections work, Confirm, grid fills; `uv run -- python -m pytest -q` passes, including `test_reading_matches_truth`. Kill Groq key: Gemini fallback works. Invalid key: clear error and retry button.
  Learner check: Paste a plan of your own and watch it get read, gated, and confirmed.
  Commit: `Add Groq and Gemini adapters, bakeoff, live read-plan and suggest-fixes`

- [ ] **7. Report, Before/After, polish, README**
  Becomes usable: The full report renders with all six sections, the Before/After toggle compares original and fixed grids, browser print produces a clean PDF, and the README explains setup and usage.
  Why now: Last screen. Everything it draws from is already built and tested.
  PRD ref: `prd.md > Screen 5: Report`, `prd.md > Look and Feel`
  Spec ref: `spec.md > Components`
  Build: Screen 5 with six sections (plan with correction trail, what was tested, what broke, fixes with turned-down reasons, after fixes, what was NOT tested); example-mode notice; fingerprint in footer; `@media print` stylesheet removing nav and controls. Before/After toggle on the grid (reads `AppliedFix` chain to reconstruct original state). A design pass over every screen against `spec.md > Look and Feel` and `prd.md > Look and Feel`: colours, typography, mark rendering, motion, spacing. `README.md`: prerequisites, setup (`uv sync`, `npm install`), `python scripts/dev.py`, example mode, what the app does, what it does not claim.
  Verify (mechanical): Open the report with all six sections present with correct data; toggle Before/After and confirm the grid switches; `Ctrl+P` produces a clean print layout; open README and confirm instructions are correct and complete.
  Learner check: Print the report to PDF and read it.
  Commit: `Add report, Before/After toggle, print layout, design pass, README`

## Hands-on Checkpoints

- [ ] Hands-on checkpoint - after slice 5 (the complete demo story), I explore the running app and give feedback
- [ ] Final kick-the-tires exploration and feedback completed

## Final Review

- [ ] Final review complete - feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete - focused alternative: follow one AI reading from raw JSON through the gate, normalisation, rules, and confirmation to the checker
- [ ] Optional edit and transfer reflection addressed - offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: [what actually happened; real document/test/code references; unfinished work if interrupted]
Route and stops: [actual paths and symbols; guided stops completed, or reference-only route]
Edit outcome: [tried/kept/reverted/declined/not applicable; verification if changed]
Reflection: [offered/answered/declined/already covered - personal answer belongs only in the ignored profile]
Activity mode: [live app and editor, explicit static fallback, focused alternative, prior practice, or recap]

## Revisions
- Revised AI review, 17 October 2026, parts 1 to 5: the user approved role-aligned checker-field scoring, all 100 full-result comparisons, names as labels, constrained missing-fact questions, generic prompt revisions and three runs per provider. These are implemented and tested. read-v1 saved calls were rescored; read-v2 failures and retries were retained; read-v3 completed three successful readings per provider. Gemini becomes primary with 43/100 mean exact results and 90.57% aligned fields; Groq has 12/100 and 82%. `ai-reading-review.md` records every prompt version, scores, settings and raw report paths. Existing `.gitignore` and `oxcode.hooks.json` changes remain excluded.
- Slice 6 checkpoint, 17 October 2026: the provider adapter and strict-schema tests are implemented; six unedited bake-off readings are recorded in `devpost/bakeoff.json`. Gemini averaged 58.06% exact truth-field agreement; Groq 46.24%. `server/config.py` records Gemini as the dated bake-off winner while retaining Groq as the requested primary. The separate one-shot primary reading passed the format gate but omitted the delivery and used entity names that cannot be corrected with the approved controls. The required STOP condition applies. No fixture was replaced or committed, no real fix suggestions were requested after the stop, and live app integration remains pending. See `devpost/ai-reading-review.md` and the raw local output in ignored `devpost/screens/live-candidates/`. Slice 6 stays unchecked; slice 7 has not started. Current verification: 100 offline tests pass, Ruff clean.
- Hardening after the Oct 17 audit verified on 17 October 2026: 86 offline tests pass; whole-repository Ruff reports zero issues; the production TypeScript/Vite build passes. `scripts/verify_review.py` passes the top Read-tab and Plan map editing paths, all three accepted fixes, updated sentences and the at-a-glance box, and re-confirmation. `scripts/verify_story.py` passes the unchanged 100-cell example, turned-down fixes, three linked fingerprints and reduced motion, with no page errors. Confirmation uses a server-owned reading ID and explicit actions; missing or forged browser lists cannot bypass it. Sixteen correction types have separate regression cases; dependent route facts need individual re-confirmation. The shared loading-team editor changes the loaders shared across all routes and preserves route-specific assignments. The checker model, example display order, scenario IDs and `expected-results.json` remain unchanged. Functional editor wrapping keeps the new controls inside the existing panel; landing artwork, animation and design are unchanged. Evidence screenshots are in ignored `devpost/screens/hardening-current-facts.png` and `hardening-read-tab-reconfirm.png`. Git history audit across all reachable commits found no `devpost/learner-profile.md`, `.env` or ZIP paths. Existing `.gitignore` and `oxcode.hooks.json` changes remain excluded.
- Hardening after the Oct 17 audit: user approved repairs A through F before slice 6, each with regression coverage. Existing `.gitignore` and `oxcode.hooks.json` changes are unrelated and remain excluded. No landing or visual design changes are authorized in this pass. Slice 6 follows hardening; stop before committing real fixtures if the reading cannot be corrected with the controls or real suggestions change the demo story. Do not start slice 7.
- Repository audit on 2026-10-17 at `f00bf91`: all 113 tracked files inventoried; 45 tests, frontend build, both browser audits and the production fix story passed. Whole-repository lint has 20 issues. Additional probes found confirmation bypass through omitted request lists, mismatched cached scenario IDs after list reordering, Read-tab re-confirmation blocking, stale statements after spare-key fixes, limited correction controls and input-validation gaps. Resolve these before live AI; details and the remaining build work are in `audit-2026-10-17.md`, with per-file coverage in `audit-files-2026-10-17.md`. No completion boxes changed.
- Local startup timeout corrected on 2026-10-17: the launcher now allows 90 seconds, probes the API health response and web page, reports pending servers every five seconds, and names a server that exits or times out. A real launch completed in 5.11 seconds; API, web proxy, duplicate-launch rejection, the expected 100-scenario result and shutdown releasing both ports all passed. All 45 Python tests and lint for the changed Python files passed. Verification logs stay local in `devpost/screens/`.
- Startup correction on 2026-10-17: CP-SAT and its native dependencies now load only when checking a scenario. Measured API import time fell from 6.35 seconds to 1.32 seconds in consecutive local runs. A fresh-process regression proves the health endpoint can load without OR-Tools, NumPy or Pandas; seven targeted launcher, locked-result and streaming tests passed. The checker model and results are unchanged.
- V2 production verification on 2026-10-17, implementation checkpoint `aae41d2`: production build and script lint passed; 33 Python tests passed. The browser audit passed at 1440, 768, 390 and 320 pixels with no browser errors, including all 105 sample squares, repeated and interrupted page-break effects, keyboard navigation, zero-width resize recovery, all three driver-rule pickers and responsive timeline scrolling. The complete live story passed with all 100 scenarios surviving, three linked fingerprints and exact preview cancellation. Fixed the skip link resetting the selected tab and negative SVG sizes during transient zero-width resizes. Coverage is recorded in `design/landing-v2/verification.md`; screenshots and the JSON report remain local in `devpost/screens/`.
- User-approved UI revision after slice 5: use Landing v2 and its Grid companion from the supplied archive. Convert the templates to native React and TypeScript with htmlparser2; use GSAP, ScrollTrigger and the React cleanup hook for motion. Preserve the six sections, story scroll, grid interactions, replay, page-break effect and editor. Label illustrative readings/results honestly and connect the Start editor to the existing 24-item confirmation, live checker and scored fixes. This revision does not start slice 6.
- Local launcher corrected after a previous preview left ports occupied: it checks ports before starting, keeps Vite on 5173, waits for both servers to be ready, and shuts down their process groups. Two launcher regression tests and a real startup, duplicate-launch, and shutdown check passed; all development ports were released afterward.
- Slice 5 verified: 31 Python tests passed and the production web build passed. `scripts/verify_story.py` plays the full story at 1440x900, verifies all four crosses, both turned-down fixes, exact preview cancellation, the three-link fingerprint chain, corrected map marks, reduced motion, and all 100 scenarios surviving, with no page errors. Six full-page screenshots are saved as `devpost/screens/slice5-*.png`; screenshots remain ignored by Git.
- Slice 5 explanations and suggestions in `fixtures/example-fixes.json` are hand-made PLACEHOLDER data, labelled in the interface. The checker generates reasons from its schedule and confirmed inputs; every suggested change is gated and scored live against all 100 scenarios.
- The alternate answer "The van too" now updates Ravi's loading roles on the van routes; "Only his car" still matches the truth map. Opening the map alone does not mark results out of date; changing a checker input does.
- Slice 4 verified: 28 Python tests passed, production web build passed, and Playwright saw the first cell before completion, then all 100 expected marks with no page errors. Screenshot: `devpost/screens/slice4-grid.png`.
- Slice 4/5 checkpoint moved from after slice 4 to after slice 5 so the learner can explore the complete demo story; slices 4 and 5 still have separate verification, commits, and checklist ticks.
- Slice 3 example reading is explicitly a hand-made PLACEHOLDER fixture, not real AI output; the UI labels it as such.
- B revision: pairs that combine two problems for the same entity are excluded because that combination cannot happen (for example, one person cannot be absent and leave early at once). The locked story stays the same: 100 total, 1 single weak spot, 3 hidden pairs, 12 dimmed, 84 survived.

- Spare-key fix operation corrected in `spec.md`: "Give the key to another person" (which just moved the weak spot) replaced with "Give a spare key to a person" (`holds_key` becomes true, existing holders keep theirs).
- The original target was impossible: absent is strictly worse than leaving early, and a route can only be late if someone becomes free later. The example was redesigned; the three hidden pairs now end as “not delivered.”
