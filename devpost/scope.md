---
doc: scope
status: approved
---

# Failure Compiler

A crash-test tool for plans: it tests every single failure and every pair from a fixed list, and shows you which ones break it before Saturday does.

## The Unique Kernel

Most risk tools give you a list of general warnings. Failure Compiler finds the specific combination of two ordinary problems that breaks your specific plan, where each one alone would have been fine, and then tests whether a proposed fix actually works against every scenario that was tested, not just the one that broke. Problems that are invisible alone, fixes that get tested before you trust them.

## Who It's For

A volunteer coordinator running a Saturday morning food distribution for a community kitchen or food bank. They plan in a group chat and a spreadsheet. They have a handful of volunteers, one van, one car, one loading area, and a hard finish time because families are waiting. When something goes wrong on the day, it is not a bug report. It is a family that does not get food.

## The Core Loop

Paste a messy written plan. The AI reads it into a structured map and asks one or two clarifying questions. The user confirms or corrects the map using constrained choices. The checker tests every single failure and every pair of failures from a fixed list. The grid fills in live with ticks, crosses, dimmed marks, and question marks. Open a cross to see the exact broken morning, including how many households are affected and by how much. Ask for fixes. Watch the obvious fix turned down and the real one pass. Accept fixes one at a time; each accepted fix becomes part of the plan and everything re-tests. The grid reaches all ticks.

## Inspiration and Identity

Calm and honest. Not a busy dashboard. The aesthetic of a tool that takes responsibility seriously: simple, direct, no decoration that is not doing work. The grid filling in live, the timeline of the broken morning, the fix being turned down and the real one passing: those are the emotional beats. Tick and cross, not just colour, so it is readable by everyone.

## Why This Matters to the Learner

The learning goal is a repeatable pipeline: AI reads messy input into a structured map, plain rules validate the map before any strict system touches it, the user confirms, and only then the deterministic checker acts. That pattern (AI reads, rules check, human confirms, strict system acts) is the thing to take away from this project and apply elsewhere.

The personal stake is the thing everyone has seen: a plan that looked complete on paper, every box ticked, every job with a backup, and it still fell apart because two small things went wrong at the same time and nobody had a plan for that combination. Food distribution is the case where the people who pay for a broken plan are families waiting for food.

## What "Working" Looks Like

Under a minute, on screen: paste the example plan, answer one question, hit test, watch the grid fill in, open a cross and see the not-delivered route and reason on the timeline, ask for fixes, watch the obvious fix rejected and the real one pass, accept both fixes in sequence, grid reaches all ticks. The same confirmed map always gets the same results: the demo never surprises.

The example plan is the one to build around: Saturday food distribution, Route A with 10 households, Route B with 12, and Route C with 8. The van returns from an early pickup at 9:30. Joel has the only loading-area key and leaves at 10:30; Maya leaves at 10:45; Sam is not on the loading team. Three hidden pairs break the plan: Supply truck late + Ravi absent; Van late + Anita leaves early; Van late + Anita absent. Joel absent is the only single weak spot. Written the messy way a real coordinator would write it.

The example is designed so the story is true: “Add Maya as backup driver for Route C” is turned down because the gap is loading, not driving. The checker-backed fixes are Sam loads Route C and Sam backs up Route A. One spare key is turned down because it reveals Joel + Maya absent; spare keys for Maya and Sam make all 105 scenarios survive. A test locks in those results so they never change.

The example works without an AI key. The AI reading of the example plan is done once using the real AI, and the result (the structured map, the questions, the explanations, the fix suggestions) is saved and shipped with the app. In example mode the app loads that saved reading; the full flow still runs (plan map screen, rules check, questions, confirmation gate). The checker always runs live. A small label reads: "Example mode: using a saved AI reading." Pasting your own plan requires a key.

Target: about 12 to 15 failure types, around 100 tests, finished in a few seconds.

## The POC Boundary

**Four screens:**

1. Paste plan. A text area. No checklist yet; the "looks complete" view belongs to the plan map screen where the AI reading is available.

2. Plan map. At the top: the checklist view showing what the plan looks like when every job has a person and a backup, all ticked. It looks done. Below: the AI's structured reading as short plain statements, each sourced to a line of the original. Guesses are marked and asked as questions. The user confirms or corrects using constrained choices only (pick from known people, vehicles, places; time picker; no free text). Corrections go directly into the map; the AI does not re-read. The app runs plain rules against the map (every name exists, every route has a vehicle and driver, every time is coherent, nothing the checker needs is missing); rule failures surface as questions. The checker only runs once every item is confirmed and every rule passes.

3. Crash test. A live-filling grid: every failure type across the top, every failure type down the side. Each cell is one scenario being tested. Four visual states:
   - Tick: the plan survives this scenario.
   - Cross: the plan breaks. On the diagonal (single failures): a single weak spot. On a pair where both failures pass alone: a hidden pair.
   - Dimmed mark: the pair breaks, but only because one failure already breaks the plan alone. Labelled "already broken by X alone." This keeps one obvious weak spot from filling a whole row and column with crosses and burying the hidden pairs.
   - Question mark: the checker could not determine the result (for example, it ran out of time). Never counted as survived.
   Count at the top adds up to the total and reads like: "105 tests: 1 single weak spot, 3 hidden pairs, 13 already broken by the weak spot, 88 survived."

4. Broken case detail. For a hidden pair: shows the two failures and that each one alone was fine. For a single weak spot: shows the one failure. Either way: a timeline of the morning. A not-delivered route is drawn as never leaving, with the reason shown, e.g. “Van back 10:45. Loading team gone.” A plain sentence explaining why. The human cost: how many households are affected and by how much, like “Route C: 8 households not delivered.” Then fix suggestions (up to 3), each showing fixes-N / breaks-N / new-crosses before acceptance. Selecting a fix previews its grid with changed cells outlined. Accepting a fix updates the main plan and re-tests everything. Fixes stack: accept one, then another; each becomes part of the plan. One fix can contain more than one change. A Before/After toggle compares the original plan against the current fixed version. If a fix creates a new cross, that cell is marked differently so it cannot hide.

**The validation pipeline (the learning goal made concrete):**
- AI produces the structured map as fixed-schema output.
- App runs plain rules against the map; rule failures become questions, not silent errors.
- User confirms or corrects using constrained choices only; AI does not re-read.
- Checker runs only once every item is confirmed and every rule passes.

**The checker's three honest answers:**
- This breaks your plan, and here is exactly how.
- Your plan survived everything we tested. That is not the same as "your plan is safe." It only covers what we tested.
- I could not tell, because something is missing or unclear. Never treated as a pass.

**The AI's three jobs (only these):**
1. Parse messy plan into structured map, surface ambiguities as questions.
2. Explain why a broken case breaks, in plain language.
3. Suggest up to three fixes per broken case.

The AI never chooses what gets tested. It never has the final word on pass or fail.

**End-of-run report:** the plan, what was tested, what broke, what fixed it, and an explicit section on what was NOT tested.

## Later

- A second example type (event setup) using the same checker, to show it is not food-distribution-specific.
- AI-suggested plan-specific failure types, pending user approval before they run.
- Nicer report download.
- Live public link.

## Explicitly Cut

- **Any plan in any industry.** The checker and map structure are designed around people/vehicles/places/times/deadlines; generalising the UI and parsing is post-PoC work.
- **File upload.** Paste only; file handling adds complexity with no demo value.
- **Three or more simultaneous failures.** Singles and pairs already cover the interesting cases for the demo.
- **Accounts and logins.** No persistence needed for a proof of concept.
- **Connecting to other apps or messaging volunteers.** Out of scope entirely.
- **AI-suggested failure types.** Deferred to Later; the fixed taxonomy keeps results reproducible and fair.
