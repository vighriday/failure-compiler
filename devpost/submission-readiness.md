# Submission readiness

Checked **22 October 2026** against the public hackathon pages and repository.
This is a technical audit and completion checklist, not submission prose.

**The application is ready for recording and local judging. Completion of the
Devpost entry is unverified, so the video cannot yet be called the only remaining
task.**

## Repository evidence

| Item | Evidence and status |
| --- | --- |
| Public source and licence | Anonymous GitHub API access succeeds; `main` is public and GitHub detects MIT. [Repository](https://github.com/vighriday/failure-compiler), [licence](../LICENSE). |
| Planning before implementation | The first commits are approved scope, PRD and spec on 15 October, followed by the checker. All three substantive documents are approved and public: [scope](scope.md), [PRD](prd.md), [spec](spec.md). This supports the recorded build chronology; Git history alone cannot establish every off-repository action. |
| Working complete example | Read, review, confirm, checker, rejected AI cards, accepted Sam card, two coordinator changes, Before/After and report are implemented. The original result is 1 single weak spot, 3 hidden pairs, 12 dimmed and 84 survived. The approved story ends with all 100 survived. |
| Reproducible access | [Judge guide](../docs/judging.md): one local server; no Docker, key or account needed for the saved example. Personal keys are optional for new plans. No public app is deployed. |
| Gallery and report | Six current [gallery screenshots](../docs/images/README.md), recording thumbnails, before/after GIF and [sample report](../docs/sample-report.pdf) are committed. The GIF and thumbnail are labelled accurately; neither substitutes for the pending video. |
| Design and dependencies | [Supplied design provenance](../design/landing-v2/README.md#design-provenance) records the owner's confirmation that Claude Design generated the references. The README and bundled notices identify dependencies and font licences. |
| Privacy | The fresh history/index scan found no credentials or private paths requiring removal. Gitleaks scanned 94 commits without findings. The actual learner profile, `.env` and local verification screenshots stay excluded. This is evidence from scans, not a guarantee against every possible disclosure. |

## Verification

- Fresh Windows offline suite: **238 passed, 2 opt-in network tests skipped**;
  one upstream Starlette deprecation warning. Ruff and TypeScript/Vite build pass.
- Every local README image, file and heading link resolves.
- Fresh saved-story and review browser checks pass, including the all-100 result,
  three linked fix fingerprints, corrections and reconfirmation, with no page errors.
- All six app tabs pass the 11 landing interaction checks at widths 1440, 768,
  390 and 320. This includes interrupted animation recovery, all 105 sample
  squares, scroll steps, rule pickers and reduced motion. Fresh desktop and phone
  screenshots were also inspected.
- Ten accessibility states pass the existing checks: 1,370 keyboard Tab presses,
  no text below 12 px and minimum measured text contrast 4.551:1. The automatic
  scanner's incomplete icon/overlap contrast checks are retained in the local
  proof alongside the supplementary computed text-contrast measurements.
- The offline own-key browser flow passes 16 checks using a real recorded reading
  and synthetic suggestions for error/retry paths: key clearing and privacy,
  environment keys, 503 fallback, both-provider failure, caching, one retry and
  phone layout. Its 12 provider calls are mocked, not live API requests.
- The verified [Linux workflow](https://github.com/vighriday/failure-compiler/actions/runs/39632808174)
  at `dd8dfd5` passed a fresh dependency setup, tests, recorded own-key flow,
  actual Docker build and complete saved story. Docker was run remotely.
- The last real provider checks, on 21 October, were **Groq success and Gemini
  HTTP 504**. Gemini remains the configured primary; its current availability is
  not promised. The saved example makes no provider calls.

## Official requirements and remaining actions

The [overview](https://learn-ai-basics.devpost.com/) requires a new project built
with the skills, its planning documents, a working video and a description of
the project, audience and learning. Repository evidence is above; the owner's
written entry and video remain unverified.

Under the [official rules](https://learn-ai-basics.devpost.com/rules):

- Record working app footage, **under three minutes**, publicly visible on
  **YouTube or Vimeo**; use English or supply an English translation.
- Confirm personal/team eligibility, ownership, permitted asset use and any
  incorporated work disclosures. Avoid unauthorised material in the recording.
- Keep judging access free through 30 October. Repository plus video is an
  allowed access path; a hosted app is unnecessary.
- Complete and submit the entry by **26 October 2026, 5:00 pm EDT**, which is
  **27 October 2026, 2:30 am IST**. A saved draft is not a submitted entry.

The [organiser's update](https://learn-ai-basics.devpost.com/updates/46821-two-new-questions-on-the-submission-form)
adds two required fields: an explanation of actual Skill Pack use and the
age-of-majority checkbox. The
[repository reminder](https://learn-ai-basics.devpost.com/updates/46766-don-t-forget-to-include-a-url-to-your-public-repo)
places the public repository URL in **Try it out**. Check these even on an
already saved entry.

### Check in the private submission form

- [ ] Registration, eligibility and team details are correct.
- [ ] The owner has written all required project and Skill Pack answers and
  completed the form's reflection/exit-survey questions.
- [ ] Try it out contains `https://github.com/vighriday/failure-compiler`.
- [ ] The public video URL works when signed out; the footage matches the app.
- [ ] Images, disclosures and testing instructions match the repository.
- [ ] The entry is submitted to this hackathon, with confirmation received.

The private form was unavailable for inspection. Its exact prompts, saved
answers, registration and submission status are **not verified**. These boxes
record missing verification, not an assertion that the owner left them blank.

## Tabs checked

| Devpost tab | Finding |
| --- | --- |
| Overview | Project, planning, description and video requirements checked. |
| My projects | Public view requires registration; no account-owned entry inspected. |
| Participants | Sign-in required; no participant list or personal data collected. |
| Resources | Official Skill Pack and help events reviewed. No extra deliverable identified. |
| Rules | All 15 sections reviewed; personal declarations remain the owner's responsibility. |
| Project gallery | Not yet published. Public filters show participation, resources-used and value questions; they do not prove the private form is complete. |
| Updates | All listed updates reviewed, including the added required questions and repository field. |
| Discussions | All four listed topics reviewed. The manager says the Skill Pack should be used from the beginning; the recorded planning-first history supports that sequence here. Replies from other entrants are not treated as rules. |

The rules list **four equal judging criteria**: design, potential impact,
innovation and presentation. Design is the first tie-break comparison. The
overview's shorter list omits potential impact; use the rules when preparing
the entry. The existing [2:30 click runbook](demo-runbook.md) demonstrates the
working kernel and explicit limits; narration and reflection belong to the owner.

## Project workflow status

All seven slices, the focused learning activity and app map are complete.
The owner's final hands-on and explicit ready-to-ship boxes in
[checklist.md](checklist.md#final-review) remain open under the build workflow.
Automated verification does not fill in that personal approval. This audit does
not certify contest acceptance, submit the entry or claim a prize outcome.
