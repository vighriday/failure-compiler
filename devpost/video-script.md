# Simple recording: one button per scene

Use the dedicated recording window. Click **Next scene** or press **F8** after
each paragraph. You can scroll at any pause. **Restart** clears only that
recording window's session and returns to the beginning.

The guide performs ordinary clicks, selections and confirmations through the
app's existing controls. It uses the approved review choices for the fictional
example, real saved AI responses and the live checker. It adds its own clearly
labelled recording controls; it does not replace facts, AI text or results.

Aim for **2:30 to 2:50**, including scene transitions. Read naturally and leave
short pauses while the app works. Record the browser, not a terminal or key field.
Keep the saved-example labels visible. This is a suggested factual voiceover;
adjust it to your own words and do not add unverified claims or personal learning
statements.

## Voiceover and actions

### 1. Overview

“This is Failure Compiler. It helps volunteer coordinators find where a Saturday
delivery plan can break before families are left waiting.”

**Click Next.** The guide opens Start and loads the example.

### 2. Plain-text plan

“The plan is plain text. For this recording, I’m loading the fictional example.
It needs no API key.”

**Click Next.** The saved reading opens.

### 3. AI reading

“This is a real saved AI reading, not a new AI request. Each fact links back to
the source text. Guesses and questions need explicit answers.”

**Click Next.** The guide applies the approved example review through the normal
controls. Allow a few seconds for the selections and confirmations.

### 4. Reviewed map

“The guide has applied the reviewed example answers through the normal controls.
The server allows a run only after the facts are confirmed and the rules pass.”

**Click Next.** The checker runs.

### 5. Original results

“The live checker runs one hundred scenarios: every listed single problem and
every compatible pair. It finds one single weak spot and three hidden pairs.”

**Click Next.** The broken van case opens.

### 6. A hidden pair

“The van is late and Anita leaves early. Each problem alone survives. Together,
Route C cannot load, and eight households miss delivery.”

**Click Next.** The page scrolls to the real AI cards.

### 7. AI suggestions rejected

“These are real AI suggestions. All three are turned down. The checker tests
what each change actually does, including whether it creates another failure.”

**Click Next.** The guide opens the related Anita-absent case and accepts the
eligible Sam loader card. Watch the grid update.

### 8. A fix that works

“Adding Sam as a loader passes. The checker tests the change across all one
hundred scenarios. Both van failures disappear.”

**Click Next.** The guide opens Joel's case, fills the spare-key builder and
tests the change. Nothing is accepted yet.

### 9. Your own change

“The fixed-choice builder lets the coordinator propose a change too. Here,
spare keys for Maya and Sam pass the same checks as an AI suggestion.”

**Click Next.** The guide accepts those keys, then builds, tests and accepts
Sam as Route A's backup. Both use the normal controls.

### 10. All tested scenarios survive

“With the spare keys and Sam backing up Route A, all one hundred tested
scenarios survive. I can compare the original plan with the accepted changes.”

**Click Next while saying the last sentence.** The guide briefly shows Before,
then After, then opens the report.

### 11. Report and limits

“The report records the original failures, the changes and the test limits.
Surviving these listed problems is useful evidence, not a guarantee about
everything that could happen.”

End the recording here. You can scroll upward to show the report summary or
down to its limits and fingerprint. **Restart demo** prepares another take.

## Start again later

With the frontend and backend running:

```text
uv run -- python scripts/present_demo.py
```

The helper needs the existing development Playwright installation. It opens a
separate browser session; the ordinary website works without it. Closing the
recording browser leaves the app servers running.

For automatic advances, rather than the Next button:

```text
uv run -- python scripts/present_demo.py --autoplay --hold 12
```

Automatic mode pauses on the last scene. Runtime depends on the machine and the
chosen pause; use the manual button if you want to control the voiceover pace.
