"""Exercise server-owned review, current facts, and both post-run editing paths."""

import os
import re
from pathlib import Path

from browser_review import review_example
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("FAILURE_COMPILER_URL", "http://127.0.0.1:8011")
SCREENS = Path(__file__).resolve().parents[1] / "devpost/screens"
CASES = [
    (
        "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van",
        "sam-route-c-loader",
        "86 survived",
    ),
    (
        "volunteer_absent__person-ravi+supply_delivery_late__delivery-supply-truck",
        "sam-route-a-driver",
        "87 survived",
    ),
    ("volunteer_absent__person-joel", "maya-sam-spare-keys", "100 survived"),
]


def main():
    SCREENS.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/#start")
        page.get_by_role("button", name="Load the example plan", exact=True).click()
        page.get_by_role("button", name="Read plan", exact=True).click()
        review_example(page)
        page.get_by_role("button", name="Confirm plan", exact=True).click()
        expect(page.locator(".crash-count")).to_contain_text("84 survived", timeout=60000)
        expect(page.locator(".result-cell")).to_have_count(100)
        for scenario, fix_id, count in CASES:
            page.locator(f'[data-scenario="{scenario}"]').click()
            card = page.locator(f'[data-fix-id="{fix_id}"]')
            expect(card).to_be_visible(timeout=60000)
            card.get_by_role("button", name="Accept fix", exact=True).click()
            expect(page.locator(".crash-count")).to_contain_text(count, timeout=60000)

        # Top Read tab must reopen a usable review, just as the Plan map button does.
        page.get_by_role("tab", name="Read", exact=True).click()
        expect(page.locator('[data-item-id="joel-key"]')).to_contain_text(
            "Joel, Maya and Sam hold loading-area keys."
        )
        for number in (1, 2, 3):
            expect(page.get_by_text(f"changed by Fix {number}", exact=True).first).to_be_visible()
        expect(page.locator(".job-checks")).to_contain_text(
            "Route A · Car · Ravi, backups Maya and Joel and Sam"
        )
        expect(page.locator('[data-item-id="route-c"]')).to_contain_text(
            "Loading cover: Anita, Maya, Joel and Sam"
        )
        page.screenshot(path=str(SCREENS / "hardening-current-facts.png"), full_page=True)
        van = page.locator('[data-item-id="van"]')
        van.get_by_role("button", name="Correct", exact=True).click()
        van.get_by_label(re.compile("Correction for (The )?[Vv]an")).fill("09:35")
        expect(page.locator(".outdated-notice")).to_contain_text("Out of date")
        expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_disabled()
        pending = page.get_by_role("button", name="Confirm", exact=True)
        while pending.count():
            with page.expect_response(lambda response: response.url.endswith("/api/update-map")):
                pending.first.click()
        expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_enabled()
        page.screenshot(path=str(SCREENS / "hardening-read-tab-reconfirm.png"), full_page=True)
        page.get_by_role("button", name="Confirm plan", exact=True).click()
        expect(page.locator(".result-cell")).to_have_count(100, timeout=60000)
        expect(page.locator(".run-progress")).to_contain_text("100 / 100", timeout=60000)

        # The other route back also invalidates the grid on a real checker-input edit.
        page.get_by_role("button", name=re.compile("Plan map")).click()
        page.get_by_role("combobox", name="Vehicle returns late size", exact=True).select_option(
            "45"
        )
        expect(page.locator(".outdated-notice")).to_contain_text("Out of date")
        expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_enabled()
        page.get_by_role("tab", name="Crash test", exact=True).click()
        expect(
            page.get_by_role("heading", name="Confirm the plan before we test it.")
        ).to_be_visible()
        assert not errors, errors
        browser.close()
    print(
        "PASS: 100 locked results, 3 fixes, current facts, Read-tab and Plan-map reconfirmation; "
        "no page errors"
    )


if __name__ == "__main__":
    main()
