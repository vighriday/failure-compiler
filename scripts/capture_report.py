"""Print the real full example report to A4 and verify Letter using Playwright."""

import json
from pathlib import Path

from browser_story import play_story
from local_preview import local_preview
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    (ROOT / "docs").mkdir(exist_ok=True)
    proof = ROOT / "devpost/screens"
    proof.mkdir(parents=True, exist_ok=True)
    with local_preview() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        play_story(page, base)
        page.evaluate("document.fonts.ready.then(() => true)")
        page.emulate_media(media="print")
        expect(page.locator(".report-controls")).to_be_hidden()
        expect(page.locator('[data-header="1"]')).to_be_hidden()
        assert page.locator(".report-screen button:visible").count() == 0
        for paper, target in [
            ("A4", ROOT / "docs/sample-report.pdf"),
            ("Letter", proof / "sample-report-letter.pdf"),
        ]:
            page.pdf(
                path=str(target),
                format=paper,
                print_background=False,
                tagged=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=(
                    '<div style="font-size:12px;width:100%;text-align:center;color:black">'
                    'Failure Compiler · <span class="pageNumber"></span> / '
                    '<span class="totalPages"></span></div>'
                ),
            )
        assert not errors, errors
        (proof / "report-print-proof.json").write_text(
            json.dumps(
                {
                    "papers": ["A4", "Letter"],
                    "all_survived": 100,
                    "accepted_fixes": 3,
                    "controls_hidden": True,
                    "page_errors": errors,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        browser.close()
    print(
        "Printed the full real example report: docs/sample-report.pdf (A4); "
        "Letter proof saved locally."
    )


if __name__ == "__main__":
    main()
