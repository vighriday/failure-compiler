# File review inventory

Reviewed on 17 October 2026 against application checkpoint `f00bf91`.

The review covered all 113 tracked files: 85 application, design, test, configuration and project-document files, plus 28 bundled workflow files. Source review was combined with executable checks. Generated components were regenerated into an ignored temporary folder and compared with the checked-in files. Lockfiles were parsed and checked against their manifests, rather than treated as handwritten application code.

Private `.env` contents, the private learner profile, installed third-party source, dependency caches and Git internals are outside this inventory. The inaccessible `.pytest_cache` directory is a generated cache. Screenshots and diagnostic output remain in the ignored `devpost/screens/` folder. This inventory records review coverage; an entry does not mean every possible input has been proved correct.

## Root files

| File | Review result |
| --- | --- |
| `.env.example` | Empty provider-key placeholders. Real provider integration is pending. |
| `.gitignore` | Credentials, private profile, screenshots and frontend output excluded. Local extra memory rule left untouched. |
| `LICENSE` | MIT license present, with project copyright. |
| `README.md` | Setup, example counts and current build status checked. Nine linked local assets absent; video and personal narrative still placeholders. Some claims exceed current coverage. |
| `package.json` | React, Vite, TypeScript, fonts, GSAP and converter dependencies present. Build passes. |
| `package-lock.json` | Parsed; installed top-level dependency tree is valid. Registry audit reports zero known JavaScript advisories. |
| `pyproject.toml` | Python, solver, validation, test and browser dependencies reviewed. Full configured lint currently fails. |
| `uv.lock` | Parsed; `uv lock --check` passes. No live provider call was attempted. |
| `skills-lock.json` | Six bundled workflow sources and recorded hashes present. Not application functionality. |
| `tsconfig.json` | Solution configuration references app and build-tool projects. Bare `tsc --noEmit` lists no source files here. |
| `tsconfig.app.json` | Strict checking enabled, although application entity types still use `any`. Production build checks this project. |
| `tsconfig.node.json` | Vite configuration type-checking project present. |
| `vite.config.ts` | React build, `web` root, production output and local API proxy reviewed and exercised. |

## Backend

| File | Review result |
| --- | --- |
| `server/__init__.py` | Package marker. |
| `server/config.py` | Five problem categories, preset sizes, 24-problem cap and deterministic solver settings. AI names are unused configuration; lint cleanup needed. |
| `server/models.py` | Checker, result and fix shapes reviewed. Fix operations use strict validation; other models allow some type coercion. |
| `server/main.py` | Seven working API routes across the app. Example reading uses truth data plus handwritten reading metadata. Confirmation omissions and duplicate-ID handling need repair. |
| `server/grid.py` | Live SSE, count arithmetic, pacing and cached replay exercised. Cached scenario identifiers need canonical ordering. Two lint errors. |
| `server/fixes.py` | Allowed operations, rule checks, live scoring, rejected fixes, cache and acceptance chain exercised. Client-supplied eligibility is rejected. |
| `server/session.py` | In-memory maps/results reviewed. Cache remains until process exit. Same-fingerprint reordered maps can mismatch cached scenario identifiers. |
| `server/checker/__init__.py` | Package marker. |
| `server/checker/scenarios.py` | Singles/pairs and same-entity exclusions checked. Pair identifiers depend on input order. |
| `server/checker/runner.py` | Singles first, dimming, live iteration and deferred solver import verified. |
| `server/checker/solver.py` | Scheduling constraints, shared resources, absence/early-exit changes, weighted lateness, non-delivery penalty and verdict extraction reviewed. Locked example passes; lint cleanup needed. Models one selected shared loading area. |
| `server/checker/explain.py` | Checker-derived reasons match all four locked crosses. Logic is tailored to the supported loading-area model. |
| `server/validation/__init__.py` | Package documentation. |
| `server/validation/models.py` | AI reading separated from server metadata; all required AI fields and map conversion reviewed. Non-strict scalar coercion and generic UI integration remain gaps. |
| `server/validation/gate.py` | JSON/schema checks, references, duplicates, stable IDs and metadata wrapping reviewed. Standalone tests pass; HTTP confirmation does not consistently apply this gate. |
| `server/validation/fingerprint.py` | Checker-only SHA-256 hash, ID normalization and collection sorting verified. Hash stability is correct; runtime/cache ordering needs alignment. |
| `server/validation/rules.py` | Driver eligibility, references, positive route values, problem cap and preset sizes checked. Empty plans and negative availability times currently pass. |

## Frontend

| File | Review result |
| --- | --- |
| `web/index.html` | App mount, title, viewport and local module entry present. |
| `web/src/main.tsx` | React entry and self-hosted IBM Plex fonts reviewed; production build passes. |
| `web/src/App.tsx` | Full example map workflow reviewed. Source trace, bulk confirmation, guesses, questions and Ravi cascade work. Direct Read-tab edits can block re-confirmation; only two reading fields are editable; accepted fixes leave some statements stale. |
| `web/src/types.ts` | Manually maintained API types. Entity collections use broad `Record<string, any>` shapes; generated type synchronization is absent. |
| `web/src/vite-env.d.ts` | Vite environment type reference. |
| `web/src/styles.css` | Map, grid, panel, timeline, fix preview, responsive and reduced-motion styles reviewed. Legacy paste-screen rules remain. No report print layout. |
| `web/src/api/client.ts` | Typed fetch helpers, error messages, streamed SSE parsing and fix requests reviewed and exercised. No live provider request. |
| `web/src/lib/results.ts` | Preview count arithmetic and unknown/pending separation match backend behavior. |
| `web/src/screens/CrashTest.tsx` | Live stream, retry, selection, preview/cancel, acceptance, changed cells and fix history exercised. Report buttons intentionally disabled; Before/After toggle absent. |
| `web/src/components/CrashGrid.tsx` | Four SVG states, axis highlighting, tooltips, omitted impossible combinations, preview outlines and keyboard focus exercised. |
| `web/src/components/CasePanel.tsx` | Human costs, single-case proof, reasons, placeholder explanation, fix cards and rejected acceptance exercised. Missing-suggestion text mentions future key functionality. |
| `web/src/components/CaseTimeline.tsx` | Non-delivered lanes and actual solver bars verified. Scale, noon label and three-lane sizing are example-specific. |
| `web/src/landing/LandingPage.tsx` | Real reading/checker slots and skip-link focus behavior exercised. |
| `web/src/landing/LandingView.tsx` | Generated markup checked through regeneration, type-checking, browser controls and screenshots. Matches converter output. |
| `web/src/landing/SampleGrid.tsx` | Illustration timing, counters, states, selection, resize clamp and reduced motion exercised. Separate from the real solver. |
| `web/src/landing/SampleGridView.tsx` | Generated grid markup matches converter output; all 105 illustration squares exercised. |
| `web/src/landing/data.ts` | Plan source, narrative, labels, three fixes and illustrative state mapping checked against the locked example. |
| `web/src/landing/useLanding.ts` | Navigation, history, scroll tracking, keyboard tabs, shatter recovery, typing, key disclosure and sample interactions reviewed and exercised. Sample timeline has hardcoded times. |
| `web/src/landing/landing.css` | V2 palette, focus states, responsive layout, source view and reduced-motion overrides checked visually and mechanically. |
| `web/src/landing/template-effects.css` | All generated hover/focus rules match converter output. |

## Fixtures

| File | Review result |
| --- | --- |
| `fixtures/example-plan.txt` | Plan facts match truth data: 10/12/8 households, 9:30 van, Joel/Maya hours and Sam driving-only baseline. |
| `fixtures/example-truth.json` | Parsed and validated; all original results and fix-story outcomes reproduced. |
| `fixtures/example-reading.json` | Explicit handwritten placeholder: 24 items, one guess and one question. Source references checked. Not captured AI output. |
| `fixtures/example-fixes.json` | Explicit handwritten explanations and operation suggestions for all four crosses. Live scoring reproduces accept/reject behavior. |
| `fixtures/expected-results.json` | All 100 verdicts, weighted costs and human-cost strings match the live checker. |

## Scripts

| File | Review result |
| --- | --- |
| `scripts/check_map.py` | CLI count reproduced. Unused import; singular/plural labels assume the original example. |
| `scripts/dev.py` | HTTP readiness, 90-second allowance, progress, duplicate protection and process cleanup covered by regression checks. Prior real-start verification retained. |
| `scripts/convert_landing.mjs` | Both source templates regenerated into an ignored folder; all three generated outputs match. No production HTML interpreter or source-template runtime. |
| `scripts/verify_landing.py` | Passed fresh at 1440, 768, 390 and 320 pixels, including animation cleanup and all 105 illustration squares. Does not cover all return-to-map paths. |
| `scripts/verify_story.py` | Passed fresh on development and production frontends: rejected fixes, preview cancellation, three fingerprints and all 100 survivors. |

## Tests

| File | Review result |
| --- | --- |
| `tests/__init__.py` | Test package marker. |
| `tests/validation_helpers.py` | Truth-map and AI-shaped payload factories reviewed. |
| `tests/test_checker_monotone.py` | Passes for solved example pairs. Already-dimmed pairs are skipped; not an exhaustive proof across arbitrary maps. |
| `tests/test_determinism.py` | Exact repeated result comparison passes for identical ordered example input. Does not exercise reordered runtime/cache behavior. |
| `tests/test_dev_launcher.py` | Fourteen cases pass: import separation, busy ports, HTTP readiness, slow start, diagnostics and child cleanup. |
| `tests/test_example_fixes.py` | Seven cases pass, covering rejected driver fix, Sam fixes, spare keys and all-survived result. |
| `tests/test_example_locked.py` | All 100 expected results pass; four crosses have reasoning comments. |
| `tests/test_example_reading_sources.py` | Source tags point to nonblank physical lines. This checks reference locations, not AI extraction accuracy. |
| `tests/test_fingerprint.py` | All three requested hash assertions pass. No cached replay check after reordering. |
| `tests/test_fix_pipeline.py` | Scoring, reasons, acceptance, three-link history, cache and bad-operation rejection pass. |
| `tests/test_format_gate.py` | JSON, extra fields, bad reference, duplicate ID and normalization cases pass. String-to-scalar coercion is not rejected by these tests. |
| `tests/test_live_grid.py` | Expected streaming results, cache replay, counts and unknown-fingerprint rejection pass. |
| `tests/test_rules.py` | Truth map, Ravi correction cascade, missing/non-driving drivers and problem cap pass. Empty maps and negative times are untested gaps. |
| `tests/test_scenario_entities.py` | Same-entity pairs excluded; 86 valid pairs confirmed. |

## Project and design documents

| File | Review result |
| --- | --- |
| `devpost/scope.md` | Approved project boundary and kernel intact. Describes final saved AI experience; current placeholder exception is recorded elsewhere. Some old two-fix wording remains. |
| `devpost/scope.html` | Opens offline; core example facts synchronized; no em dashes or broken internal anchors. |
| `devpost/prd.md` | Approved behavior baseline reviewed. AI/report criteria remain future work; general correction behavior is only partly implemented. |
| `devpost/prd.html` | Opens offline; eight journey steps and five screen cards expand/collapse. Core counts correct; example fix-card scores still reflect old counts. |
| `devpost/spec.md` | Approved blueprint reviewed. Planned provider files, generated types, state organization and report are not all implemented. Correct additive spare-key operation. |
| `devpost/spec.html` | Opens offline; internal anchors work; core counts correct and no em dashes. Still describes transferring the key and removing the original holder's key. |
| `devpost/checklist.md` | Approved, fast mode. Slices 1–5 checked; 6–7 and review/wrap-up unchecked. Verified progress exists, with defects now recorded in the audit. |
| `design/landing-v2/Landing.html` | Preserved source reference; bindings traced through converter and generated UI. Not served as a standalone page. |
| `design/landing-v2/Grid.html` | Preserved source reference; generated grid and controls verified. Source-only support runtime is intentionally not shipped. |
| `design/landing-v2/README.md` | Conversion, live slots and verification instructions checked against actual files. |
| `design/landing-v2/verification.md` | Historical checkpoint and coverage description accurate for its recorded run; fresh checks also pass, with additional gaps found outside that coverage. |

## Bundled workflow files

These are the build curriculum and templates, not implemented product features. Both copies were compared. The eight reference/template pairs are byte-identical. The six skill pairs differ only in frontmatter/name metadata and spacing.

| `.agents/` file | `agent/` companion | Review |
| --- | --- | --- |
| `.agents/skills/1-start/SKILL.md` | `agent/skills/1-start/SKILL.md` | Onboarding workflow; same instruction body. |
| `.agents/skills/1-start/templates/learner-profile-template.md` | `agent/skills/1-start/templates/learner-profile-template.md` | Private-context template; identical. |
| `.agents/skills/2-scope/SKILL.md` | `agent/skills/2-scope/SKILL.md` | Scope workflow; same instruction body. |
| `.agents/skills/2-scope/templates/scope-template.md` | `agent/skills/2-scope/templates/scope-template.md` | Scope template; identical. |
| `.agents/skills/3-prd/SKILL.md` | `agent/skills/3-prd/SKILL.md` | Requirements workflow; same instruction body. |
| `.agents/skills/3-prd/references/prd-guide.md` | `agent/skills/3-prd/references/prd-guide.md` | Requirements reference; identical. |
| `.agents/skills/3-prd/templates/prd-template.md` | `agent/skills/3-prd/templates/prd-template.md` | Requirements template; identical. |
| `.agents/skills/4-spec/SKILL.md` | `agent/skills/4-spec/SKILL.md` | Technical planning workflow; same instruction body. |
| `.agents/skills/4-spec/references/spec-patterns.md` | `agent/skills/4-spec/references/spec-patterns.md` | Architecture reference; identical. |
| `.agents/skills/4-spec/templates/spec-template.md` | `agent/skills/4-spec/templates/spec-template.md` | Technical specification template; identical. |
| `.agents/skills/5-build/SKILL.md` | `agent/skills/5-build/SKILL.md` | Verification, incremental commits and completion rules; same instruction body. |
| `.agents/skills/5-build/references/code-tour.md` | `agent/skills/5-build/references/code-tour.md` | Learning wrap-up reference; identical. |
| `.agents/skills/5-build/templates/checklist-template.md` | `agent/skills/5-build/templates/checklist-template.md` | Progress template; identical. |
| `.agents/skills/6-ship/SKILL.md` | `agent/skills/6-ship/SKILL.md` | Shipping workflow; same instruction body. Not a completed submission record. |

## Local-only changes

- `.gitignore` has an extra local memory ignore rule. Preserved.
- `oxcode.hooks.json` is untracked and invokes `npx tsc --noEmit`. Its contents were inspected without running the hook. That command lists no source files under the root solution configuration; use the real build command to check both TypeScript projects. Preserved and excluded from audit commits.
- The real `.env` and learner profile remain untracked/ignored; their contents were not included in this review or report.
