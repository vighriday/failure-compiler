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

- [ ] **4. The grid fills live**
  Becomes usable: After confirming the map, the crash-test grid fills cell by cell over SSE. The example plan's story is visible on screen: one cross on the diagonal, three crosses off-diagonal, dimmed marks, ticks. The count line updates live.
  Why now: Connects the confirmed map to the checker from slice 1, streamed to the browser. The grid is the emotional core of the demo.
  PRD ref: `prd.md > Screen 3: Crash Test`, `prd.md > Live-Filling Grid`
  Spec ref: `spec.md > Checker: What It Models and How It Decides`, `spec.md > Components`
  Build: `GET /api/run-tests?map={fingerprint}` SSE endpoint with results cached by fingerprint in `server/session.py`; Screen 3: CSS-grid triangle layout, four SVG cell marks (tick, cross, dim, qmark), live count line, plan-survives-first-run message and "See report" link; `prefers-reduced-motion` check skips cell-fill animation.
  Verify (mechanical): Confirm the example map -> grid fills with exactly 1 cross on diagonal, 3 off-diagonal crosses, 12 dimmed, 84 ticks; count line reads "100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak spot, 84 survived."
  Learner check: Watch the grid fill, check the count line, click around the grid.
  Commit: `Add live SSE crash-test grid`

- [ ] **5. Broken case, fixes, flip**
  Becomes usable: Click a cross, and the detail panel slides in with the timeline, human cost, and fix cards. The turned-down fix shows a checker-derived reason. The real fix previews on the grid and, when accepted, flips cells and re-tests. After all fixes, 100 ticks.
  Why now: Completes the core journey narrative. With slices 3 to 5 done the full demo is recordable without any AI provider.
  PRD ref: `prd.md > Screen 4: Broken Case Detail (panel)`, `prd.md > Fix Cards and Scoring`, `prd.md > Fix Preview`, `prd.md > Fix Acceptance and Re-test`
  Spec ref: `spec.md > Explain and Fix`, `spec.md > Components`
  Build: `POST /api/suggest-fixes` in example mode (loads `fixtures/example-fixes.json`, gates and scores each fix live); checker-derived turned-down reasons (which resource the late route was waiting on); "Couldn't apply" state for fixes that fail the gate. Screen 4: right-side panel with grid staying interactive; SVG timeline with routes as horizontal bars and "Noon: families waiting" finish line in red; human cost; labelled "AI's explanation" sentence; fix cards with scores and turned-down labels. Preview from stored per-scenario results (no re-solve); `POST /api/apply-fix` producing new fingerprint and `AppliedFix` chain; flip animation with `prefers-reduced-motion` check. "Next broken case (N left)" button; "All 100 tested scenarios survive" then "See report"; "No saved suggestions for this case. Add a key to ask the AI." state.
  Verify (mechanical): Click each cross, and the panel shows correct facts and fixes; turned-down fix shows reason; preview draws projected grid; accept real fixes in sequence, and the grid reaches 100 ticks; cancelled preview restores grid exactly.
  Learner check: Play the whole demo story through to all ticks.
  Commit: `Add detail panel, fix cards, preview, accept, and flip`

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

- [ ] Early usable behavior explored - after slice 4 (grid fills live), I explore the running app and give feedback
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
- Slice 3 example reading is explicitly a hand-made PLACEHOLDER fixture, not real AI output; the UI labels it as such.
- B revision: pairs that combine two problems for the same entity are excluded because that combination cannot happen (for example, one person cannot be absent and leave early at once). The locked story stays the same: 100 total, 1 single weak spot, 3 hidden pairs, 12 dimmed, 84 survived.

- Spare-key fix operation corrected in `spec.md`: "Give the key to another person" (which just moved the weak spot) replaced with "Give a spare key to a person" (`holds_key` becomes true, existing holders keep theirs).
- The original target was impossible: absent is strictly worse than leaving early, and a route can only be late if someone becomes free later. The example was redesigned; the three hidden pairs now end as “not delivered.”
