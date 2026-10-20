# Deployment readiness

## Container contract

The root [Dockerfile](../Dockerfile) builds the Vite frontend and runs FastAPI
as one process. FastAPI serves `/` and `/assets/*` from `web/dist`, so a host
only needs to expose the container's `PORT` (default `8000`). The container
binds `0.0.0.0`; [scripts/dev.py](../scripts/dev.py) remains local-only on
`127.0.0.1`.

The public deployment must provide HTTPS at the host or reverse proxy, set no
provider API keys, and keep the container filesystem ephemeral. Visitors can
use example mode without a key or enter their own Gemini or Groq key. Keys are
held only in that browser's in-memory session, are never included in map data,
and are redacted from error messages. There is no server-side shared example
credential.

Each browser receives an opaque session cookie. Readings, plans, fix history
and keys are scoped to that cookie. The AI endpoints reject plans over 4,000
characters and allow six live requests per minute per browser/client and
endpoint in the single-process deployment. A scaled deployment should add a
distributed limiter at the edge. The solver retains the existing 24-problem
cap.

## Host comparison

| Host | Cost for this proof of concept | Cold start / sleeping | Solver fit | Until 4 Nov |
|---|---|---|---|---|
| Hugging Face Spaces with Docker | Free CPU Space is the lowest-cost option; paid hardware is available if needed | Free Spaces can sleep and wake slowly after inactivity | A CPU Space can run OR-Tools, but memory and build limits need checking | Good for a short demo if the Space stays healthy; less predictable |
| Render | Free web service sleeps after inactivity; paid Starter is predictable and inexpensive | Free cold starts; paid service stays warm | Straightforward Docker deploy and enough CPU for the fixed checker | Best balance if a small paid instance is acceptable |
| Fly.io | Small shared CPU VM is low cost, with usage-based billing | Can auto-stop unless configured to stay running | More control over CPU and region, but more operational setup | Reliable when `auto_stop_machines = false`; requires account and billing setup |

## Current decision

The project is currently **local-first** and has no live deployment. This is the
tested demo path and the README does not claim a public instance. The Dockerfile
and this document remain optional preparation for a future host.

Render Starter was previously considered, but it requires billing details for
the user's account and is not being used. A new free Hugging Face Docker Space
also requires a paid plan according to the current Hugging Face documentation.
Do not use a cron job to defeat provider sleep policies. If a future deployment
is wanted, choose a host explicitly, review its current terms, and verify the
live URL before adding it to the README.

## Local verification limitation

The Windows development machine used for this completion pass has neither
Docker nor Podman, so a local image build and container run could not be
honestly completed here. The Dockerfile is deterministic and the application
contract is covered by the existing full suite plus deployment-specific
configuration tests; run `docker build -t failure-compiler .` and
`docker run --rm -p 8000:8000 failure-compiler` on a machine with Docker before
publishing the URL.
