# V2 interaction coverage

## Verified on 2026-10-17

Implementation checkpoint: `aae41d2`.

- Production build passed: `npm run build -- --logLevel error`.
- Script lint passed: `uv run -- ruff check scripts/verify_landing.py scripts/verify_story.py`.
- Python regression suite: `uv run -- python -m pytest -q`, 33 passed.
- Production browser audit passed at all four viewport sizes with no browser errors. All 105 sample squares were clicked, including the five impossible combinations.
- The complete live checker story passed: rejected fixes, exact preview cancellation, three linked fingerprints, reduced motion, and all 100 tested scenarios surviving after the accepted fixes.
- The audit caught and fixed two recovery defects: the skip link reset the active tab, and a transient zero-width resize could produce negative SVG dimensions. Both now have regression coverage.

## Reproduce the checks

Run these browser checks with the local API and frontend running:

```powershell
uv run -- python scripts/verify_landing.py
uv run -- python scripts/verify_story.py
```

Set `FAILURE_COMPILER_URL` when using a frontend port other than 5173.

| Area | Checks |
| --- | --- |
| Navigation | All six tabs, brand, both example actions, secondary action, next-section buttons, arrow keys, Home, End, and a skip link that preserves the selected section. |
| Overview | Text and stroke entrances, three complete page-break effects, navigation during the effect, fragment cleanup, restored original styles and controls. |
| Plan | Sticky source, all five scroll steps, matching line highlights and reading progress. |
| Sample reading | Source focus, question answers and reopening, constrained correction, save, confirmation and transition to the sample grid. |
| Sample grid | All 105 squares clicked, Enter and Space operation, exact initial states, rerun, three example fixes and reset. Five squares are impossible pairs; the live checker tests 100 scenarios. |
| Trust | Pipeline replay, three honest outcomes and immediate end states under reduced motion. |
| Start | Empty and over-limit input, character counter, synchronized line gutter, example typing, key disclosure and controlled key value, truthful unavailable-AI errors. |
| Real reading | All 24 details, bulk confirmation excluding guesses and questions, source focus, repeated corrections, dependent re-confirmation, reversible loading answers, preset sizes and all three driver-rule pickers. |
| Live checker | SSE fill, all four crosses and their human costs, both rejected fixes, exact preview cancellation, accepted changes, three linked fingerprints and all 100 scenarios surviving after the fixes. |
| Responsive behavior | Desktop 1440x900, tablet 768x1024, phones 390x844 and 320x844, horizontal timeline keyboard scrolling, and valid SVG dimensions during a transient zero-width resize. |

`verify_landing.py` records browser errors and saves screenshots plus `v2-verification.json` in `devpost/screens/`. `verify_story.py` records the six stages of the complete checker story. These artifacts remain local and ignored by Git.

The source templates are preserved in this folder. The browser uses generated native React components, self-hosted fonts, and GSAP with scoped cleanup. The editor runtime from the archive is not shipped.
