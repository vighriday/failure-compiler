"""Capture the real README/Devpost gallery at 1500x1000, without changing the DOM.

Run: uv run --with pillow -- python scripts/capture_gallery.py
"""

import json
import shutil
from pathlib import Path

from browser_story import play_story
from local_preview import local_preview
from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/images"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    proof = ROOT / "devpost/screens"
    images, frames, errors = [], [], []
    with local_preview() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))

        def capture(name):
            page.screenshot(path=str(OUT / name), full_page=False)
            with Image.open(OUT / name) as image:
                assert image.size == (1500, 1000)
            images.append(name)

        def scroll_to(selector):
            page.locator(selector).first.evaluate(
                "element => window.scrollTo({top: element.getBoundingClientRect().top "
                "+ scrollY - 90, behavior: 'instant'})"
            )

        def checkpoint(stage, page):
            if stage == "hero":
                capture("01-paste-plan.png")
                shutil.copyfile(OUT / "01-paste-plan.png", OUT / "video-thumbnail.png")
            elif stage == "map":
                scroll_to('[data-item-id="route-c"]')
                page.locator('[data-item-id="route-c"]').hover()
                expect(page.locator("#plan-L10")).to_have_class("paper-line line-active")
                capture("02-plan-map.png")
            elif stage == "grid":
                scroll_to(".crash-count")
                capture("03-crash-test-grid.png")
            elif stage == "broken":
                scroll_to(".ai-sentence")
                capture("04-broken-case.png")
            elif stage in {"before-sam", "after-sam"}:
                page.evaluate("window.scrollTo(0, 0)")
                target = proof / f"gallery-{stage}.png"
                page.screenshot(path=str(target), full_page=False)
                frames.append(target)
            elif stage == "builder":
                scroll_to(".change-builder")
                expect(page.locator('.fix-card[data-origin="yours"]')).to_contain_text("fixes 1")
                capture("05-fix-turned-down.png")
            elif stage == "report":
                scroll_to(".report-after")
                capture("06-report.png")

        play_story(page, base, checkpoint)
        assert not errors, errors
        browser.close()
    with Image.open(frames[0]) as first, Image.open(frames[1]) as second:
        first.save(
            OUT / "flip.gif", save_all=True, append_images=[second], duration=[3000, 3000], loop=0
        )
    (proof / "gallery-proof.json").write_text(
        json.dumps(
            {
                "viewport": [1500, 1000],
                "images": images,
                "gif": "Two actual Playwright frames before/after the Sam card; three seconds each",
                "page_errors": errors,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(images)} gallery images, the real hero thumbnail "
        "and a two-frame before/after GIF."
    )


if __name__ == "__main__":
    main()
