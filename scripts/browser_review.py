"""Shared visible-control steps for the saved example's browser verification."""

from playwright.sync_api import expect


def updated(page):
    return page.expect_response(lambda response: response.url.endswith("/api/update-map"))


def review_saved_plan(page, corrections, *, verify_undo=False):
    for action in corrections:
        if action["action"] == "answer" and action["question_id"].endswith("-identity"):
            card = page.locator(f'[data-question-id="{action["question_id"]}"]')

            def identify():
                card.get_by_role("button", name="Same place as another listing", exact=True).click()
                card.get_by_label("Same place as", exact=True).select_option(
                    action["value"]["place_id"]
                )
                with updated(page):
                    card.get_by_role("button", name="Use this place", exact=True).click()
                expect(card).to_contain_text("is the same place as")

            original_rows = page.locator(".reading-row").count()
            identify()
            expect(page.locator(".reading-row")).to_have_count(original_rows - 2)
            if verify_undo:
                with updated(page):
                    card.get_by_role("button", name="Change", exact=True).click()
                expect(page.locator(".reading-row")).to_have_count(original_rows)
                identify()
            continue
        if action["action"] != "correct" or action["field"] != "loader_ids":
            raise AssertionError(f"This UI proof needs an explicit control for {action}")
        row = page.locator(f'[data-item-id="{action["item_id"]}"]')
        opener = row.get_by_role("button", name="Correct", exact=True)
        (opener if opener.count() else row.get_by_role("button", name="Answer", exact=True)).click()
        for position, person_id in enumerate(action["value"]):
            label = f"Move {person_id} earlier in loader_ids"
            choice = row.locator(".choice-row").filter(
                has=page.get_by_role("button", name=label, exact=True)
            )
            while True:
                current = int(choice.locator("span").inner_text().split(".", 1)[0]) - 1
                if current == position:
                    break
                with updated(page):
                    choice.get_by_role("button", name=label, exact=True).click()
                expect(choice.locator("span")).to_contain_text(f"{current}. ")
        expect(row.locator(".status-chip")).to_have_text("corrected by you")
    with updated(page):
        page.get_by_role("button", name="Confirm everything that isn’t a guess", exact=True).click()
    guessed = page.locator(".reading-row").filter(has=page.locator(".status-guessed"))
    while guessed.count():
        row = guessed.first
        row.get_by_role("button", name="Answer", exact=True).click()
        with updated(page):
            row.get_by_role("button", name="Keep this guess", exact=True).click()
    pending = page.locator(".row-confirm")
    while pending.count():
        previous_count = pending.count()
        with updated(page):
            pending.first.click()
        expect(pending).to_have_count(previous_count - 1)
    questions = page.get_by_role("button", name="Use the reviewed details", exact=True)
    while questions.count():
        previous_count = questions.count()
        with updated(page):
            questions.first.click()
        expect(questions).to_have_count(previous_count - 1)
    expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_enabled()
