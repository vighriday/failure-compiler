"""Capture the real example journey for the submission asset pack."""

import json
import os
import re
from pathlib import Path

from browser_fixes import backup_driver, spare_keys, test_change
from browser_review import review_example
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/submission/screenshots"
BASE = os.environ.get("FAILURE_COMPILER_URL", "http://127.0.0.1:5173")
VAN_ANITA = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
VAN_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"
JOEL_RAVI = "volunteer_absent__person-ravi+volunteer_absent__person-joel"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    captures = []
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def capture(name, *, full_page=False, target=None):
            page.mouse.move(1430, 100)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            if target is None:
                page.screenshot(path=str(OUT / name), full_page=full_page)
            else:
                target.screenshot(path=str(OUT / name))
            captures.append(name)

        page.goto(BASE)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(3000)
        capture("01-overview.png")
        page.get_by_role("tab", name="Start", exact=True).click()
        page.get_by_role("button", name="Load the example plan", exact=True).click()
        expect(page.get_by_role("button", name="Read plan", exact=True)).to_be_enabled()
        capture("02-paste-plan.png")

        page.get_by_role("button", name="Read plan", exact=True).click()
        expect(page.locator(".reading-row")).to_have_count(32)
        page.locator('[data-item-id="joel-key"]').hover()
        expect(page.locator("#plan-L3")).to_have_class(re.compile("line-active"))
        # Keep the real source highlight visible; no text or status is altered for the image.
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(OUT / "03-plan-map.png"))
        captures.append("03-plan-map.png")
        capture("03-plan-map-full.png", full_page=True)

        review_example(page)
        page.get_by_role("button", name="Confirm plan", exact=True).click()
        expect(page.locator(".result-cell")).to_have_count(100, timeout=30000)
        expect(page.locator(".result-cross")).to_have_count(4)
        expect(page.locator(".crash-count")).to_contain_text("84 survived")
        capture("04-live-grid.png", full_page=True)

        page.locator(f'[data-scenario="{VAN_ANITA}"]').click()
        maya = page.locator('[data-fix-id="fix-2-add-driver-ravi-to-c"]')
        expect(maya).to_be_visible(timeout=30000)
        expect(page.locator(".human-cost")).to_have_text("Route C: 8 households not delivered")
        capture("05-broken-case.png", full_page=True)
        capture("06-fix-turned-down.png", target=page.locator(".case-panel"))

        page.locator(f'[data-scenario="{VAN_ABSENT}"]').click()
        sam = page.locator('[data-fix-id="fix-2"]')
        expect(sam).to_contain_text("Add an extra loader (Sam) to Route C", timeout=60000)
        sam.get_by_role("button", name="Accept fix", exact=True).click()
        expect(page.locator(".crash-count")).to_contain_text("86 survived", timeout=30000)
        page.locator('[data-scenario="volunteer_absent__person-joel"]').click()
        one_key = page.locator('[data-fix-id="fix-1"]')
        expect(one_key).to_be_visible(timeout=30000)
        one_key.get_by_role("button", name="Preview", exact=True).click()
        expect(page.locator(f'[data-scenario="{JOEL_RAVI}"]')).to_have_attribute(
            "data-state", "cross"
        )
        capture("07-one-key-new-pair.png", full_page=True)
        page.get_by_role("button", name="Cancel preview", exact=True).click()
        spare_keys(page)
        capture("07b-your-change-filled.png", full_page=True)
        own = test_change(page)
        own.get_by_role("button", name="Accept fix", exact=True).click()
        expect(page.locator(".crash-count")).to_contain_text("99 survived", timeout=30000)
        page.get_by_role("button", name="Next broken case (1 left)", exact=True).click()
        expect(page.get_by_role("region", name="Test your own change")).to_be_visible(timeout=60000)
        backup_driver(page)
        own = test_change(page)
        own.get_by_role("button", name="Accept fix", exact=True).click()
        expect(page.locator(".result-tick")).to_have_count(100, timeout=30000)
        expect(page.locator(".case-panel")).to_contain_text("All 100 tested scenarios survive.")
        capture("08-all-survived.png", full_page=True)
        assert not errors, errors
        browser.close()

    (OUT.parent / "captures.json").write_text(
        json.dumps(
            {"viewport": [1440, 900], "source": BASE, "files": captures, "page_errors": errors},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {len(captures)} real app captures to {OUT}")


if __name__ == "__main__":
    main()
