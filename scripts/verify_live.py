"""Verify the live browser flow offline with a recorded reading and test provider doubles.

Both SDK entry points are replaced before the local server starts. No network AI call
is possible. By default fixes are clearly labelled synthetic test data. --fix-record
can replay an unedited provider record from the local review folder after capture.
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.browser_review import review_example  # noqa: E402
from server import credentials, main  # noqa: E402
from server.ai import gemini_provider, groq_provider  # noqa: E402
from server.ai.types import AIError, ProviderResponse  # noqa: E402
from server.config import PROVIDER_MODELS  # noqa: E402

TEST_KEY = "offline-browser-test-key-not-a-real-credential"
MAIN_PAIR = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"


class OfflineProviders:
    def __init__(self, record=None):
        self.reading = json.loads(
            (ROOT / "fixtures/example-reading.json").read_text(encoding="utf-8")
        )
        self.record = record
        self.mode = "success"
        self.env_keys = {}
        self.calls = []
        self.fix_raw = None

    def generate(self, provider):
        def call(_system, _user, _schema, _key, version):
            self.calls.append((provider, version))
            if self.mode == "invalid":
                raise AIError(
                    "invalid_key", "The AI key is invalid. Check it and try again.", status=401
                )
            if self.mode == "both_failed":
                raise AIError(
                    "server_error", "The provider is temporarily unavailable (503).", status=503
                )
            if not version.startswith("read-") and self.record:
                if provider != self.record["provider"]:
                    raise AIError(
                        "server_error",
                        "Offline replay: this provider has no fix record (503).",
                        status=503,
                    )
                response = ProviderResponse(**self.record)
                self.fix_raw = response.raw_text
                return response
            if self.mode == "fallback" and provider == "gemini":
                raise AIError(
                    "server_error", "The provider is temporarily unavailable (503).", status=503
                )
            raw = (
                self.reading["raw_text"]
                if version.startswith("read-")
                else (
                    json.dumps(
                        {
                            "explanation": (
                                "Synthetic offline test explanation: "
                                "Route C has no loader available."
                            ),
                            "fixes": [
                                {
                                    "id": "offline-sam-loads-c",
                                    "description": (
                                        "Synthetic test fixture: add Sam as a Route C loader"
                                    ),
                                    "operations": [
                                        {
                                            "op": "add_loader",
                                            "target_id": "route-c",
                                            "field": "loader_ids",
                                            "value": "person-sam",
                                        }
                                    ],
                                }
                            ],
                        }
                    )
                )
            )
            if not version.startswith("read-"):
                self.fix_raw = raw
            return ProviderResponse(
                provider,
                PROVIDER_MODELS[provider],
                version,
                "2026-10-19T00:00:00Z",
                raw,
                0,
                0,
                0,
                {"offline_replay": True},
            )

        return call


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-record", type=Path)
    parser.add_argument("--prefix", default="slice6-live")
    args = parser.parse_args()
    fix_record = (
        json.loads(args.fix_record.read_text(encoding="utf-8")) if args.fix_record else None
    )
    if fix_record and "raw" in fix_record:
        fix_record = fix_record["raw"]
    providers = OfflineProviders(fix_record)
    original = (gemini_provider.generate, groq_provider.generate, credentials.dotenv_values)
    saved_env = {name: os.environ.pop(name, None) for name in ("GEMINI_API_KEY", "GROQ_API_KEY")}
    gemini_provider.generate = providers.generate("gemini")
    groq_provider.generate = providers.generate("groq")
    credentials.dotenv_values = lambda _path: providers.env_keys
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    base = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(main.app, log_level="warning"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    screens = ROOT / "devpost/screens"
    screens.mkdir(exist_ok=True)
    plan = (ROOT / "fixtures/example-plan.txt").read_text(encoding="utf-8")
    errors, returned = [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "response",
                lambda response: (
                    returned.append(response.text())
                    if any(
                        path in response.url
                        for path in ("/api/read-plan", "/api/suggest-fixes", "/api/ai-status")
                    )
                    else None
                ),
            )
            page.goto(base + "/#start")
            expect(page.locator(".gemini-data-notice")).to_contain_text("Google may use content")
            page.get_by_role("textbox", name="Your plan", exact=True).fill(plan)
            page.get_by_role("button", name="Read plan", exact=True).click()
            key = page.get_by_label("AI key", exact=True)
            expect(key).to_be_visible()
            expect(key).to_be_focused()
            expect(page.locator(".landing-error")).to_contain_text("Add an AI key")
            key.fill(TEST_KEY)
            providers.mode = "invalid"
            page.get_by_role("button", name="Try again", exact=True).click()
            expect(page.locator(".landing-error")).to_contain_text("invalid")
            expect(key).to_have_value(TEST_KEY)
            providers.mode = "success"
            page.get_by_role("button", name="Try again", exact=True).click()
            expect(page.locator(".placeholder-notice")).to_contain_text(
                "Live AI reading. Read by gemini"
            )
            page.get_by_role("tab", name="Start", exact=True).click()
            expect(key).to_have_value("")
            page.get_by_role("tab", name="Read", exact=True).click()
            page.screenshot(path=str(screens / f"{args.prefix}-map.png"), full_page=True)
            review_example(page)
            page.get_by_role("button", name="Confirm plan", exact=True).click()
            expect(page.locator(".crash-count")).to_contain_text("84 survived", timeout=60000)
            expect(page.locator(".result-cell")).to_have_count(100)
            expect(page.locator(".live-view-bar")).to_contain_text("Read by gemini")
            expect(page.locator(".live-view-bar")).to_contain_text("YOUR PLAN")
            providers.env_keys = {"GROQ_API_KEY": "offline-groq-fallback-test-key"}
            providers.mode = "both_failed"
            page.locator(f'[data-scenario="{MAIN_PAIR}"]').click()
            expect(page.locator(".case-panel .inline-error")).to_contain_text(
                "Both providers failed", timeout=60000
            )
            expect(page.locator(".checker-facts")).to_contain_text("Loading team gone")
            page.screenshot(
                path=str(screens / f"{args.prefix}-suggestion-error.png"), full_page=True
            )
            providers.mode = "fallback"
            page.get_by_role("button", name="Try suggestions again", exact=True).click()
            fix_provider = fix_record["provider"] if fix_record else "groq"
            fix_model = fix_record["model"] if fix_record else PROVIDER_MODELS[fix_provider]
            expect(page.locator(".ai-sentence")).to_contain_text(
                f"Suggested by {fix_provider} / {fix_model}", timeout=60000
            )
            if fix_provider == "groq":
                expect(page.locator(".ai-sentence")).to_contain_text("fallback provider")
            else:
                expect(page.locator(".ai-sentence")).not_to_contain_text("fallback provider")
            expect(page.locator(".fix-card").first).to_be_visible()
            if fix_record:
                for suggestion in json.loads(fix_record["raw_text"])["fixes"]:
                    card = page.locator(f'[data-fix-id="{suggestion["id"]}"]')
                    for callout in card.locator(".new-cross-callout").all():
                        text = callout.inner_text()
                        assert ("New hidden pair:" in text) == (" + " in text)
                        if " + " not in text:
                            assert "New single weak spot:" in text
            calls = len(providers.calls)
            page.get_by_role("button", name="Close", exact=True).click()
            page.locator(f'[data-scenario="{MAIN_PAIR}"]').click()
            expect(page.locator(".ai-sentence")).to_contain_text(
                f"Suggested by {fix_provider} / {fix_model}"
            )
            assert len(providers.calls) == calls, "Reopening called a provider again"
            page.screenshot(path=str(screens / f"{args.prefix}-suggestions.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                "Phone viewport overflows"
            )
            page.screenshot(path=str(screens / f"{args.prefix}-phone.png"), full_page=True)
            if not fix_record:
                # The same synthetic change cannot rescue Joel. One explicit extra
                # attempt is available; reopening still does not call a provider.
                providers.mode = "success"
                page.locator('[data-scenario="volunteer_absent__person-joel"]').click()
                retry = page.get_by_role("button", name="None worked. Try once more", exact=True)
                expect(retry).to_be_visible(timeout=60000)
                retry.click()
                expect(page.locator(".suggestion-loading")).to_have_count(0, timeout=60000)
                expect(retry).to_have_count(0)
            stored = page.evaluate(
                "JSON.stringify({local: {...localStorage}, session: {...sessionStorage}, "
                "cookie: document.cookie})"
            )
            assert TEST_KEY not in stored
            assert not any(TEST_KEY in body for body in returned), "A response echoed the typed key"
            context.close()
            # A different browser session uses only fake .env keys. Both-failed
            # reading can retry through the fallback without typing a key.
            providers.env_keys = {
                "GEMINI_API_KEY": "offline-env-gemini",
                "GROQ_API_KEY": "offline-env-groq",
            }
            providers.mode = "both_failed"
            page = browser.new_page(
                viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/#start")
            page.get_by_role("textbox", name="Your plan", exact=True).fill(plan)
            page.get_by_role("button", name="Read plan", exact=True).click()
            expect(page.locator(".landing-error")).to_contain_text("Both providers failed")
            expect(
                page.get_by_role("button", name="Try the example plan instead", exact=True)
            ).to_be_visible()
            providers.mode = "fallback"
            page.get_by_role("button", name="Try again", exact=True).click()
            expect(page.locator(".placeholder-notice")).to_contain_text(
                "Live AI reading. Read by groq"
            )
            expect(page.locator(".placeholder-notice")).to_contain_text("fallback provider")
            assert not errors, errors
            browser.close()
        proof = {
            "offline": True,
            "reading": "unedited recorded response",
            "suggestions": "unedited recorded response" if fix_record else "synthetic test fixture",
            "provenance": {
                "reading": "recorded",
                "fix": "recorded" if fix_record else "synthetic",
                "digest": hashlib.sha256(providers.fix_raw.encode("utf-8")).hexdigest(),
                "reading_digest": hashlib.sha256(
                    providers.reading["raw_text"].encode("utf-8")
                ).hexdigest(),
                "digest_format": "SHA-256 of UTF-8 raw_text",
                "fix_provider": fix_provider,
                "fix_model": fix_model,
            },
            "checks": [
                "missing key opens and focuses field",
                "invalid key retained for retry",
                "key cleared after success",
                "no key in response or browser storage",
                "typed-key live paste",
                "env-key live paste",
                "100 scenarios",
                "Read by on map and results",
                "both providers failed on read and fixes",
                "503 fallback on reading",
                *(["503 fallback on fixes"] if fix_provider == "groq" else []),
                "checker facts survive AI failure",
                "successful suggestions cached",
                *(["one extra attempt when none worked"] if not fix_record else []),
                "phone layout",
                "no page errors",
            ],
            "provider_calls": len(providers.calls),
            "page_errors": errors,
        }
        (screens / f"{args.prefix}-verification.json").write_text(
            json.dumps(proof, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(proof, indent=2))
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        listener.close()
        gemini_provider.generate, groq_provider.generate, credentials.dotenv_values = original
        for name, value in saved_env.items():
            if value is not None:
                os.environ[name] = value


if __name__ == "__main__":
    main_cli()
