"""Run the entire example by keyboard and audit each screen with axe-core."""

import argparse
import json
from pathlib import Path

from browser_story import JOEL, TRUCK_RAVI, VAN_ABSENT, VAN_EARLY, play_story
from local_preview import local_preview
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "node_modules/axe-core/axe.min.js"


class Keyboard:
    def __init__(self, page):
        self.page, self.tab_presses, self.actions = page, 0, []

    def reach(self, locator):
        expect(locator).to_be_enabled(timeout=60000)
        for _ in range(700):
            if locator.evaluate("el => el === document.activeElement"):
                style = locator.evaluate(
                    "el => { const s = getComputedStyle(el); "
                    "return {width: parseFloat(s.outlineWidth), style: s.outlineStyle}; }"
                )
                assert style["width"] >= 1 and style["style"] != "none", style
                return
            self.page.keyboard.press("Tab")
            self.tab_presses += 1
        raise AssertionError(f"Keyboard could not reach {locator}")

    def activate(self, locator):
        self.reach(locator)
        self.actions.append(locator.inner_text()[:100])
        self.page.keyboard.press("Enter")

    def select(self, locator, value):
        self.reach(locator)
        index = locator.evaluate(
            "(el, value) => [...el.options].findIndex(option => option.value === value)", value
        )
        assert index >= 0
        self.page.keyboard.press("Home")
        for _ in range(index):
            self.page.keyboard.press("ArrowDown")
        expect(locator).to_have_value(value)
        self.actions.append(f"Select {value}")

    def open_tab(self, name):
        self.reach(self.page.get_by_role("tab", selected=True))
        target = self.page.get_by_role("tab", name=name, exact=True)
        for _ in range(7):
            if target.get_attribute("aria-selected") == "true":
                return
            self.page.keyboard.press("ArrowRight")
        raise AssertionError(f"Cannot open {name} with keyboard arrows")


def keyboard_review(page, keys):
    expect(page.locator(".reading-row")).to_have_count(32, timeout=60000)
    identity = page.locator('[data-question-id$="-identity"]')
    keys.activate(identity.get_by_role("button", name="Same place as another listing", exact=True))
    keys.select(identity.get_by_label("Same place as", exact=True), "place-loading-bay")
    keys.activate(identity.get_by_role("button", name="Use this place", exact=True))
    expect(page.locator(".reading-row")).to_have_count(30)
    keys.activate(
        page.get_by_role("button", name="Confirm everything that isn’t a guess", exact=True)
    )
    guessed = page.locator(".reading-row").filter(has=page.locator(".status-guessed"))
    while guessed.count():
        item_id = guessed.first.get_attribute("data-item-id")
        row = page.locator(f'[data-item-id="{item_id}"]')
        keys.activate(row.get_by_role("button", name="Answer", exact=True))
        keys.activate(row.get_by_role("button", name="Keep this guess", exact=True))
        expect(row.locator(".status-guessed")).to_have_count(0)
    pending = page.locator(".row-confirm")
    while pending.count():
        count = pending.count()
        keys.activate(pending.first)
        expect(pending).to_have_count(count - 1)
    questions = page.get_by_role("button", name="Use the reviewed details", exact=True)
    while questions.count():
        count = questions.count()
        keys.activate(questions.first)
        expect(questions).to_have_count(count - 1)


def audit(page, stage):
    page.add_script_tag(path=str(AXE))
    findings = page.evaluate((ROOT / "scripts/accessibility_audit.js").read_text(encoding="utf-8"))
    findings["stage"] = stage
    return findings


def keyboard_story(page, base, results):
    keys = Keyboard(page)
    page.goto(base + "/#start")
    results.append(audit(page, "paste"))
    keys.activate(page.get_by_role("button", name="Load the example plan", exact=True))
    keys.activate(page.get_by_role("button", name="Read plan", exact=True))
    keyboard_review(page, keys)
    results.append(audit(page, "reviewed-map"))
    keys.activate(page.get_by_role("button", name="Confirm plan", exact=True))
    expect(page.locator(".crash-count")).to_contain_text("84 survived", timeout=60000)
    results.append(audit(page, "grid"))
    keys.activate(page.locator(f'[data-scenario="{VAN_EARLY}"]'))
    expect(page.locator(".turned-down-card")).to_have_count(3, timeout=60000)
    results.append(audit(page, "three-turned-down"))
    card = page.locator('[data-fix-id="fix-2-add-driver-ravi-to-c"]')
    keys.activate(card.get_by_role("button", name="Preview", exact=True))
    keys.activate(page.get_by_role("button", name="Cancel preview", exact=True))
    keys.activate(page.locator(f'[data-scenario="{VAN_ABSENT}"]'))
    sam = page.locator('[data-fix-id="fix-2"]')
    expect(sam).to_contain_text("Add an extra loader (Sam)", timeout=60000)
    keys.activate(sam.get_by_role("button", name="Accept fix", exact=True))
    expect(page.locator(".crash-count")).to_contain_text("86 survived", timeout=60000)
    keys.activate(page.get_by_role("button", name="Before", exact=True))
    expect(page.locator(".result-cross")).to_have_count(4)
    keys.activate(page.get_by_role("button", name="After", exact=True))
    keys.activate(page.locator(f'[data-scenario="{JOEL}"]'))
    builder = page.get_by_role("region", name="Test your own change")
    expect(builder).to_be_visible(timeout=60000)
    for index, person in enumerate(["person-maya", "person-sam"], 1):
        if index == 2:
            keys.activate(builder.get_by_role("button", name="Add another operation", exact=True))
        keys.select(builder.get_by_label(f"Operation {index}", exact=True), "give_spare_key")
        keys.select(builder.get_by_label(f"Person {index}", exact=True), person)
    keys.activate(builder.get_by_role("button", name="Test this change", exact=True))
    own = page.locator('.fix-card[data-origin="yours"]')
    expect(own).to_contain_text("fixes 1", timeout=60000)
    results.append(audit(page, "scored-builder"))
    keys.activate(own.get_by_role("button", name="Preview", exact=True))
    keys.activate(page.get_by_role("button", name="Cancel preview", exact=True))
    keys.activate(own.get_by_role("button", name="Accept fix", exact=True))
    expect(page.locator(".crash-count")).to_contain_text("99 survived", timeout=60000)
    keys.activate(page.locator(f'[data-scenario="{TRUCK_RAVI}"]'))
    expect(builder).to_be_visible(timeout=60000)
    keys.select(builder.get_by_label("Route 1", exact=True), "route-a")
    keys.select(builder.get_by_label("Person 1", exact=True), "person-sam")
    keys.activate(builder.get_by_role("button", name="Test this change", exact=True))
    expect(own).to_contain_text("Sam backs up Route A", timeout=60000)
    keys.activate(own.get_by_role("button", name="Accept fix", exact=True))
    expect(page.locator(".result-tick")).to_have_count(100, timeout=60000)
    keys.activate(page.get_by_role("button", name="See report", exact=True).first)
    expect(page.locator(".report-after")).to_contain_text("All 100 tested scenarios survive.")
    results.append(audit(page, "report"))
    page.evaluate("() => { window.printCalls = 0; window.print = () => window.printCalls++; }")
    keys.activate(page.get_by_role("button", name="Print or save as PDF", exact=True))
    page.wait_for_function("window.printCalls === 1")
    keys.activate(page.get_by_role("button", name="Back to results", exact=True))
    expect(page.locator(".result-tick")).to_have_count(100)
    return {"tab_presses": keys.tab_presses, "actions": keys.actions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()
    results, errors, keyboard = [], [], None
    with local_preview() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))
        if args.scan_only:
            play_story(page, base, lambda stage, page: results.append(audit(page, stage)))
        else:
            keyboard = keyboard_story(page, base, results)
            preview = browser.new_page(
                viewport={"width": 1500, "height": 1000}, reduced_motion="reduce"
            )
            preview.on("pageerror", lambda error: errors.append(str(error)))
            preview.goto(base)
            navigation = Keyboard(preview)
            results.append(audit(preview, "overview"))
            for name in ("Plan", "Read", "Trust"):
                navigation.open_tab(name)
                results.append(audit(preview, f"preview-{name.lower()}"))
            preview.close()
        proof = {
            "keyboard": keyboard,
            "scans": results,
            "page_errors": errors,
            "reduced_motion": True,
        }
        (ROOT / "devpost/screens/accessibility-proof.json").write_text(
            json.dumps(proof, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(proof, indent=2))
        assert not errors and all(
            not row["violations"] and not row["small"] and not row["manual_contrast"]["failures"]
            for row in results
        )
        browser.close()


if __name__ == "__main__":
    main()
