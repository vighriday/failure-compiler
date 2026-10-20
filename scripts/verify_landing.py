"""Exercise the v2 design and its connection to the confirmed-map workflow."""

import json
import os
import re
from collections import Counter
from pathlib import Path

from browser_review import confirm_pending, review_example
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("FAILURE_COMPILER_URL", "http://127.0.0.1:5173")
ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "devpost/screens"
VAN_ANITA = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"


def main():
    SCREENS.mkdir(parents=True, exist_ok=True)
    errors = []
    console_errors = []
    controlled_failures = []
    checked = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        def new_page(width=1440, height=900, reduced=False):
            page = browser.new_page(
                viewport={"width": width, "height": height},
                reduced_motion="reduce" if reduced else "no-preference",
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append((message.text, message.location.get("url")))
                    if message.type == "error"
                    else None
                ),
            )
            page.goto(f"{BASE}/")
            page.evaluate("document.fonts.ready")
            return page

        def tab(page, name):
            button = page.get_by_role("tab", name=name, exact=True)
            button.click()
            expect(button).to_have_attribute("aria-selected", "true")
            page.wait_for_timeout(600)

        def screenshot(page, name):
            page.evaluate("window.scrollTo(0, 0)")
            page.mouse.move(page.viewport_size["width"] - 8, 100)
            page.wait_for_timeout(150)
            page.screenshot(path=str(SCREENS / name), full_page=True)

        def no_overflow(page):
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                f"Page overflows at {page.viewport_size}, {page.url}"
            )

        def load(page):
            tab(page, "Start")
            page.get_by_role("button", name="Load the example plan", exact=True).click()
            expect(page.get_by_role("button", name="Read plan", exact=True)).to_be_enabled()

        def confirm(page):
            page.get_by_role("button", name="Read plan", exact=True).click()
            expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_disabled()
            review_example(page)
            ravi = page.locator('[data-item-id="ravi-driver"]')
            ravi.focus()
            source = ravi.locator(".source-tag").inner_text()
            expect(page.locator(f"#plan-{source}")).to_have_class(re.compile("line-active"))
            ravi.get_by_role("button", name="Correct", exact=True).click()
            page.get_by_role(
                "combobox", name="Correction for Ravi can drive.", exact=True
            ).select_option("false")
            expect(page.locator(".rule-question")).to_have_count(3)
            expect(ravi).to_contain_text("Ravi cannot drive.")
            page.get_by_role(
                "combobox", name="Correction for Ravi can drive.", exact=True
            ).select_option("true")
            expect(page.locator(".rule-question")).to_have_count(0)
            driving = page.locator('[data-item-id="route-c-driving"]')
            driving.get_by_role("button", name="Correct", exact=True).click()
            driving.get_by_role(
                "combobox", name=re.compile("Correction for Route C's drive")
            ).select_option("45")
            driving.get_by_role(
                "combobox", name=re.compile("Correction for Route C's drive")
            ).select_option("60")
            sizes = page.get_by_role("combobox", name="Vehicle returns late size", exact=True)
            sizes.select_option("45")
            sizes.select_option("30")
            confirm_pending(page)
            page.get_by_role("button", name="Confirm plan", exact=True).click()
            expect(page.locator(".result-cell")).to_have_count(100, timeout=30000)

        page = new_page()
        page.wait_for_timeout(3000)
        page.evaluate("""() => {
            window.originalWidthDescriptor = Object.getOwnPropertyDescriptor(window, 'innerWidth');
            Object.defineProperty(window, 'innerWidth', {configurable: true, value: 0});
            window.dispatchEvent(new Event('resize'));
        }""")
        page.wait_for_timeout(100)
        assert page.locator("svg").evaluate_all("""nodes => nodes.every(node =>
            ['width', 'height'].every(name => {
                const value = node.getAttribute(name);
                return value === null || !Number.isFinite(Number(value)) || Number(value) >= 0;
            }))""")
        page.evaluate("""() => {
            Object.defineProperty(window, 'innerWidth', window.originalWidthDescriptor);
            window.dispatchEvent(new Event('resize'));
        }""")
        page.wait_for_timeout(100)
        checked.append("Transient zero-width resize keeps every SVG dimension valid")
        screenshot(page, "v2-overview.png")
        primary = page.locator('[data-shard="0"]')
        before = primary.get_attribute("style")
        buttons_before = primary.locator("button").count()
        for _ in range(3):
            page.get_by_role("button", name="Break the page", exact=True).click()
            expect(page.locator("[data-shard]")).to_have_count(9)
            assert page.locator('[data-shard]:not([data-shard="0"])').evaluate_all(
                "nodes => nodes.every(n => n.inert && n.getAttribute('aria-hidden') === 'true')"
            )
            expect(page.locator("[data-shard]")).to_have_count(1, timeout=5000)
            assert primary.get_attribute("style") == before
            assert primary.locator("button").count() == buttons_before
        # Navigation during an animation must also restore the original surface.
        page.get_by_role("button", name="Break the page", exact=True).click()
        tab(page, "Plan")
        tab(page, "Overview")
        expect(page.locator("[data-shard]")).to_have_count(1)
        page.wait_for_timeout(3000)
        screenshot(page, "v2-overview-restored.png")
        checked.append("Repeated and interrupted shatter animations restore styles and controls")

        # Every supplied navigation control, not only the tab buttons.
        for name in ["Plan", "Read", "Crash test", "Trust", "Start"]:
            page.locator(".landing-root").first.locator(":scope > button").click()
            expect(page.get_by_role("tab", name=name, exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
        tab(page, "Overview")
        page.get_by_role("button", name="See what breaks", exact=True).click()
        expect(page.get_by_role("tab", name="Crash test", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        tab(page, "Plan")
        page.get_by_role("button", name="Read the plan", exact=True).click()
        expect(page.get_by_role("tab", name="Read", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        tab(page, "Overview")

        for name in ["Read", "Trust", "Start"]:
            tab(page, name)
            selected_url = page.url
            page.get_by_role("link", name="Skip to content", exact=True).focus()
            page.get_by_role("link", name="Skip to content", exact=True).click()
            assert page.url == selected_url
            expect(page.get_by_role("tab", name=name, exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
            expect(page.locator("#landing-panel")).to_be_focused()
        checked.append("Skip link preserves the selected section and moves focus to its content")
        tab(page, "Overview")

        page.get_by_role("tab", name="Overview", exact=True).focus()
        page.keyboard.press("End")
        expect(page.get_by_role("tab", name="Start", exact=True)).to_be_focused()
        page.keyboard.press("Home")
        expect(page.get_by_role("tab", name="Overview", exact=True)).to_be_focused()
        page.keyboard.press("ArrowRight")
        expect(page.get_by_role("tab", name="Plan", exact=True)).to_be_focused()
        page.keyboard.press("ArrowLeft")
        expect(page.get_by_role("tab", name="Overview", exact=True)).to_be_focused()
        page.keyboard.press("ArrowRight")
        for index in range(5):
            item = page.locator(f'[data-story-step="{index}"]')
            item.evaluate(
                "el => window.scrollTo(0, el.getBoundingClientRect().top"
                " + scrollY - innerHeight * .25)"
            )
            expect(item).to_have_css("opacity", "1")
        assert page.locator('[data-story-step="4"]').evaluate(
            "el => getComputedStyle(el).opacity === '1'"
        )
        screenshot(page, "v2-plan-scroll.png")
        checked.append("Keyboard tabs, sticky plan, five scroll steps and progress indicator")

        tab(page, "Read")
        source_row = page.get_by_text("Joel has the only loading-bay key.", exact=True).locator(
            "xpath=../.."
        )
        source_row.focus()
        expect(
            page.locator('[data-screen-label="02 Read"] [style*="box-shadow"]').nth(2)
        ).to_have_css("background-color", "rgb(233, 229, 217)")
        expect(page.get_by_role("button", name="Confirm sample", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Only his car", exact=True).click()
        page.get_by_role("button", name="Change", exact=True).click()
        page.get_by_role("button", name="The van too", exact=True).click()
        page.get_by_role("button", name="we guessed, check it", exact=True).click()
        page.get_by_role("combobox", name="Minutes", exact=True).select_option("60")
        page.get_by_role("button", name="Save", exact=True).click()
        screenshot(page, "v2-sample-reading-corrected.png")
        page.get_by_role("button", name="Confirm sample", exact=True).click()
        cells = page.locator("[data-sample-state]")
        expect(cells).to_have_count(105)
        initial = Counter(cells.evaluate_all("nodes => nodes.map(n => n.dataset.sampleState)"))
        assert initial == {"ok": 84, "cross": 1, "ring": 3, "dash": 12, "hatch": 5}, initial
        for index in range(105):
            cell = cells.nth(index)
            cell.click()
            row = int(cell.get_attribute("data-sample-row"))
            column = int(cell.get_attribute("data-sample-column"))
            expect(page.locator("[data-case]")).to_contain_text(
                f"Problem {row} on its own"
                if row == column
                else f"Problems {column} and {row} together"
            )
        cells.nth(0).focus()
        page.keyboard.press("Enter")
        expect(page.locator("[data-case]")).to_contain_text("Problem 1 on its own")
        cells.nth(2).focus()
        page.keyboard.press("Space")
        expect(page.locator("[data-case]")).to_contain_text("Problem 2 on its own")
        page.get_by_role("button", name="Run the crash test again", exact=True).click()
        for _ in range(3):
            page.get_by_role("button", name="Show this example fix", exact=True).click()
            page.wait_for_timeout(900)
        expect(
            page.get_by_text("Your plan survived all 100 tested scenarios.", exact=True)
        ).to_be_visible()
        assert page.locator('[data-sample-state="ok"], [data-sample-state="fixed"]').count() == 100
        page.get_by_role("button", name="Start over", exact=True).click()
        expect(page.locator('[data-sample-state="ring"]')).to_have_count(3)
        checked.append(
            "Sample question, constrained correction, all 105 squares, rerun,"
            " three example fixes and reset"
        )

        tab(page, "Trust")
        page.get_by_role("button", name="Replay", exact=True).click()
        page.wait_for_timeout(2700)
        screenshot(page, "v2-trust.png")
        checked.append("Trust sequence replay and all three honest outcomes")

        tab(page, "Start")
        editor = page.get_by_role("textbox", name="Your plan", exact=True)
        read = page.get_by_role("button", name="Read plan", exact=True)
        expect(read).to_be_disabled()
        editor.fill("x" * 4001)
        expect(read).to_be_disabled()
        expect(page.get_by_role("alert")).to_contain_text("4,001")
        editor.fill("\n".join(f"Line {n}" for n in range(60)))

        # Keep this visual regression offline even when the server has .env keys.
        # Provider and format-gate behavior is exercised by verify_live.py.
        def controlled_read(route):
            body = route.request.post_data_json
            if body.get("example"):
                route.continue_()
                return
            supplied = bool(body.get("api_key"))
            controlled_failures.append(route.request.url)
            route.fulfill(
                status=401,
                content_type="application/json",
                body=json.dumps(
                    {
                        "detail": "The AI key is invalid. Check it and try again."
                        if supplied
                        else "Add an AI key, or load the example plan.",
                        "error_code": "invalid_key" if supplied else "missing_key",
                    }
                ),
            )

        page.route("**/api/read-plan", controlled_read)
        editor.evaluate("el => { el.scrollTop = 120; el.dispatchEvent(new Event('scroll')); }")
        assert page.locator("[data-plan-editor]").evaluate(
            "el => el.parentElement.firstElementChild.firstElementChild.style.transform"
            " === `translateY(${-el.scrollTop}px)`"
        )
        page.get_by_role("button", name="Read plan", exact=True).click()
        expect(page.get_by_label("AI key", exact=True)).to_be_visible()
        page.get_by_label("AI key", exact=True).fill("test-key")
        read.click()
        expect(page.get_by_role("alert")).to_contain_text("The AI key is invalid")
        key_button = page.get_by_role("button", name="Use your own AI key", exact=True)
        key_button.click()
        expect(key_button).to_have_attribute("aria-expanded", "false")
        checked.append(
            "Empty and over-limit input, synchronized gutter, key disclosure,"
            " controlled key and offline error states"
        )
        page.get_by_role("button", name="Failure Compiler home", exact=True).click()
        page.get_by_role("button", name="Try the example", exact=True).click()
        expect(read).to_be_enabled()
        page.get_by_role("button", name="Failure Compiler home", exact=True).click()
        page.get_by_role("button", name="Try the example plan", exact=True).click()
        expect(read).to_be_enabled()
        screenshot(page, "v2-start-example.png")
        confirm(page)
        no_overflow(page)
        page.locator(f'[data-scenario="{VAN_ANITA}"]').click()
        expect(page.locator('.fix-card[data-origin="ai"]')).to_have_count(3, timeout=60000)
        screenshot(page, "v2-live-case.png")
        no_overflow(page)
        tab(page, "Start")
        editor.fill("The source plan changed.")
        tab(page, "Crash test")
        expect(
            page.get_by_role("heading", name="Confirm the plan before we test it.")
        ).to_be_visible()
        checked.append(
            "Both CTAs reach the real gate; repeated corrections, dependent re-confirmation,"
            " reversible answers, preset sizes, live checker, scored fixes"
            " and changed-source protection"
        )
        page.close()

        for width, height in [(768, 1024), (390, 844), (320, 844)]:
            mobile = new_page(width, height)
            for name in ["Overview", "Plan", "Read", "Crash test", "Trust", "Start"]:
                tab(mobile, name)
                no_overflow(mobile)
                screenshot(mobile, f"v2-{width}-{name.lower().replace(' ', '-')}.png")
            load(mobile)
            confirm(mobile)
            no_overflow(mobile)
            mobile.locator(f'[data-scenario="{VAN_ANITA}"]').click()
            expect(mobile.locator(".human-cost")).to_have_text(
                "Route C: 8 households not delivered", timeout=30000
            )
            no_overflow(mobile)
            if width < 520:
                timeline = mobile.get_by_role("region", name="Scrollable route timeline")
                assert timeline.evaluate("el => el.scrollWidth > el.clientWidth")
                timeline.focus()
                mobile.keyboard.press("ArrowRight")
                mobile.wait_for_timeout(200)
                assert timeline.evaluate("el => el.scrollLeft > 0")
            screenshot(mobile, f"v2-{width}-live-case.png")
            mobile.close()
        checked.append(
            "All six sections and real map, confirmation footer, grid and case panel"
            " at tablet and phone sizes"
        )

        # Every driver rule picker must recover the map when the listed driver cannot drive.
        rule_page = new_page()
        load(rule_page)
        rule_page.get_by_role("button", name="Read plan", exact=True).click()
        review_example(rule_page)
        rule_page.locator('[data-item-id="ravi-driver"]').get_by_role(
            "button", name="Correct", exact=True
        ).click()
        rule_page.get_by_role(
            "combobox", name="Correction for Ravi can drive.", exact=True
        ).select_option("false")
        expect(rule_page.locator(".rule-question")).to_have_count(3)
        for route, driver in [("A", "person-maya"), ("B", "person-sam"), ("C", "person-anita")]:
            rule_page.get_by_role(
                "combobox", name=f"Choose a driver for Route {route}", exact=True
            ).select_option(driver)
        expect(rule_page.locator(".rule-question")).to_have_count(0)
        confirm_pending(rule_page)
        rule_page.get_by_role("button", name="Confirm plan", exact=True).click()
        expect(rule_page.locator(".result-cell")).to_have_count(100, timeout=30000)
        rule_page.close()
        checked.append("All three driver rule pickers recover a valid, confirmable map")

        reduced = new_page(reduced=True)
        reduced.get_by_role("button", name="Break the page", exact=True).click()
        expect(reduced.locator("[data-shard]")).to_have_count(1)
        tab(reduced, "Trust")
        reduced.get_by_role("button", name="Replay", exact=True).click()
        assert reduced.locator('[data-screen-label="04 Trust"]').evaluate(
            "el => [...el.querySelectorAll('[style*=\"translateY\"]')]"
            ".every(n => getComputedStyle(n).opacity === '1')"
        )
        reduced.close()
        checked.append("Reduced motion shows completed states without fragment or scroll animation")
        browser.close()
    expected_console = [
        item
        for item in console_errors
        if item[1] in controlled_failures and "status of 401" in item[0]
    ]
    assert len(expected_console) == len(controlled_failures) == 2
    errors.extend(text for text, url in console_errors if (text, url) not in expected_console)
    assert not errors, dict(Counter(errors))
    report = {
        "checks": checked,
        "page_errors": errors,
        "viewports": [1440, 768, 390, 320],
        "sample_cells_clicked": 105,
        "controlled_unauthorized_responses": len(controlled_failures),
    }
    (SCREENS / "v2-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
