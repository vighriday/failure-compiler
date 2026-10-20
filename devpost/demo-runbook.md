# Demo click runbook: 2:30

## Recording setup

- Browser content area: **1440x900**, browser zoom **100%**. Keep normal motion on.
- Build the recording version: `npm run build`.
- Stop an existing local server before starting this command: `uv run -- python -m uvicorn server.main:app --host 127.0.0.1 --port 8000`.
- Start each take at **http://127.0.0.1:8000/demo**. It resets only this browser's keys, reading, results and fixes, clears browser storage, then returns to the landing page at `/`.
- The saved example needs no key. Leave the AI-key disclosure closed.

## Click path and timing

| Time | Click path | Expected screen and numbers |
| --- | --- | --- |
| 0:00-0:08 | Wait on Overview after `/demo` redirects to `/`. | Landing hero and the labelled sample preview. The real plan has not been read. |
| 0:08-0:15 | Start tab, Load the example plan, then Read plan once the text finishes appearing. | Read tab. The original text stays on the left; 32 AI items are unconfirmed on the right. Saved-reading notice and Read by Gemini / gemini-3.8-flash. |
| 0:15-0:24 | Hover or focus Joel's Can drive tag at L16, then Ravi's Available until tag at L15. | Each tag highlights its own physical line in the sticky source panel. Unstated arrivals carry an explicit mentioned-on tag. |
| 0:24-0:32 | Scroll to the Hall identity question. Same place as another listing, choose Loading bay, Use this place. | Hall merges into Loading bay: 30 remaining fact rows. The question shows the explicit identity answer; the bay's facts need individual re-confirmation. |
| 0:32-0:55 | Confirm everything that isn't a guess. For each of the 17 guessed rows, Answer, then Keep this guess. Confirm the two stale Loading bay rows individually. Answer all four arrival questions with Use the reviewed details. | Sticky footer ends at 30 of 30 confirmed and 0 questions open. Confirm plan becomes enabled. Guesses and questions never get bulk-confirmed. |
| 0:55-1:02 | Confirm plan. Wait for the live grid to finish. | 100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak spot, 84 survived. |
| 1:02-1:15 | Open the circled cross at Van back 30 min late + Anita leaves 90 min early. Scroll the right panel through the timeline to the three cards. | Timeline on the right shows Route C never leaving, with Van back 10:45. Loading team gone. Human cost: 8 households not delivered. All three AI cards say Turned down; scores are 0/4/2, 0/4/0 and 3/1/1 (fixes/still broken/new crosses). |
| 1:15-1:27 | Open the other van cross, Van back 30 min late + Anita absent. Accept Add an extra loader (Sam) to Route C. Immediately scroll back to the grid's count line while it re-tests. | Card score 2/2/0. Both van crosses flip in the left grid, on the van row. Now 1 single weak spot, 1 hidden pair, 12 dimmed and 86 survived. Panel says Now survives. |
| 1:27-1:48 | Open Joel absent on the diagonal. Read the turned-down AI spare-key card. In Test your own change: Give a spare key, Maya; Add another operation, Give a spare key, Sam; Test this change; Accept fix on Your change. | AI card reveals Joel absent + Ravi absent. Your change scores 1/1/0. Joel and its 12 re-tested pairs survive; 99 survived, 1 hidden pair remains. |
| 1:48-2:06 | Open Ravi absent + Supply truck drops 45 min late. In the builder choose Add a driver, Route A, Sam. Test this change; Accept fix. | Your change scores 1/0/0. Final truck cross flips. All 100 tested scenarios survive. History: Fix 1 (AI), Fix 2 (yours), Fix 3 (yours). |
| 2:06-2:16 | Before, then After above the grid. | Before restores 84 survived, four crosses and 12 dimmed. After restores 100 survived. Switching does not call the solver or AI. |
| 2:16-2:30 | See report. Pause on Summary, then scroll to What was NOT tested and the fingerprint footer. | 3 fixes accepted: 1 from the AI, 2 yours. The AI suggested 12 fixes; ten turned down and one couldn't apply. End on the explicit limits, saved-example notice and fingerprint. |

## Saved thumbnail candidates

- [YouTube candidate, 1280x720](../docs/images/youtube-thumbnail.png)
- [Devpost candidate, 1500x1000](../docs/images/devpost-thumbnail.png)

Both are actual Overview screenshots at 100% zoom, with no overlaid artwork.
