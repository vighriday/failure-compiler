"""Inspect a saved candidate through real UI controls without replacing example fixtures.

The candidate overrides the fixture loader only in this isolated preview process. No AI
provider is called, and no canonical fixture is written. Screenshots stay in devpost/screens.
"""

import argparse
import json
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import main as http  # noqa: E402
from server.evaluation import compare_reading  # noqa: E402
from server.models import PlanMapData  # noqa: E402
from server.reading import plan_from_record  # noqa: E402
from server.validation.models import PlanMap  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reading", type=Path)
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    record = json.loads(args.reading.read_text(encoding="utf-8"))
    plan_from_record(record)  # Format gate before opening a browser.
    audit = json.loads(args.reading.with_name("reading-audit.json").read_text(encoding="utf-8"))
    screens = ROOT / "devpost/screens"
    screens.mkdir(parents=True, exist_ok=True)
    original_fixture = http._fixture
    http._fixture = lambda path: (
        record if path == "fixtures/example-reading.json" else original_fixture(path)
    )
    # Binding first prevents accidentally connecting to or shutting down another server.
    listener = socket.socket()
    listener.bind(("127.0.0.1", args.port))
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(http.app, log_level="warning"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    errors, requests = [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            page.goto(f"http://127.0.0.1:{args.port}/#start")
            page.get_by_role("button", name="Load the example plan", exact=True).click()
            page.get_by_role("button", name="Read plan", exact=True).click()
            expect(page.locator(".placeholder-notice")).to_contain_text("saved AI reading")
            page.screenshot(path=str(screens / "read-v3-candidate-before.png"), full_page=True)
            for action in audit["scripted_corrections"]:
                if action["action"] != "correct" or action["field"] != "loader_ids":
                    raise AssertionError(f"This UI proof needs an explicit control for {action}")
                row = page.locator(f'[data-item-id="{action["item_id"]}"]')
                opener = row.get_by_role("button", name="Correct", exact=True)
                (
                    opener
                    if opener.count()
                    else row.get_by_role("button", name="Answer", exact=True)
                ).click()
                # Only reorder the existing loaders, preserving the raw entity set.
                for position, person_id in enumerate(action["value"]):
                    while True:
                        choice = row.locator(".choice-row").filter(
                            has=page.get_by_role(
                                "button", name=f"Move {person_id} earlier in loader_ids", exact=True
                            )
                        )
                        current = int(choice.locator("span").inner_text().split(".", 1)[0]) - 1
                        if current == position:
                            break
                        with page.expect_response(
                            lambda response: response.url.endswith("/api/update-map")
                        ):
                            choice.get_by_role(
                                "button", name=f"Move {person_id} earlier in loader_ids", exact=True
                            ).click()
                        expect(choice.locator("span")).to_contain_text(f"{current}. ")
                expect(row.locator(".status-chip")).to_have_text("corrected by you")
            with page.expect_response(lambda response: response.url.endswith("/api/update-map")):
                page.get_by_role(
                    "button", name="Confirm everything that isn’t a guess", exact=True
                ).click()
            guessed = page.locator(".reading-row").filter(has=page.locator(".status-guessed"))
            while guessed.count():
                row = guessed.first
                row.get_by_role("button", name="Answer", exact=True).click()
                with page.expect_response(
                    lambda response: response.url.endswith("/api/update-map")
                ):
                    row.get_by_role("button", name="Keep this guess", exact=True).click()
            question_buttons = page.get_by_role(
                "button", name="Use the reviewed details", exact=True
            )
            while question_buttons.count():
                previous_count = question_buttons.count()
                with page.expect_response(
                    lambda response: response.url.endswith("/api/update-map")
                ):
                    question_buttons.first.click()
                expect(question_buttons).to_have_count(previous_count - 1)
            expect(page.locator(".problem-total")).to_contain_text(
                f"{audit['actual_scenario_count']} scenarios"
            )
            expect(page.get_by_role("button", name="Confirm plan", exact=True)).to_be_enabled()
            page.screenshot(path=str(screens / "read-v3-candidate-reviewed.png"), full_page=True)
            with page.expect_response(
                lambda response: response.url.endswith("/api/confirm-map")
            ) as confirmation:
                page.get_by_role("button", name="Confirm plan", exact=True).click()
            confirmed = PlanMap.model_validate(confirmation.value.json()["plan_map"])
            expect(page.locator(".result-cell")).to_have_count(
                audit["actual_scenario_count"], timeout=60000
            )
            expect(page.locator(".run-progress")).to_contain_text(
                f"{audit['actual_scenario_count']} / {audit['actual_scenario_count']}",
                timeout=60000,
            )
            page.screenshot(path=str(screens / "read-v3-candidate-grid.png"), full_page=True)
            truth = PlanMap.from_truth_map(
                PlanMapData.model_validate_json((ROOT / "fixtures/example-truth.json").read_text())
            )
            result = compare_reading(confirmed, truth)
            assert result["checker_matches"] == audit["after"]["checker_matches"]
            assert not errors, errors
            assert not any("suggest-fixes" in url for url in requests)
            proof = {
                "reference_matches": result["checker_matches"],
                "actual_scenarios": audit["actual_scenario_count"],
                "aligned_fields": result["aligned_field_match_percent"],
                "counts": page.locator(".crash-count").inner_text(),
                "page_errors": errors,
                "suggestions_requested": False,
            }
            args.reading.with_name("ui-proof.json").write_text(
                json.dumps(proof, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(proof, indent=2))
            browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=10)
        listener.close()
        http._fixture = original_fixture


if __name__ == "__main__":
    main()
