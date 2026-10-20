"""Use only the coordinator's visible fixed-choice builder controls."""

from playwright.sync_api import expect


def spare_keys(page, people=("person-maya", "person-sam")):
    builder = page.get_by_role("region", name="Test your own change")
    for index, person in enumerate(people, 1):
        if index > 1:
            builder.get_by_role("button", name="Add another operation", exact=True).click()
        builder.get_by_label(f"Operation {index}", exact=True).select_option("give_spare_key")
        builder.get_by_label(f"Person {index}", exact=True).select_option(person)
    return builder


def backup_driver(page, route="route-a", person="person-sam"):
    builder = page.get_by_role("region", name="Test your own change")
    builder.get_by_label("Operation 1", exact=True).select_option("add_driver")
    builder.get_by_label("Route 1", exact=True).select_option(route)
    builder.get_by_label("Person 1", exact=True).select_option(person)
    return builder


def test_change(page):
    with page.expect_response(
        lambda response: response.url.endswith("/api/test-change"), timeout=60000
    ) as response:
        page.get_by_role("button", name="Test this change", exact=True).click()
    assert response.value.status == 200, response.value.text()
    fix = response.value.json()
    assert fix["gate_status"] == "passed" and fix["origin"] == "yours"
    assert len(fix["scenario_results"]) == 100
    card = page.locator(f'[data-fix-id="{fix["id"]}"]')
    expect(card.get_by_role("heading", name="Your change", exact=True)).to_be_visible()
    return card
