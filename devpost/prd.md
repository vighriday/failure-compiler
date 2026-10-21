---
doc: prd
status: approved
---

# Failure Compiler: Product Requirements

A crash-test tool for volunteer coordinators: paste a messy written plan, confirm what the AI read, and find out which combinations of ordinary problems quietly break it before Saturday does.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`.

---

## The Core Journey

Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`.

1. **Arrive at the v2 overview.** The landing navigation has Overview, Plan, Read, Crash test, Trust, and Start. The Start tab contains the paste screen: a single text area and a brief prompt. They paste their plan, or load the example in example mode.
2. **The AI reads the plan.** It produces a structured map (people, vehicles, places, times, deadlines) and surfaces ambiguities as questions. In example mode, a saved AI reading loads instead; a small label reads "Example mode: using a saved AI reading."
3. **Plan map screen.** The user sees the checklist view at the top (every job with a person and a backup, all ticked; it looks done), followed by the AI's structured reading as short plain statements. Source tags distinguish field citations from entity mentions; a mention alone does not support a field's value. Below the plan statements: the "What we'll test" section listing each failure type with its size. The user confirms or corrects using constrained choices only, then hits confirm.
4. **Crash test screen.** A grid fills in live. Every failure type across the top, every failure type down the side. Each scenario appears once: the diagonal plus the cells below it, so the grid shows one triangle, not two. Cells flip to tick, cross, dimmed mark, or question mark as the checker runs. A count line tracks results in real time.
5. **Broken case detail panel.** The user clicks a cross. A panel slides in on the right; the grid stays visible on the left. The panel shows the failures, a timeline of the broken morning, the human cost, and up to three fix suggestions, each already scored.
6. **Fix and re-test.** The user previews a fix on the live grid, accepts it, watches the grid re-test in place. The panel updates: "Now survives." They move to the next broken case. Fixes stack.
7. **All cases survive (or the coordinator stops here).** When nothing is left, the panel reads "All 100 tested scenarios survive" and offers "See report." If the coordinator decides to stop fixing, "See report" is available any time after the first run. The report then shows what is still broken.
8. **Report screen.** The full run in plain language: plan, what was tested, what broke, what fixed it, what was NOT tested. Print or save as PDF via browser print.

---

## Screens and Layout

Five screens, desktop-first.

### Screen 1: Paste Plan
A text area. A brief prompt. No checklist yet. A button to load the example plan. Pasting your own plan requires an AI key; the key field surfaces here if none is set.

Uses the supplied Landing v2 Start layout: prompt and assurances on the left, a paper editor with synchronized line numbers, counter, actions, and collapsed key field on the right. The layout stacks on smaller screens.

### Screen 2: Plan Map
**Top: checklist view.** Every job with a person and a backup. All ticked. It looks complete. This is the "before": the plan as any coordinator would call it done.

**Middle: AI's structured reading.** Short plain statements with honest source tags. A field tag such as "Loaders · L13" shows the AI's citation for that field; "Ravi · mentioned on L8" only locates the entity, not evidence for every fact about it. Null or missing field citations stay missing. Hovering or focusing each tag highlights its own line. Three visual states for each item:
- Default: AI's reading with field citations where supplied, otherwise labelled entity mentions or "No source line".
- Corrected: original AI reading struck through, user's correction next to it, marked "corrected by you." Retained tags describe the original reading's sources, not proof of the user's new value.
- Added: no source line, marked "added by you" (created because a rule asked a question).

If an extra place listing has no loading activity or supply arrival, a rule question asks whether it is separate or the same place as another listed loading or supply place. The user chooses from existing places. Keeping it preserves its tests; identifying it as another place uses that place's details and requires those facts to be checked individually again. The original listing and source stay in the question history. Change restores it. Bulk confirmation never answers this question.

The saved example is an unedited Gemini `reading-v2` / `read-v4` response with 39 reviewed non-null citations and 10 null sources. Existing identity and confirmation controls bring all checker inputs and 100 verdicts into agreement with truth. Null sources remain labelled mentions; older captures do not gain invented evidence. The source review records the capture and incomplete new bake-off.

Confirmed items get a small "confirmed" mark. Corrections use constrained choices only: pick from known people, vehicles, or places; use a time picker; no free text. Corrections go directly into the map; the AI does not re-read.

**Below: "What we'll test."** Each failure type with its size, for example:
- Supply truck arrives 45 minutes late
- Van returns 30 minutes late
- A volunteer leaves 90 minutes early
- Loading area blocked for 30 minutes

Sizes come with sensible defaults chosen so the example plan tells its story. The user can change a size, but only from preset choices: 15, 30, 45, 60, or 90 minutes. No free typing.

**Confirm button.** Active only when every item is confirmed and every plain rule passes. Rule failures surface as questions before the button becomes available. Confirming the map confirms the "What we'll test" list too.

### Screen 3: Crash Test
A live-filling grid. Concrete problems appear across the top and down the side: the example has 14 problems from five fixed types and exactly 100 tests. Each scenario appears once: the diagonal plus the cells below it. The grid shows one triangle, not two.

**Four cell states:**
- **Tick:** the plan survives this scenario.
- **Cross:** the plan breaks. On the diagonal: a single weak spot. Off-diagonal, where both failures pass alone: a hidden pair.
- **Dimmed mark:** the pair breaks, but only because one failure already breaks it alone. Labelled "already broken by X alone." Keeps one weak spot from filling a whole row and column with crosses.
- **Question mark:** the checker could not determine the result. Never counted as survived.

**Count line** (updates live): "100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak spot, 84 survived."

**Before/After toggle** sits above the grid once any fix is accepted. Compares the original plan against the current fixed version.

Before restores the first confirmed run from frozen snapshots in the accepted-fix chain, including its original counts and labels. Before is read-only. Historical results can be explored by hover or focus; changes are made in After, which shows the current run. Switching cancels any preview and never re-tests, calls AI or changes the plan. Later plan-map edits are shown as confirmed edits rather than invented fixes.

**Preview banner** (when a fix is being previewed): "Previewing: Fix 2." Changed cells outlined. New crosses marked distinctly. Count line shows what the numbers would be. "Cancel preview" restores the grid exactly. One preview at a time.

### Screen 4: Broken Case Detail (panel)
Opens on the right when a cross is clicked. The grid stays visible on the left. No page navigation.

**Contents:**
- The two failures (for a hidden pair) or the one failure (for a single weak spot), with a plain sentence explaining why the plan breaks.
- For a hidden pair: a note that each failure alone was fine. The three example pairs are Supply truck late + Ravi absent; Van late + Anita leaves early; Van late + Anita absent.
- A timeline of the broken morning. A not-delivered route is drawn as never leaving, with the reason shown, e.g. “Van back 10:45. Loading team gone.”
- Human cost: “Route C: 8 households not delivered.” For the other crosses: “Route A: 10 households not delivered” and “Routes A, B, C: 30 households not delivered. Nobody can open the loading area”.
- Up to three fix suggestions, each a card showing:
  - What the fix changes.
  - Fixes N / still broken N / new crosses N, scored by the checker before the user touches it.
  - The saved example uses unedited real cards labelled "Suggested by Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)". All three van + Anita leaves early cards are turned down. Their reasons name the actual operation or checker result: shortening Anita's finish from 12:00 to 11:00, adding Ravi who already drives Route C while loading still fails at 10:45, or fixing three crosses while creating the single weak spot "Supply truck 45 min late".
  - On van + Anita absent, accept "Add an extra loader (Sam) to Route C so loading can finish after the original loaders leave." Both van crosses flip. Joel's one-spare-key AI card is turned down because it reveals "Joel absent + Ravi absent". The coordinator then builds spare keys for Maya and Sam and Sam as Route A backup; all 100 scenarios survive. Turned-down scored fixes can be previewed but not accepted; a card that fails the gate cannot be previewed.
- Accept button (enabled only when the selected case survives, there are no new crosses, and no candidate result is unknown). An unknown result never counts as a repaired case.

**Test your own change:** below the AI cards, build up to three operations with picks only: add a driver or loader to a route, give a spare key, change someone's hours using a time picker, or move a route to another known vehicle. No free text. "Test this change" runs the same gate and all 100 tests. The result is a "Your change" card with the same preview, turned-down and accept rules. Invalid choices name the problem and cannot be accepted.

When no AI card is eligible, say "None of these suggestions worked". Live mode offers "Ask for new suggestions" once with a configured or session key. Saved example mode never requests or captures another round automatically.

**After accepting a fix:**
- Grid re-tests in place. Cells flip. Takes a few seconds.
- Panel updates: "Now survives."
- Button: "Next broken case (N left)."
- When nothing is left: "All 100 tested scenarios survive." Button: "See report."
- Accepted changes appear on the plan map, marked "changed by Fix 1" (or Fix 2, etc.).
- Accepted history labels each change "Fix N (AI)" or "Fix N (yours)".

### Screen 5: Report
Reached from "See report." One page in the app.

Open with a summary of the before and after count lines, accepted fixes split between AI and yours, AI suggestions turned down or not applicable, and the main original human cost. These are actual history counts, including when the coordinator stops early. Review questions show their actual confirmed answer, not "Use the reviewed details". The full example report fits five pages on A4 and Letter, without splitting fix cards or changing the visual design.

The complete example summary reads "3 fixes accepted: 1 from the AI, 2 yours" and "The AI suggested 12 fixes. The checker turned down 10 and couldn't apply 1." The largest original cost is 30 households not delivered because nobody can open the loading area.

**Sections:**
1. **The plan:** current confirmed facts with field citations, labelled entity mentions or "No source line", with "AI read N items, N corrected by you, N added by you" and "Read by provider / model". Mention tags are not proof of field values; retained citations refer to the original reading when a value was corrected. The example starts with 32 AI items; identifying Hall as Loading bay leaves 30 facts and counts as one correction. A fix marks only facts its operations actually changed.
2. **What was tested:** the exact problem list with sizes. The example has 14 problems and "100 tests: every single problem and every pair that can happen". Other maps show their actual counts.
3. **What broke (before fixes):** single weak spots and hidden pairs, each with its human cost. Dimmed results grouped separately: "12 pairs already broken by the hall key alone." If removing a weak spot via a fix caused any formerly-dimmed pairs to resolve or reveal a new hidden pair, the report shows that honestly.
4. **Fixes:** accepted changes labelled "Fix N (AI)" or "Fix N (yours)", each operation and its fixes / still broken / new crosses scores at that point. Include turned-down and couldn't-apply suggestions requested during the run, their one-line checker or gate reasons, and the provider label. Gate failures say "Not scored". Preserve earlier suggestion rounds; a report never requests new ones.
5. **After fixes:** final count, e.g. "All 100 tested scenarios survive."
6. **What was NOT tested:** specific, not a generic disclaimer:
   - Three or more problems at once.
   - Problem types outside the fixed list: bad weather, someone getting sick partway through, wrong addresses, running short of food, volunteers arriving late.
   - Other sizes of the same problems: "the truck was tested 45 minutes late, not 90."
   - Anything the plan didn't mention.
   - Any question-mark results, listed by name.
7. **Example mode notice** (if applicable): "This report used a saved AI reading of the example plan."

**Print or save as PDF** button: `window.print()`, with an A4/Letter-compatible print stylesheet. Navigation, buttons and disclosure controls are hidden; pen marks and text remain readable in black and white. Limitations and fingerprint stay together. A report is available after the first completed run, even if crosses remain. The sample PDF is printed from the real full story with Playwright.

---

## Look and Feel

Source: `scope.md > Inspiration and Identity`.

A coordinator's run sheet, not a tech dashboard. The feel is calm and honest: warm off-white paper background, near-black ink text, no decoration that is not doing work.

The user-approved Landing v2 design is the visual source: warm paper `#F6F4EE`, sheet `#FBFAF6`, ink `#1A1916`, green `#1E6B47`, brick red `#B23A2E`, amber `#8A6410`, and thin neutral rules. It adds six-section navigation, large editorial headings, a sticky source-plan story, a sample grid, and an animated explanation of the pipeline. Illustrations are labelled as example previews; the full confirmed-map flow runs the real checker.

Colour carries meaning only:
- Deep green: ticks and the main action button.
- Brick red: crosses and broken states.
- Amber: question marks.
- Grey: dimmed marks.
- Everything else: neutral.

Typography:
- IBM Plex Sans for all body text, labels, and UI.
- IBM Plex Mono for times, counts, and numbers where alignment matters.

Marks: ticks and crosses are clean stroke marks, like a pen on a checklist. No emoji anywhere in the app.

Timeline: the deadline is a solid red vertical line labelled "Noon: families waiting."

Motion only where it means something: cells fill in order over a few seconds as the checker runs. Accepted fixes flip changed cells with a short animation. Both effects respect `prefers-reduced-motion`.

Timelines use natural schedules: after proving the best lateness, the checker selects the earliest sensible morning without changing the verdict. Gemini remains primary; the approved Groq example suggestions are labelled fallback responses. The fixed-choice coordinator builder uses the same gate and scorer.

The current visual design is final for this completion pass. Report, grid, panel, history and builder styling stays intact. Keyboard operation, visible focus, text contrast of at least 4.5:1, text at least 12px, and reduced motion remain required. Components retain descriptive classes for maintenance.

V2 also includes tab entrances and underline movement, reading progress, scroll-linked source highlights, a replayable pipeline, example-plan typing, and the clickable “breaks” effect. The page-break effect restores every fragment and control after completion or navigation. All motion respects reduced-motion settings; keyboard users can operate every control.

Tick and cross throughout (not colour alone), so the grid is readable by everyone.

---

## Features and Behavior

### Paste and Load
- Single text area; no file upload.
- "Load example" loads the Saturday food distribution plan: Route A has 10 households, Route B has 12, and Route C has 8. The van returns from an early pickup at 9:30. Joel has the only loading-area key and leaves at 10:30; Maya leaves at 10:45; Sam is not on the loading team.
- In example mode: saved AI reading loads (structured map, questions, explanations, fix suggestions). Full flow still runs. Checker always runs live. Label reads "Example mode: using a saved AI reading."
- Pasting your own plan requires an AI key. Key field surfaces on Screen 1 if none is set.

### AI Reading and Structured Map
- AI produces a structured map as fixed-schema output: people, vehicles, places, times, deadlines.
- Source tags distinguish the AI's field citations from entity mentions. Missing field citations are not replaced with an entity's first mention; older captures without per-field sources do not gain invented evidence.
- Ambiguities surfaced as questions before the user reaches the confirm button.
- AI does not re-read after corrections. Corrections go directly into the map.
- Acceptance criteria:
  - [ ] Each available field citation is labelled by its field. Entity-only lines say "mentioned on L…"; a missing source says "No source line". Added items are marked "added by you" without invented sources.
  - [ ] Corrections show the AI's original reading struck through and the user's correction marked "corrected by you."
  - [ ] Original source tags remain distinguishable after correction and do not claim to prove the corrected value.

### Plain Rules Validation
- App runs plain rules against the confirmed map before the checker runs: every name exists, every route has a vehicle and driver, every time is coherent, nothing the checker needs is missing.
- Rule failures surface as questions on the plan map screen, not silent errors.
- Confirm button is inactive until every item is confirmed and every rule passes.
- Acceptance criteria:
  - [ ] A map with a missing driver surfaces a question, not a silent pass to the checker.
  - [ ] Confirm button is disabled with an unexplained rule failure present.

### "What We'll Test" Configuration
- Listed on the plan map screen, below the structured reading.
- Each failure type shows its default size.
- User can change a size using preset choices only: 15, 30, 45, 60, 90 minutes. No free typing.
- The same list appears in the report under "What was tested."
- Confirmed alongside the plan map with the same confirm button.
- Acceptance criteria:
  - [ ] Changing a size is possible only via the preset picker.
  - [ ] The confirmed sizes appear unchanged in the report.

### Finish Time
- Comes from the plan. Strict: one minute past counts as broken.
- If the plan is vague (e.g. "around noon"), the AI surfaces it as a question; the user confirms an exact time via the time picker like any other item.
- Acceptance criteria:
  - [ ] A plan with no explicit finish time produces a question, not a default assumption.
  - [ ] The checker treats the confirmed finish time as a hard deadline.

### Live-Filling Grid
- Cells fill as the checker runs; no waiting for a complete result before seeing anything.
- Four states: tick, cross, dimmed mark, question mark.
- Count line updates in real time.
- Acceptance criteria:
  - [ ] Grid begins filling before all tests are complete.
  - [ ] Count line matches the final cell states when the run completes.
  - [ ] A dimmed mark cell is labelled with which single failure causes it.

### Broken Case Detail Panel
- Slides in on the right on click; grid stays visible on the left.
- Closing the panel returns the grid to its normal state.
- Acceptance criteria:
  - [ ] Grid is fully interactive (other cells clickable) while the panel is open.
  - [ ] A hidden pair case shows that each failure alone was fine.
  - [ ] The timeline shows the late route past the finish line in a visually distinct state.
  - [ ] Human cost is stated as a concrete count and delay, not a vague warning.

### Fix Cards and Scoring
- Checker tests each suggested fix against every scenario before the user sees the card.
- Each card shows: what changes, fixes N, still broken N, new crosses N.
- "Fixes N" plus "still broken N" always equals the crosses currently on the grid. Dimmed marks are not counted, since they get re-tested when the weak spot that caused them is removed.
- A fix that does not solve the presenting case, or that creates any new cross, is labelled "Turned down" with a one-line reason.
- Turned-down fixes: previewable, not acceptable.
- Acceptance criteria:
  - [ ] All three real van + Anita leaves early cards are turned down with checker-derived reasons; the real Sam loader card on van + Anita absent fixes both van pairs.
  - [ ] Coordinator-built spare keys for Maya and Sam and a Sam backup on Route A pass the same gate and score as expected across all 100 scenarios.
  - [ ] The builder accepts at most three fixed-choice operations and labels its results "Your change"; accepted history records AI or yours.
  - [ ] A turned-down fix cannot be accepted regardless of user action.
  - [ ] Scores are present on the card before the user interacts with it.

### Fix Preview
- Selecting a fix previews it on the main grid in place.
- Banner: "Previewing: Fix N." Changed cells outlined. New crosses distinctly marked.
- Count line shows projected numbers.
- "Cancel preview" restores the grid exactly. One preview at a time.
- Acceptance criteria:
  - [ ] Cancelling a preview leaves the grid identical to its pre-preview state.
  - [ ] New crosses introduced by a fix are visually distinct from existing crosses in the preview.

### Fix Acceptance and Re-test
- Accepting a fix updates the plan and re-tests all scenarios.
- Cells flip in place during re-test.
- Accepted changes appear on the plan map marked "changed by Fix N."
- Fixes stack: each accepted fix becomes part of the plan before the next fix is evaluated.
- When a weak spot is removed, pairs that were dimmed because of it are re-tested properly; they may become ticks or reveal a hidden pair.
- Acceptance criteria:
  - [ ] After accepting a fix, the plan map shows the change marked "changed by Fix 1."
  - [ ] Dimmed pairs are re-evaluated after a fix removes their root single failure.
  - [ ] A newly revealed hidden pair after fix acceptance is visually distinguishable from pre-existing crosses.

### The Checker's Three Honest Answers
- **Breaks:** "This breaks your plan, and here is exactly how."
- **Survives:** "Your plan survived everything we tested. That is not the same as 'your plan is safe.' It only covers what we tested."
- **Unknown:** "I could not tell, because something is missing or unclear." Never treated as a pass.

---

## States and Boundaries

- **First use / example mode:** "Load example" is available immediately with no key. Full flow runs on the saved AI reading. Checker runs live.
- **No AI key:** paste area active, key field shown on Screen 1. Plan cannot be submitted without a key.
- **Plan map: unconfirmed items:** confirm button inactive. User cannot proceed to the crash test.
- **Plan map: rule failure:** surfaces as a question. Confirm button inactive until resolved.
- **Grid: question mark cell:** never counted as survived. Listed by name in the report under "What was NOT tested."
- **Fix: turned down:** card visible and previewable; accept button absent.
- **Plan survives everything on the first run:** the count line reads "Your plan survived all 100 tested scenarios." The panel (or a prominent message) offers "See report" directly. No broken cases to open.
- **After all cases survive (via fixes):** panel reads "All 100 tested scenarios survive" and offers "See report."
- **Report available after first run:** "See report" is accessible any time after the checker has completed at least one run, regardless of whether all cases are resolved. The report shows what is still broken if the coordinator stops early.
- **AI key invalid or AI call fails:** a clear error message, a retry button, and a suggestion to try the example plan instead.
- **AI reading fails the format check:** "The AI's reading did not pass the format check." Retry button offered. Nothing reaches the plan map unchecked; the format check is part of the validation pipeline.
- **Pasted text is not a distribution plan:** "This version only supports community distribution plans." Offer to load the example plan.
- **None of the suggested fixes pass:** "None of these suggestions worked". Live mode only offers "Ask for new suggestions" once, using a key. The coordinator can build a change in either mode.
- **Persistence:** no database or accounts. Closing the tab does not clear server memory, although the browser view is not restored. `/demo` clears only that browser's typed keys, reading, maps, results and fixes, rotates its cookie, clears browser storage and returns to the landing page. Server restart clears every session; local `.env` keys remain in the ignored file.

---

## Product Decisions

- **Finish time is strict, not adjustable.** One minute late is broken. The human cost display makes the exact delay visible; the coordinator decides what that means. Keeps the checker honest and the results comparable.
- **Problem sizes use preset choices only.** 15, 30, 45, 60, 90 minutes. No free typing. Keeps results reproducible and the example story reliable.
- **Corrections do not trigger AI re-reads.** The user's correction goes directly into the map. Preserves the validation pipeline: AI reads once, human confirms, checker acts on the confirmed map.
- **Turned-down fixes are visible with checker-derived reasons.** All three real van + Anita leaves early cards fail. The AI's one spare key reveals Joel + Ravi absent. Real cards are unedited; the checker explains the failures. The coordinator can build and test their own changes through the same gate and scorer.
- **Dimmed pairs re-test after a weak spot is removed.** A fix can unmask a hidden pair the weak spot was covering. The report shows this honestly. Keeps the checker's results accurate across fix iterations.
- **Report is a page in the app with browser print.** No custom export for the PoC. Nicer download is explicitly in Later.
- **Desktop-first.** The desktop view keeps grid and panel beside each other. Narrow layouts stack content and allow horizontal grid scrolling; landing, review and saved-story controls are checked at phone widths.
- **The broken case detail opens as a panel, not a separate screen.** Grid stays visible throughout the fix flow. Spatial continuity: the user never loses sight of where they are in the full picture.

---

## What We're Building

- Screen 1: paste plan or load example; AI key field.
- Screen 2: plan map with checklist view, AI reading with labelled field citations or entity mentions and a correction trail, "What we'll test" with preset size pickers, plain rules validation, confirm button.
- Screen 3: live-filling crash test grid with four cell states, count line, Before/After toggle, preview banner.
- Screen 4: broken case detail panel (slides in beside grid) with timeline, human cost, scored fix cards, preview and accept flow, re-test in place.
- Screen 5: report page with all six sections and browser print.
- Example mode: saved AI reading ships with the app; full flow runs without a key.
- The checker runs live in all modes.
- A locked test confirms the example plan's three hidden pairs and one single weak spot never change.

---

## Deferred From the POC

- **Custom file export / nicer report download.** Browser print covers the PoC.
- **AI-suggested plan-specific failure types.** Fixed taxonomy only for now; reproducibility depends on it.
- **Live public link / deployment.** Out of scope for the demo.
- **Accounts and saved sessions.** No persistence needed for a proof of concept.
- **File upload.** Paste only.
- **A second example type** (event setup). Post-PoC to show the checker is not food-distribution-specific.

---

## Possible Later Enhancements

A second example plan type (event setup) using the same checker, to show the pattern is general. AI-suggested plan-specific failure types, pending user approval before they run: the scope explicitly defers this but it is the natural next step. Nicer report download. Live public link.

---

## Non-Goals

- **Any plan in any industry.** The checker and map structure are designed around people/vehicles/places/times/deadlines. Generalising is post-PoC.
- **Three or more simultaneous failures.** Singles and pairs cover the interesting demo cases.
- **Connecting to other apps or messaging volunteers.** Out of scope entirely.
- **AI having the final word on pass or fail.** The checker always decides; AI only reads, explains, and suggests.

---

## Resolved Planning Questions

- **Failure taxonomy:** five fixed types instantiate 14 example problems, 14 singles and 86 possible pairs. The locked count is 100.
- **AI key UX:** the disclosure stays collapsed until needed. Typed provider keys stay in private server session memory; missing, invalid and failed-provider states have explicit retry/example actions.
- **Recording start:** `/demo` provides a clean take without affecting another browser. `demo-runbook.md` specifies the 2:30 path at 1440x900 and 100% zoom.
