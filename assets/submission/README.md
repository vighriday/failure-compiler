# Submission assets

All artwork and website screenshots are saved in this folder. This pack represents the current example-mode build, captured on 17 October 2026.

## Covers

| File | Dimensions | Use |
| --- | --- | --- |
| [thumbnail.png](thumbnail.png) | 1536 × 1024 | Landscape project thumbnail, with smaller artwork and generous crop margins. |
| [cover-square.png](cover-square.png) | 1254 × 1254 | Square cover, with the title, grid and footer inset for a landscape card crop. |

The covers are generated editorial artwork using the project's existing name, tagline, palette and grid motif. They are not app screenshots. The exact prompts and generation method are recorded in [prompts.md](prompts.md).

Both covers were revised to fit the project card shown in the review. The full composition is smaller inside the image, with empty paper around it. Use the landscape thumbnail for the project card; the square cover also keeps its full title and footer visible in a centered 337 × 223 card crop. These versions replace the earlier edge-filling covers.

## Actual website screenshots

| File | Dimensions | Shows |
| --- | --- | --- |
| [01-overview.png](screenshots/01-overview.png) | 1440 × 900 | Landing v2 overview and illustrative grid. |
| [02-paste-plan.png](screenshots/02-paste-plan.png) | 1440 × 900 | The example plan in the paper editor. |
| [03-plan-map.png](screenshots/03-plan-map.png) | 1440 × 900 | Original source, highlighted line and confirmation question. |
| [03-plan-map-full.png](screenshots/03-plan-map-full.png) | 1440 × 3491 | The complete 24-item reading and test configuration. |
| [04-live-grid.png](screenshots/04-live-grid.png) | 1440 × 1550 | Real checker results: 1 single weak spot, 3 hidden pairs, 12 dimmed, 84 survived. |
| [05-broken-case.png](screenshots/05-broken-case.png) | 1440 × 1795 | Van/Anita hidden pair, Route C's human cost, schedule and fix cards. |
| [06-fix-turned-down.png](screenshots/06-fix-turned-down.png) | 587 × 1177 | Actual case-panel capture showing the rejected driver fix and working loader fix. |
| [07-one-key-new-pair.png](screenshots/07-one-key-new-pair.png) | 1440 × 1752 | Preview revealing Joel absent + Maya absent with only one spare key. |
| [08-all-survived.png](screenshots/08-all-survived.png) | 1440 × 1523 | All 100 scenarios surviving after the three accepted fixes. |

The screenshots come directly from the running website. Text, counts, notices and statuses have not been replaced. The case-panel image uses Playwright's element screenshot; the other images are viewport or full-page captures. Handwritten reading/suggestion notices remain visible. Live AI and reports are still future work.

## Suggested gallery selection

Use the wide thumbnail as the cover, then the plan map, live grid, broken case, rejected fix and all-survived result. The square cover is an alternative crop format. Keep the complete reading and single-key preview as supporting detail.

## Refresh the screenshots

Start the app in one terminal:

```powershell
uv run -- python scripts/dev.py
```

Then capture the real journey in another:

```powershell
uv run -- python scripts/capture_submission.py
```

The script checks the expected counts and fix outcomes before saving each state. It replaces this pack's screenshot outputs. It does not change application code or fixtures. Set `FAILURE_COMPILER_URL` to capture another local frontend address.

[captures.json](captures.json) records the capture source and browser errors. [files.json](files.json) records PNG dimensions and file sizes. The fresh capture completed with no page errors.
