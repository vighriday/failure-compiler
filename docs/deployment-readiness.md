# Hosting and container verification

## Current decision

**The supported judging path is a local run. No public application URL exists.**
Use the [judge guide](judging.md): build once, start one Python server, open
`http://127.0.0.1:8000/demo`. The complete saved example needs no key or Docker.
The guide also covers personal AI keys and an optional private Codespaces run.

A Railway trial is a plausible next hosting experiment if the owner's account
has verified outbound access and credit. It is not a deployed demo, an unlimited
free service or a promise that every account can proceed without a card. A public
URL also needs the application protections listed below.

## What was actually verified

The actual [Dockerfile](../Dockerfile) was built and run on **Ubuntu 24.04** by
the public repository's standard GitHub-hosted runner, at commit `dbae42f`.
[Successful container verification](https://github.com/vighriday/failure-compiler/actions/runs/39627825863).

That run passed:

- Fresh Linux dependency installation, Ruff, frontend compilation and **238
  tests**, with two explicitly opt-in network tests skipped.
- The actual multi-stage image build, including its imported example fixture.
- Container startup, API health, production frontend and licence-notice serving.
- The complete real-card browser story against the image, ending at **all 100
  survived**, with three linked fix fingerprints and no page errors.
- A check that `.env` and the personal profile are absent from the image.

The container used **135.4 MiB** when sampled after the story. This is a single
observation on a runner with 15.61 GiB available, not peak usage or a guarantee
for a small hosting plan. No provider key was supplied to that job. It made no
live-provider calls and deployed no service. Standard runner usage is free for
public repositories; it is verification compute, not public website hosting.
[GitHub runner policy](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).

Nothing was installed locally to obtain this Docker proof. Docker/Podman remains
unavailable on the owner's device. Base-image tags and the installed `uv`
version remain mutable, so future builds still need verification.

## Hosting options checked on 21 October 2026

The conclusions below separate platform documentation from this application's
requirements. Account eligibility and available credit must be checked in the
owner's dashboard; no account or paid plan was created during this work.

| Option | What the official documentation allows | Fit for this project |
|---|---|---|
| **Vercel** | FastAPI is supported as a Vercel Function. Hobby currently has a 500 MB Python bundle limit, 2 GB memory and a 300-second maximum invocation. [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [limits](https://vercel.com/docs/functions/limitations). | **Requires architecture work.** The app holds keys, reviews, results and fix history in process memory across requests. Vercel explicitly advises external shared state because instances can be recycled and requests can reach different instances. Frontend-only hosting would still need a backend. [State guidance](https://vercel.com/kb/guide/vercel-services-fluid-compute). |
| **Railway** | The trial grants $5 for up to 30 days, then becomes a Free plan with $1/month credit. Trials have 1 GB RAM; unverified accounts have restricted outbound networking. GitHub activity affects automated verification. [Trial terms](https://docs.railway.com/pricing/free-trial). | **Plausible trial candidate.** A single long-running process fits better, and Railway can build the checked-in Dockerfile remotely. Live AI needs verified outbound access. Availability lasts only while the account's credit and limits allow; host performance and public protections still need testing. [Cloud Docker builds](https://docs.railway.com/builds/dockerfiles). |
| **Render** | Free web services are documented; free instances sleep after 15 idle minutes and are subject to usage limits. Accounts without payment methods can have services suspended rather than incur overages. [Free services](https://render.com/docs/free), [billing FAQ](https://render.com/docs/faq). | **Possible only if the account allows it.** The old `render.yaml` selected paid Starter compute; it now selects **Free**. That removes the paid default, but does not bypass a dashboard's verification/card requirement or establish performance on free compute. |
| **Hugging Face** | New Docker and Gradio compute Spaces require a paid plan; Static Spaces remain free. The personal ZeroGPU exception concerns Gradio, not this Docker deployment. [Current policy](https://huggingface.co/docs/hub/spaces-overview). | **No suitable drop-in free Space for this app.** Static hosting cannot run the Python checker. A Gradio rewrite would change the existing interface and would not provide the current Docker deployment. |
| **Northflank** | A free Sandbox exists, but every user must add a payment method before creating resources, regardless of plan. [Payment-method requirement](https://northflank.com/docs/v1/application/billing/pricing-on-northflank). | **Does not meet the no-card requirement.** |
| **GitHub Codespaces** | Personal accounts include a monthly allowance; Free currently includes 120 core-hours and 15 GB-month storage. Without a payment method, exhausted allowance blocks further use. [Quotas](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces). | **Optional private browser workspace.** Runs the whole app remotely without filling the laptop. A judge uses their own account and keeps port 8000 private. It is not a shared public demo, and no account-owned workspace was launched in this verification. [Port forwarding](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace). |

**There are possible free/trial routes; none is a verified permanent, card-free
public deployment of this app.** Until an eligible account and a hardened public
instance are tested, the submission should link the repository, judge guide,
video when available, screenshots and sample report, and state **local run**.

## Required before an untrusted public URL

These protections remain separate from the successful container test:

- **Provider keys:** local mode deliberately reads operator keys from `.env`
  and process environment. Public mode must ignore those keys and offer the
  saved example or each visitor's own session key. Do not put developer keys
  in hosting settings.
- **Ownership:** normal browser-owned maps/reviews are isolated. Exclude the
  trusted unowned-map helper fallback from public requests and test that boundary.
- **Resource budgets:** the current six-request AI limiter combines session/IP
  and endpoint; a new cookie receives a new allowance. Add an independent IP
  budget and checker CPU/concurrency limits.
- **Retention:** bound and expire sessions, reviews, maps and caches; abandoned
  or repeated sessions must not grow memory indefinitely.
- **HTTP boundary:** verify HTTPS/proxy configuration, Secure cookies, private
  no-store responses, Origin checks and a body-size limit. A provider's TLS
  certificate alone does not supply those application controls.
- **Host behavior:** verify cold starts, solver latency, memory, session loss
  on restart, outbound provider access and a spending cap on the actual plan.

Do not use cron pings to defeat a free plan's sleep rules. The verified container
is useful deployment evidence; it does not certify any external hosting plan.

## Optional Docker commands on another machine

Judges can use the no-Docker guide instead. If Docker is already available:

```text
docker build -t failure-compiler .
docker run --rm -p 127.0.0.1:8000:8000 failure-compiler
```

Open `http://127.0.0.1:8000/demo`. The image serves both the built frontend and
the API on that one port. It needs no key for the saved example; use the app's
typed-key control for your own live plan. Its sessions disappear when the
container stops. The port publication above is loopback-only.
