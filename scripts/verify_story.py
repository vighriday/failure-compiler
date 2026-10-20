"""Playwright contract for the full example story. Run with a local dev server up."""

import os
from pathlib import Path

from browser_fixes import backup_driver, spare_keys, test_change
from browser_review import review_example
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("FAILURE_COMPILER_URL", "http://127.0.0.1:5173")
SCREENS = ROOT / "devpost/screens"
VAN_ANITA = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
VAN_ANITA_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"
JOEL_RAVI = "volunteer_absent__person-ravi+volunteer_absent__person-joel"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supply-truck"


def main() -> None:
    SCREENS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def screenshot(name):
            page.evaluate("window.scrollTo(0, 0)")
            page.mouse.move(1400, 100)
            page.screenshot(path=str(SCREENS / name), full_page=True)

        def states():
            return page.locator(".result-cell").evaluate_all(
                "cells => Object.fromEntries(cells.map(c => [c.dataset.scenario, c.dataset.state]))"
            )

        def card(fix_id):
            return page.locator(f'[data-fix-id="{fix_id}"]')

        def accept(fix_id):
            with page.expect_response(
                lambda response: response.url.endswith("/api/apply-fix")
            ) as response:
                card(fix_id).get_by_role("button", name="Accept fix", exact=True).click()
            assert response.value.status == 200
            return response.value.json()

        page.goto(f"{BASE_URL}/#start")
        page.get_by_role("button", name="Load the example plan", exact=True).click()
        page.get_by_role("button", name="Read plan").click()
        review_example(page)
        # Adding loading cover preserves the saved reading's display order.
        route = page.locator('[data-item-id="route-c"]')
        route.get_by_role("button", name="Correct", exact=True).click()
        loader_picker = route.get_by_label("Loaders for route-c", exact=True)
        expect(loader_picker).to_be_enabled()
        with page.expect_response(lambda response: response.url.endswith("/api/update-map")):
            loader_picker.focus()
            loader_picker.press("ArrowDown")
        expect(route).to_contain_text("Loading cover: Joel, Anita, Maya and Ravi")
        with page.expect_response(lambda response: response.url.endswith("/api/update-map")):
            route.get_by_role(
                "button", name="Remove person-ravi from loader_ids", exact=True
            ).click()
        expect(
            route.get_by_role("button", name="Remove person-ravi from loader_ids", exact=True)
        ).to_have_count(0)
        expect(route).to_contain_text("Loading cover: Joel, Anita and Maya")
        page.reload()
        page.get_by_role("tab", name="Start", exact=True).click()
        page.get_by_role("button", name="Load the example plan", exact=True).click()
        page.get_by_role("button", name="Read plan").click()
        review_example(page)
        page.get_by_role("button", name="Confirm plan").click()
        page.wait_for_function(
            "document.querySelectorAll('.result-cell').length > 0"
            " && document.querySelectorAll('.result-cell').length < 100"
        )
        expect(page.locator(".crash-count")).to_have_text(
            "100 tests: 1 single weak spot, 3 hidden pairs,"
            " 12 already broken by the weak spot, 84 survived.",
            timeout=30000,
        )
        expect(page.locator(".result-cell")).to_have_count(100)
        expect(page.locator(".result-cross")).to_have_count(4)
        screenshot("slice5-filled-grid.png")

        # Both Anita cases are real, and another cross stays clickable with the panel open.
        page.locator(f'[data-scenario="{VAN_ANITA}"]').click()
        expect(card("fix-2-add-driver-ravi-to-c")).to_be_visible(timeout=60000)
        expect(page.locator('.fix-card[data-origin="ai"]')).to_have_count(3)
        expect(page.locator(".fix-card.turned-down-card")).to_have_count(3)
        expect(page.locator(".ai-sentence")).to_contain_text(
            "Suggested by Groq / openai/gpt-oss-120b (fallback: Gemini unavailable)"
        )
        expect(page.get_by_text("None of these suggestions worked", exact=True)).to_be_visible()
        expect(
            page.get_by_role("button", name="Ask for new suggestions", exact=True)
        ).to_have_count(0)
        expect(page.locator(".checker-facts")).to_contain_text("Van back 10:45. Loading team gone.")
        expect(page.locator(".single-proof")).to_contain_text("Each alone: survives")
        assert page.locator(".axis-column span").last.evaluate(
            "el => el.getBoundingClientRect().right"
            " <= el.closest('.triangle-scroll').getBoundingClientRect().right"
        ), "Last column label is clipped"
        screenshot("slice6-van-anita-three-turned-down.png")

        maya = card("fix-2-add-driver-ravi-to-c")
        expect(maya).to_contain_text("Turned down")
        expect(maya).to_contain_text("fixes 0")
        expect(maya.get_by_role("button", name="Accept fix")).to_have_count(0)
        before = states()
        maya.get_by_role("button", name="Preview", exact=True).click()
        expect(page.locator(".preview-banner")).to_contain_text("TURNED DOWN")
        assert states() == before
        screenshot("slice5-maya-turned-down-preview.png")
        page.get_by_role("button", name="Cancel preview", exact=True).click()
        assert states() == before
        page.locator(f'[data-scenario="{VAN_ANITA_ABSENT}"]').click()
        sam = card("fix-2")
        expect(sam).to_contain_text("Add an extra loader (Sam) to Route C", timeout=60000)
        expect(sam).to_contain_text("fixes 2 · still broken 2 · new crosses 0")
        screenshot("slice6-sam-card-eligible.png")
        first = accept("fix-2")
        expect(page.locator(".crash-count")).to_contain_text("86 survived", timeout=30000)
        expect(page.locator(".case-resolved")).to_contain_text("Now survives.")
        expect(page.locator(".result-cross")).to_have_count(2)
        assert states()[VAN_ANITA] == states()[VAN_ANITA_ABSENT] == "tick"
        expect(page.locator(".accepted-changes")).to_contain_text("Fix 1 (AI)")
        screenshot("slice6-sam-card-accepted.png")
        expect(page.locator(".accepted-fix-card")).to_contain_text("Add an extra loader (Sam)")

        page.locator('[data-scenario="volunteer_absent__person-joel"]').click()
        expect(card("fix-1")).to_be_visible(timeout=60000)
        expect(page.locator(".human-cost")).to_have_text(
            "Routes A, B, C: 30 households not delivered. Nobody can open the loading area"
        )
        one_key = card("fix-1")
        expect(one_key).to_contain_text("Turned down")
        expect(one_key).to_contain_text("Joel absent + Ravi absent")
        expect(one_key.get_by_role("button", name="Accept fix")).to_have_count(0)
        before = states()
        assert before[JOEL_RAVI] == "dim"
        one_key.get_by_role("button", name="Preview", exact=True).click()
        expect(page.locator(".new-cross-cell")).to_have_count(1)
        expect(page.locator(f'[data-scenario="{JOEL_RAVI}"]')).to_have_attribute(
            "data-state", "cross"
        )
        expect(page.locator(".crash-count")).to_contain_text("98 survived")
        screenshot("slice5-one-key-new-cross-preview.png")
        page.get_by_role("button", name="Cancel preview", exact=True).click()
        assert states() == before
        builder = spare_keys(page)
        # The three-operation limit and removal are exercised through visible controls.
        builder.get_by_role("button", name="Add another operation", exact=True).click()
        expect(
            builder.get_by_role("button", name="Add another operation", exact=True)
        ).to_have_count(0)
        builder.get_by_role("button", name="Remove change 3", exact=True).click()
        screenshot("slice6-builder-spare-keys-filled.png")
        own = test_change(page)
        expect(own).to_contain_text("fixes 1 · still broken 1 · new crosses 0")
        second = accept(own.get_attribute("data-fix-id"))
        expect(page.locator(".crash-count")).to_contain_text("99 survived", timeout=30000)
        expect(page.locator(".accepted-changes")).to_contain_text("Fix 2 (yours)")
        page.get_by_role("button", name="Next broken case (1 left)", exact=True).click()
        expect(page.locator(".suggestion-loading")).to_have_count(0, timeout=60000)
        expect(page.locator(".human-cost")).to_have_text("Route A: 10 households not delivered")
        backup_driver(page)
        own = test_change(page)
        expect(own).to_contain_text("fixes 1 · still broken 0 · new crosses 0")
        final = accept(own.get_attribute("data-fix-id"))
        expect(page.locator(".case-panel")).to_contain_text(
            "All 100 tested scenarios survive.", timeout=30000
        )
        expect(page.locator(".result-tick")).to_have_count(100)
        expect(page.locator(".result-cross, .result-dim, .result-qmark")).to_have_count(0)
        expect(page.locator(".accepted-changes")).to_contain_text("Fix 3 (yours)")
        expect(page.locator(".accepted-fix-card")).to_contain_text("Sam backs up Route A.")
        screenshot("slice6-all-survived.png")
        chain = final["plan_map"]["fix_history"]
        assert len(chain) == 3
        assert chain[0]["to_fingerprint"] == first["fingerprint"]
        assert chain[1]["from_fingerprint"] == first["fingerprint"]
        assert chain[1]["to_fingerprint"] == second["fingerprint"]
        assert chain[2]["from_fingerprint"] == second["fingerprint"]
        for button in page.get_by_role("button", name="See report", exact=True).all():
            expect(button).to_be_disabled()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        too_small = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(el =>
            [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) &&
            el.getBoundingClientRect().width && parseFloat(getComputedStyle(el).fontSize) < 12
        ).map(el => el.textContent.slice(0, 80))""")
        assert not too_small, too_small
        page.get_by_role("button", name="Plan map", exact=False).click()
        expect(page.get_by_text("changed by Fix 1", exact=True).first).to_be_visible()
        expect(page.get_by_text("changed by Fix 2", exact=True).first).to_be_visible()
        expect(page.get_by_text("changed by Fix 3", exact=True).first).to_be_visible()
        expect(page.locator(".outdated-notice")).to_have_count(0)
        page.get_by_role("combobox", name="Vehicle returns late size", exact=True).select_option(
            "45"
        )
        expect(page.locator(".outdated-notice")).to_contain_text("Out of date: re-run")

        reduced = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        reduced.on("pageerror", lambda error: errors.append(str(error)))
        reduced.goto(f"{BASE_URL}/#start")
        reduced.get_by_role("button", name="Load the example plan", exact=True).click()
        reduced.get_by_role("button", name="Read plan").click()
        review_example(reduced)
        reduced.evaluate("""() => {
            window.cellCounts = [];
            new MutationObserver(() => window.cellCounts.push(
                document.querySelectorAll('.result-cell').length))
                .observe(document.body, {childList: true, subtree: true});
        }""")
        reduced.get_by_role("button", name="Confirm plan").click()
        expect(reduced.locator(".result-cell")).to_have_count(100, timeout=30000)
        assert reduced.evaluate("window.cellCounts.every(n => n === 0 || n === 100)")
        assert (
            reduced.locator(".result-cell").first.evaluate(
                "el => getComputedStyle(el).animationName"
            )
            == "none"
        )
        assert not errors, errors
        print(
            "PASS: full example story; all 100 survived; 3 linked fingerprints;"
            " real AI cards, constrained builder, full-page screenshots;"
            " reduced motion; no page errors."
        )
        browser.close()


if __name__ == "__main__":
    main()
