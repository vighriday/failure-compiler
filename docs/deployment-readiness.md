# Deployment readiness

## Current status

This is a **local-first proof of concept**, with no live deployment. The tested
demo path is the local launcher, saved example and browser checks described in
the [README](../README.md). No host is currently selected. The Dockerfile and
`render.yaml` are preparation only, not evidence that the app is ready for an
untrusted public audience.

## Container preparation

The root [Dockerfile](../Dockerfile) is intended to build the Vite frontend and
run FastAPI as one process. FastAPI serves `/` and `/assets/*` from `web/dist`.
The container listens on `0.0.0.0` at `PORT` (default `8000`); the local
[launcher](../scripts/dev.py) binds to `127.0.0.1`.

The frontend stage now includes the example text imported by the application.
An isolated Windows copy of that build context failed before this file was
included and passed after the repair. This checks the frontend inputs, not a
Linux image build. Base-image tags and the installed `uv` version are not
pinned, so the Dockerfile does not guarantee an identical build over time.

This Windows machine has no Docker or Podman engine. **The image has not been
built or run here.** On a machine with Docker, first test it locally without
provider keys:

```powershell
docker build -t failure-compiler .
docker run --rm -p 127.0.0.1:8000:8000 failure-compiler
```

Then verify the saved example, session separation, reset, report and startup
from the actual image. Publishing its port to the internet needs the work
below as well.

## Required before public hosting

These are **missing protections**, not completed container features:

- **Provider keys:** local mode deliberately reads operator keys from `.env`
  or the process environment and can use them for any browser. A public mode
  must ignore operator keys and offer only the saved example or each visitor's
  own session key. Do not put developer keys in host settings.
- **Ownership boundary:** browser-owned maps and reviews are isolated, but the
  trusted unowned-map helper fallback must be excluded from public requests.
  Verify two unrelated browsers cannot access each other's state, including
  helper-created maps.
- **Resource limits:** the basic AI limiter allows six requests per minute per
  combined session/IP and endpoint. A new cookie, including one created by
  `/demo`, gets a new allowance. There is no independent IP limit or shared
  checker CPU/concurrency budget. The 4,000-character plan limit and 24-problem
  cap do not supply those protections.
- **State lifetime:** session, review, map and cache stores have no general
  expiry or size bound. Public hosting needs bounded retention and cleanup,
  including abandoned sessions and completed work.
- **HTTP boundary:** configure and verify HTTPS, Secure cookies, private
  no-store responses across sensitive APIs, trusted proxy handling, Origin
  checks and a request-body size limit. The current application does not enforce
  this complete public-hosting contract. Keep keys out of host logs and use
  ephemeral storage; verify these settings on the chosen host.

Implement and test these boundaries before choosing a public URL. A host's TLS
certificate alone does not supply the application protections above.

## Host comparison

Official information checked **21 October 2026**. Prices are USD snapshots,
excluding taxes and extra usage. None of these hosts has been measured with
this app; CPU/RAM figures are not a checker performance claim.

| Host | Cost and resources | Idle behavior and remaining check |
|---|---|---|
| Hugging Face Docker Spaces | Creating a Docker compute Space requires a paid plan. CPU Basic has 2 vCPU and 16 GB RAM with no hourly hardware charge, separate from that plan requirement. [Official overview](https://huggingface.co/docs/hub/spaces-overview). | CPU Basic currently sleeps after 48 inactive hours and restarts for a visitor. [Sleep policy](https://huggingface.co/docs/hub/spaces-gpus#set-a-custom-sleep-time). Check the account's settings and measure wake-up and solver times before recording. |
| Render | The `1c-2g` plan, formerly Standard, has 1 CPU and 2 GB RAM; Render quotes approximately $25/month. [Compute specifications](https://render.com/docs/compute-plans), [published cost](https://render.com/articles/best-cloud-platforms-for-enterprise-ai-deployment). | Free services sleep after 15 idle minutes and take about a minute to wake; paid compute removes those free-instance limitations. [Free-service limits](https://render.com/docs/free). Measure startup, memory and full-story latency on the selected paid size. |
| Fly.io | A shared 1-CPU, 1-GB Machine is $6.70 per 30 days of continuous runtime in its lowest-priced regions. Billing is per second; region, traffic and other resources change the total. [Official pricing](https://fly.io/docs/about/pricing/). | Auto-stop depends on configuration. Check the running-machine settings, memory and cold starts; the compute estimate is not a complete hosting bill. |

Render paid compute is a candidate for a later measured trial, not a current
deployment recommendation. Its retained Starter configuration has not been
validated for this workload. No option here guarantees availability through
4 November. Recheck terms and costs, choose a host explicitly, complete the
public-hosting work, and verify the live URL before adding it to the README.
Do not use a cron job to defeat a provider's sleep policy.
