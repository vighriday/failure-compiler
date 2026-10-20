# README and Devpost gallery

Captured from the running app with Playwright at **1500 × 1000**, a 3:2 viewport. These are actual screenshots of the saved example, with its real provider responses and live checker. No DOM text, styles or results are replaced for the camera. Scrolling frames the relevant controls.

| File | Shows |
| --- | --- |
| [01-paste-plan.png](01-paste-plan.png) | Landing hero. |
| [02-plan-map.png](02-plan-map.png) | Reviewed map and the highlighted source line for Route C. |
| [03-crash-test-grid.png](03-crash-test-grid.png) | Original 100-case result grid. |
| [04-broken-case.png](04-broken-case.png) | Van + Anita leaves early, with all three real turned-down cards. |
| [05-fix-turned-down.png](05-fix-turned-down.png) | Filled spare-key builder and its scored "Your change" card. The existing filename is retained for the README link. |
| [06-report.png](06-report.png) | Final report count, limits, example notice and fingerprint. |

[video-thumbnail.png](video-thumbnail.png) is the actual landing hero, also 1500 × 1000. It is an image for the pending video link, not a video recording. [flip.gif](flip.gif) alternates two actual 1500 × 1000 screenshots taken before and after accepting the Sam loader card, three seconds each. It is a before/after comparison, not a video of the transition.

Regenerate from the repository root:

```powershell
npm run build
uv run --with pillow -- python scripts/capture_gallery.py
uv run -- python scripts/capture_report.py
uv run --with pymupdf -- python scripts/verify_report_pdf.py
uv run -- python scripts/check_readme_links.py --external
```

The capture scripts use isolated local servers and fail if they try to request new AI output. The printed [sample report](../sample-report.pdf) follows the complete real-card story: one accepted AI change, two coordinator changes, all 100 scenarios survived. A4 is committed; the Letter proof and rendered verification pages stay local under `devpost/screens/`.
