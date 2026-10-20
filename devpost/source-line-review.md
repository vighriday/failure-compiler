# Source-line review

## Accepted example: reading-v2 / read-v4

The new primary capture initially failed with HTTP 504 and a timeout. The three-run
bake-off then produced exactly one successful Gemini response, on its third slot.
That same unedited response is the new example reading; no additional successful
capture was sampled. The two initial failures are retained in
[reading-v4-attempts.json](reading-v4-attempts.json), and the campaign retains every
slot and raw success in [bakeoff-read-v4.json](bakeoff-read-v4.json).

The existing visible Hall identity question and confirmation controls still yield
32 AI items, one correction, zero additions and 30 remaining facts. The candidate
was exercised through the actual UI before promotion: all checker inputs align,
all 100 verdicts match truth, and the actual grid remains 100 scenarios with one
single weak spot, three hidden pairs, 12 dimmed pairs and 84 survived. The raw AI
name "Supply truck drops" is retained; display labels and IDs are not checker inputs.

## Citation support

All 39 non-null fact citations were reviewed against the original 16 physical plan
lines. All are in range and non-blank. No unsupported non-null citation was found.
Ten missing citations remain null and are shown as entity mentions, not evidence.

| Facts | Supporting lines | Review |
| --- | --- | --- |
| Joel's hours and key | L3 | Explicit hours and only-key statement. |
| Joel and Maya can drive | L16 | "Everyone can drive." |
| Ravi, Sam and Anita can drive | L8, L9, L10 | Their explicit driving assignments support ability; L16 is another valid source. |
| Other volunteers' finish times | L15 | Explicit individual finish times. Arrival times remain uncited guesses. |
| Van and car availability | L5 | Explicit return/free times. |
| Hall/bay opening and access | L3 | Shared hall/access context. The text says the hall opens at 9 and the bay needs its key. The individual identity question confirms the interpretation; it is not an unrelated first mention. |
| One vehicle in the bay | L12 | Explicit capacity constraint. |
| Supply arrival and destination | L4 | Explicit arrival at the bay. |
| Route households, vehicles, drivers and durations | L8-L10 | Each route's own statement. |
| Route loading durations | L12 | General duration applies to each vehicle load. |
| Route loaders | L13 | Shared team plus Ravi's own-car exception. |
| Finish time | L6 | Explicit noon deadline. |

Null sources cover unstated arrivals, non-key-holder flags and unused Hall flags.
The fixed schema requires every nullable source field in provider output. Older
captures can still be replayed without fabricating citations. Added facts have no
source. A correction preserves the original citation as original evidence, not
proof of the coordinator's new value.

## New-schema bake-off

Checker equivalence still compares only state, lateness_minutes and human_cost,
not timelines. Loader lists remain sets; drivers retain primary-first order.

| Provider | Slot 1 | Slot 2 | Slot 3 | Available successful score |
| --- | --- | --- | --- | --- |
| Groq | Success | HTTP 400 | Timeout | 12/100 verdicts, 88% aligned fields, 4,662 tokens |
| Gemini | Timeout | HTTP 504 | Success | 100/100 verdicts, 94.34% aligned fields, 3,216 tokens |

Neither provider completed three successful runs, so the new campaign has no
ranked winner or consistency claim. Gemini remains primary from the last complete
read-v3 campaign (100/100 mean verdicts and 94.34% aligned fields versus Groq
55/100 and 84%). The new accepted reading reaches 100% aligned fields only after
the explicit identity answer. No successful response was retried or edited.
