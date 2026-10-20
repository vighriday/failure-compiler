"""Play the actual saved example through visible controls, with capture checkpoints."""

from browser_fixes import backup_driver, spare_keys, test_change
from browser_review import review_example
from playwright.sync_api import expect

VAN_EARLY = "volunteer_leaves_early__person-anita+vehicle_returns_late__vehicle-van"
VAN_ABSENT = "volunteer_absent__person-anita+vehicle_returns_late__vehicle-van"
TRUCK_RAVI = "volunteer_absent__person-ravi+supply_delivery_late__delivery-supply-truck-drops"
JOEL = "volunteer_absent__person-joel"


def play_story(page, base, checkpoint=lambda stage, page: None):
    page.goto(base)
    page.evaluate("document.fonts.ready.then(() => true)")
    checkpoint("hero", page)
    page.get_by_role("tab", name="Start", exact=True).click()
    page.get_by_role("button", name="Load the example plan", exact=True).click()
    page.get_by_role("button", name="Read plan", exact=True).click()
    review_example(page)
    checkpoint("map", page)
    page.get_by_role("button", name="Confirm plan", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("84 survived", timeout=60000)
    checkpoint("grid", page)
    page.locator(f'[data-scenario="{VAN_EARLY}"]').click()
    expect(page.locator('.fix-card[data-origin="ai"]')).to_have_count(3, timeout=60000)
    expect(page.locator(".turned-down-card")).to_have_count(3)
    checkpoint("broken", page)
    page.locator(f'[data-scenario="{VAN_ABSENT}"]').click()
    card = page.locator('[data-fix-id="fix-2"]')
    expect(card).to_contain_text("Add an extra loader (Sam)", timeout=60000)
    checkpoint("before-sam", page)
    card.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("86 survived", timeout=60000)
    checkpoint("after-sam", page)
    page.locator(f'[data-scenario="{JOEL}"]').click()
    expect(page.locator('[data-fix-id="fix-1"]')).to_contain_text(
        "Joel absent + Ravi absent", timeout=60000
    )
    spare_keys(page)
    own = test_change(page)
    checkpoint("builder", page)
    own.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("99 survived", timeout=60000)
    page.locator(f'[data-scenario="{TRUCK_RAVI}"]').click()
    expect(page.get_by_role("region", name="Test your own change")).to_be_visible(timeout=60000)
    backup_driver(page)
    own = test_change(page)
    own.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("100 survived", timeout=60000)
    checkpoint("all-survived", page)
    page.get_by_role("button", name="See report", exact=True).first.click()
    expect(page.locator(".report-after")).to_contain_text(
        "All 100 tested scenarios survive.", timeout=30000
    )
    expect(page.locator(".report-accepted-fix")).to_have_count(3)
    checkpoint("report", page)
