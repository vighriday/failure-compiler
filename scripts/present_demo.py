"""Guide a local recording through the real saved-example UI, one scene at a time.

Run with the app already running: uv run -- python scripts/present_demo.py
The guide clicks ordinary controls. It never substitutes plan facts or results.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlsplit

from browser_fixes import backup_driver, spare_keys, test_change
from browser_review import review_example
from browser_story import JOEL, TRUCK_RAVI, VAN_ABSENT, VAN_EARLY
from playwright.sync_api import Error, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCENE_COUNT = 11

GUIDE = """({number, title, ready, final}) => {
  let guide = document.getElementById('recording-guide');
  const state = window.failureRecordingGuide ||= {action: null};
  if (!guide) {
    guide = document.createElement('aside');
    guide.id = 'recording-guide';
    guide.setAttribute('aria-label', 'Recording guide');
    Object.assign(guide.style, {
      position: 'fixed', bottom: '14px', left: '18px', zIndex: '2147483647',
      background: '#f6f4ee', color: '#1a1916', border: '1px solid #8e8a80',
      padding: '12px 14px', boxShadow: '0 3px 14px #0002', maxWidth: '360px',
      font: '13px/1.5 "IBM Plex Sans", sans-serif'
    });
    for (const name of ['label', 'title', 'note']) {
      const line = document.createElement('div');
      line.dataset.guidePart = name;
      guide.appendChild(line);
    }
    const controls = document.createElement('div');
    Object.assign(controls.style, {display: 'flex', gap: '14px', marginTop: '8px'});
    for (const [action, text] of [['next', 'Next scene'], ['restart', 'Restart']]) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.guideAction = action;
      button.textContent = text;
      Object.assign(button.style, {
        cursor: 'pointer', border: '1px solid #1e6b47', padding: '5px 10px',
        background: action === 'next' ? '#1e6b47' : '#f6f4ee',
        color: action === 'next' ? '#fff' : '#1a1916', font: 'inherit'
      });
      button.addEventListener('click', () => { state.action = action; });
      controls.appendChild(button);
    }
    guide.appendChild(controls);
    document.body.appendChild(guide);
    document.addEventListener('keydown', (event) => {
      if (event.code === 'F8' && !event.repeat && state.ready) {
        event.preventDefault(); state.action = 'next';
      }
    });
  }
  state.ready = ready;
  state.action = null;
  guide.style.pointerEvents = ready ? 'auto' : 'none';
  guide.querySelector('[data-guide-part="label"]').textContent =
    `GUIDED SAVED EXAMPLE · ${number} / 11`;
  guide.querySelector('[data-guide-part="title"]').textContent = title;
  guide.querySelector('[data-guide-part="note"]').textContent = ready
    ? 'Saved AI responses. Real checker. Scroll freely.'
    : 'Preparing the next scene through the usual app controls…';
  for (const button of guide.querySelectorAll('button')) button.disabled = !ready;
  guide.querySelector('[data-guide-action="next"]').textContent = final
    ? 'Restart demo' : 'Next scene · F8';
}"""


class RestartRecording(Exception):
    pass


def frame(page, selector):
    page.locator(selector).first.evaluate(
        "element => window.scrollTo({top: element.getBoundingClientRect().top "
        "+ scrollY - 95, behavior: 'instant'})"
    )


def scenes(page, base):
    page.goto(base + "/demo")
    page.wait_for_url(base + "/")
    page.evaluate("document.fonts.ready.then(() => true)")
    yield "Overview", None

    page.get_by_role("tab", name="Start", exact=True).click()
    page.get_by_role("button", name="Load the example plan", exact=True).click()
    expect(page.get_by_role("button", name="Read plan", exact=True)).to_be_enabled()
    yield "Plain-text example plan", "textarea"

    page.get_by_role("button", name="Read plan", exact=True).click()
    expect(page.locator(".reading-row").first).to_be_visible(timeout=30000)
    yield "Real saved reading, before review", ".reading-row"

    review_example(page)
    route = page.locator('[data-item-id="route-c"]').first
    route.hover()
    yield "Reviewed facts and source lines", '[data-item-id="route-c"]'

    page.get_by_role("button", name="Confirm plan", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("84 survived", timeout=60000)
    yield "Live checker: the original 100 scenarios", ".crash-count"

    page.locator(f'[data-scenario="{VAN_EARLY}"]').click()
    expect(page.locator(".turned-down-card")).to_have_count(3, timeout=60000)
    yield "Hidden pair: eight households not delivered", ".case-panel"

    yield "Three real AI suggestions, all turned down", ".ai-sentence"

    page.locator(f'[data-scenario="{VAN_ABSENT}"]').click()
    sam = page.locator('[data-fix-id="fix-2"]')
    expect(sam).to_contain_text("Add an extra loader (Sam)", timeout=60000)
    sam.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("86 survived", timeout=60000)
    yield "Accepted Sam loader: both van pairs survive", ".accepted-fix-card"

    page.locator(f'[data-scenario="{JOEL}"]').click()
    expect(page.locator('[data-fix-id="fix-1"]')).to_contain_text(
        "Joel absent + Ravi absent", timeout=60000
    )
    spare_keys(page)
    own = test_change(page)
    yield "Your change: spare keys for Maya and Sam", ".change-builder"

    own.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("99 survived", timeout=60000)
    page.locator(f'[data-scenario="{TRUCK_RAVI}"]').click()
    expect(page.get_by_role("region", name="Test your own change")).to_be_visible(
        timeout=60000
    )
    backup_driver(page)
    own = test_change(page)
    own.get_by_role("button", name="Accept fix", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("100 survived", timeout=60000)
    yield "All 100 tested scenarios survive", ".crash-count"

    page.get_by_role("button", name="Before", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("84 survived")
    frame(page, ".crash-count")
    page.wait_for_timeout(2200)
    page.get_by_role("button", name="After", exact=True).click()
    expect(page.locator(".crash-count")).to_contain_text("100 survived")
    page.wait_for_timeout(1800)
    page.get_by_role("button", name="See report", exact=True).first.click()
    expect(page.locator(".report-after")).to_contain_text(
        "All 100 tested scenarios survive.", timeout=30000
    )
    yield "Report: results, limits and fingerprint", ".report-after"


def run_take(page, args):
    for number, (title, selector) in enumerate(scenes(page, args.url), 1):
        if selector:
            frame(page, selector)
        page.evaluate(GUIDE, {
            "number": number, "title": title, "ready": True, "final": number == SCENE_COUNT,
        })
        print(f"Scene {number}/{SCENE_COUNT}: {title}", flush=True)
        if number == 1 or args.headless and number in {7, 9, 10, 11}:
            output = ROOT / "devpost/screens"
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / f"recording-guide-{number:02}.png"))
        if args.autoplay and (number < SCENE_COUNT or args.once):
            page.wait_for_timeout(args.hold * 1000)
            action = page.evaluate("window.failureRecordingGuide.action")
        else:
            page.wait_for_function("window.failureRecordingGuide.action !== null", timeout=0)
            action = page.evaluate("window.failureRecordingGuide.action")
        if action == "restart":
            raise RestartRecording
        page.evaluate(GUIDE, {
            "number": number, "title": title, "ready": False, "final": False,
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--autoplay", action="store_true", help="Advance scenes automatically")
    parser.add_argument(
        "--hold", type=float, default=12, help="Autoplay pause per scene in seconds"
    )
    parser.add_argument("--once", action="store_true", help="Close after one complete take")
    parser.add_argument(
        "--headless", action="store_true", help="Prepare a take without opening a window"
    )
    args = parser.parse_args()
    args.url = args.url.rstrip("/")
    url = urlsplit(args.url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"} or url.path:
        parser.error("Use the local app's base address, such as http://127.0.0.1:5173")
    if args.hold <= 0:
        parser.error("--hold must be greater than zero")
    if args.headless and not (args.autoplay and args.once):
        parser.error("--headless requires --autoplay --once")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=args.headless, args=["--start-maximized"] if not args.headless else []
        )
        page = browser.new_page(
            viewport={"width": 1440, "height": 900} if args.headless else None,
            no_viewport=not args.headless,
            reduced_motion="no-preference",
        )
        page.set_default_timeout(30000)
        while not page.is_closed():
            try:
                run_take(page, args)
                if args.once:
                    print("Complete: real saved-example take, all 100 survived.", flush=True)
                    break
            except RestartRecording:
                continue
            except Error:
                if page.is_closed():
                    break
                raise
        browser.close()


if __name__ == "__main__":
    main()
