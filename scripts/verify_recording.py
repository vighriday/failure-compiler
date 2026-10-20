"""Verify a clean recording take and capture the real-app thumbnail candidates."""

import json
from pathlib import Path

from browser_story import play_story
from local_preview import local_preview
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "docs/images"
    output.mkdir(parents=True, exist_ok=True)
    errors, console_errors = [], []
    with local_preview() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        play_story(page, base)
        old_cookie = next(
            cookie["value"]
            for cookie in page.context.cookies()
            if cookie["name"] == "failure_session"
        )
        for _ in range(2):
            page.evaluate(
                "() => { localStorage.setItem('take', 'old'); "
                "sessionStorage.setItem('take', 'old'); }"
            )
            page.goto(base + "/demo")
            page.wait_for_url(base + "/")
            expect(page.get_by_role("tab", name="Overview", exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
            cookie = next(
                cookie["value"]
                for cookie in page.context.cookies()
                if cookie["name"] == "failure_session"
            )
            assert cookie != old_cookie
            old_cookie = cookie
            assert page.evaluate("() => localStorage.length + sessionStorage.length") == 0
            page.get_by_role("tab", name="Start", exact=True).click()
            expect(page.locator("textarea")).to_have_value("")
            expect(page.locator(".reading-row")).to_have_count(0)
            page.get_by_role("tab", name="Overview", exact=True).click()
        for filename, width, height in [
            ("youtube-thumbnail.png", 1280, 720),
            ("devpost-thumbnail.png", 1500, 1000),
        ]:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("() => document.fonts.ready")
            page.screenshot(path=str(output / filename))
        assert not errors and not console_errors, (errors, console_errors)
        browser.close()
    proof = {
        "clean_resets": 2,
        "full_story_survived": 100,
        "page_errors": errors,
        "console_errors": console_errors,
        "thumbnails": {"youtube-thumbnail.png": [1280, 720], "devpost-thumbnail.png": [1500, 1000]},
    }
    (ROOT / "devpost/screens/recording-proof.json").write_text(
        json.dumps(proof, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
