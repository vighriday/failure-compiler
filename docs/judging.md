# Run Failure Compiler: judge guide

**Current demo: run it locally. There is no deployed public app URL.**
The complete saved example needs no account, API key, Docker, browser-test
download or paid hosting. Live reading of your own plan needs your own AI key.
Internet is needed for the initial dependency downloads and live AI requests.

## 1. Install two tools

- **Node.js 22 LTS**, including npm: [download Node.js](https://nodejs.org/en/download).
  Node 20 or newer also works with this build.
- **uv**, which downloads Python 3.12 for you:
  [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

Open a new terminal after installing. You do not need to activate a Python
environment or change PowerShell's execution policy.

## 2. Get the project

With Git installed:

```text
git clone https://github.com/vighriday/failure-compiler.git
cd failure-compiler
```

Or use the repository's **Code > Download ZIP**, extract it, and open a terminal
inside the extracted folder containing `pyproject.toml` and `package.json`.

## 3. Install and build once

The same commands work in PowerShell, macOS Terminal and Linux shells:

```text
uv sync --frozen --no-dev --python 3.12
npm ci
npm run build
```

`--no-dev` leaves out test and browser tools. The app needs no Playwright browser
download. The first setup downloads Python if needed, AI SDKs, the native checker
and frontend packages; allow download time and free disk space. Later runs reuse
the installation. Node is needed for this build step; the built app uses one
Python server.

If PowerShell says `npm.ps1` cannot run, use `npm.cmd ci` and
`npm.cmd run build` instead. No execution-policy change is needed.

## 4. Start the app

```text
uv run --no-dev -- python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Wait for **Application startup complete**, then open:

**http://127.0.0.1:8000/demo**

Keep the terminal open. This one server supplies both the website and API.
Use **Ctrl+C** to stop it. Next time, run only the start command. Rebuild with
`npm run build` after updating frontend source.

## 5. Try the complete example without a key

1. Open **Start**, then **Load the example plan**, then **Read plan**.
2. The saved response is real captured Gemini output. It contains guesses and
   questions deliberately requiring review.
3. At the **Hall** identity question, choose **Same place as another listing**,
   select **Loading bay**, then **Use this place**.
4. Use **Confirm everything that isn't a guess**. For each guessed row, choose
   **Answer > Keep this guess** after checking it. Confirm any remaining rows
   individually. Answer the arrival questions with **Use the reviewed details**.
5. The footer reaches **30 of 30 confirmed**, with no open questions. Choose
   **Confirm plan** and let the grid finish.

Expected original result:

> 100 tests: 1 single weak spot, 3 hidden pairs, 12 already broken by the weak
> spot, 84 survived.

### Play the fix story

| Open this case | What to do | Expected result |
|---|---|---|
| Van late + Anita leaves early | Read the timeline and all three AI cards. All are turned down by the checker. | Route C: 8 households not delivered. |
| Van late + Anita absent | Accept **Add an extra loader (Sam) to Route C**. | Both van pairs survive; 86 survived in total. |
| Joel absent | The AI's one-key card is turned down. Under **Test your own change**, choose **Give a spare key > Maya**, add another operation **Give a spare key > Sam**, then **Test this change** and **Accept fix** on Your change. | 99 survived. |
| Supply truck late + Ravi absent | Build **Add a driver > Route A > Sam**, test it and accept Your change. | **All 100 tested scenarios survive.** |

Try **Before / After**, then **See report**. The report records one accepted AI
fix and two of your changes, the original failures and explicit limits. Use
**Print or save as PDF** for browser printing. An already printed example is
available as [sample-report.pdf](sample-report.pdf).

For the exact recording sequence and controls, see the
[demo runbook](../devpost/demo-runbook.md). Opening `/demo` again resets only
this browser's session and returns to a clean starting point.

## 6. Try your own plan with your own key

**No `.env` file is required for this path.**

1. Get a key from [Groq](https://console.groq.com/keys) or
   [Google AI Studio](https://aistudio.google.com/apikey). Provider access,
   regional eligibility, quotas and any charges are set by that provider.
2. Open `/demo` for a clean session. Go to **Start**, paste a short community
   distribution plan, and expand **Use your own AI key**.
3. Choose the matching provider and paste its key into the password field.
   The selected provider is tried first. Click **Read plan**.
4. Review the facts and source labels, correct picks or times where necessary,
   answer all guesses and questions, then confirm and run the checker.
5. Open a cross to request live suggestions. Use the same preview, builder and
   acceptance controls as in the example. Your own plan can have different
   problem counts and outcomes; the 100-case numbers belong to the saved example.

**Provider check, 21 October 2026:** a real Groq reading succeeded. The Gemini
request returned HTTP 504, so Gemini availability is not promised. Gemini remains
the configured primary based on the recorded comparison; selecting Groq in the
key picker tries Groq first. If a provider is unavailable or its quota is
exhausted, retry later, select another available key or return to the saved
example. The saved example does not call either provider.

A successful read clears the input field. Typed keys stay in that server
session's memory and are not returned in API responses or written to `.env`.
Closing the tab does not clear server memory: use `/demo` or restart the server.
Your live plan and relevant checker facts are sent to your selected AI provider;
the Gemini data notice is shown on Start. Use fictional information for judging.

### Optional: configure both providers for automatic fallback

Create `.env` beside `pyproject.toml`, using the empty `.env.example` as a guide:

```dotenv
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

Use only your own keys. `.env` is ignored by Git. Gemini is tried first unless
you explicitly select another provider with a typed key. On an eligible failure,
the server can try Groq when its key is available. A wrong key requires correction;
fallback is not a way around authentication or exhausted account allowances.

## No room to install locally? Optional private Codespaces run

You can run a private copy in your browser using GitHub Codespaces. This is a
development workspace you start, not a permanently hosted public demo.

GitHub personal accounts include a monthly allowance. GitHub Free currently
includes 120 core-hours and 15 GB-month storage; a 2-core workspace uses two
core-hours per running hour. Without a payment method, usage stops when the
allowance is exhausted. Check your own remaining allowance first.
[Official billing and quotas](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces).

1. Open [this repository in Codespaces](https://codespaces.new/vighriday/failure-compiler).
   Sign in to your own GitHub personal account and choose the default 2-core
   workspace. Do not choose paid resources if your allowance is unavailable.
2. In its browser terminal, install uv using the official Linux installer if
   `uv --version` is not available:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   . "$HOME/.local/bin/env"
   ```

3. The repository is already present. Run the install/build commands in step 3,
   followed by the start command in step 4.
4. In the **Ports** panel, open port **8000** in your browser. Keep its visibility
   **Private**. Use that forwarded address, with `/demo` appended, instead of
   `127.0.0.1` on your own device.
5. Use a typed key if desired. It stays in your private remote server's memory,
   not on your laptop. Stop and delete the workspace when finished to release
   compute and storage usage.

This path follows GitHub's documented
[private port forwarding](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace).
An account-owned Codespace has not been launched as part of this verification;
availability depends on your account and remaining allowance. The application
image is verified separately on a Linux runner when the linked workflow passes.

## Troubleshooting

| What you see | What to do |
|---|---|
| `uv`, `node` or `npm` is not recognized | Install the two prerequisites and open a new terminal. Check `uv --version` and `node --version`. |
| An activated environment from another project | Open a fresh terminal in this project. Environment activation is not required. |
| A blank page or missing frontend | Run `npm ci` and `npm run build` before starting the Python server. The judge setup needs a built frontend. |
| Port 8000 already in use | Stop the old app terminal with Ctrl+C. Or run the same start command with `--port 8001`, and open `http://127.0.0.1:8001/demo`. |
| Confirm plan is disabled | Answer every guess and question, confirm any stale facts and resolve the named rule errors. Bulk confirm deliberately skips guesses. |
| Missing/invalid key, 429, 503 or 504 | Choose the correct provider, check its key and quota, or retry later. The saved example remains available without a key. |
| Both providers failed | Retry later or use the saved example. The checker facts remain available when suggestions fail. |
| A `?` result | The checker could not prove a verdict. It never counts as survived. The report names these results. |
| Fresh start needed | Open `/demo`. It clears only this browser's server session and local browser state. |

## Optional developer checks

Judges do not need these tools to use the app. To run the automated suite:

```text
uv sync --frozen
uv run -- python -m pytest -q
uv run -- ruff check .
npm run build
uv run -- python scripts/check_map.py fixtures/example-truth.json
```

For browser verification, install Chromium once and run the offline runner:

```text
uv run -- python -m playwright install chromium
uv run -- python scripts/verify_browser.py
uv run -- python scripts/verify_live.py
```

Both browser commands replay saved or explicitly synthetic responses without
using real keys. Real-network tests require separate explicit opt-in. The
[Linux container workflow](../.github/workflows/verify-container.yml) builds and
runs Docker remotely; it does not deploy a public service or need local Docker.
