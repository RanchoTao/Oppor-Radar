"""Capture the real static site with a dedicated, local Playwright browser.

Usage: .venv/Scripts/python scripts/capture_design.py before
Requires optional QA dependency: playwright. Uses installed Google Chrome.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
SIZES = [(1440, 900), (768, 1024), (390, 844), (320, 720)]


def capture(stage):
    folder = ROOT / "artifacts" / "design" / stage
    folder.mkdir(parents=True, exist_ok=True)
    results = {"stage": stage, "viewports": [], "console_errors": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(device_scale_factor=1)
        page.on("pageerror", lambda error: results["console_errors"].append(str(error)))
        for width, height in SIZES:
            page.set_viewport_size({"width": width, "height": height})
            page.goto(BASE, wait_until="networkidle")
            page.locator(".front-lead h3").wait_for()
            page.screenshot(path=str(folder / f"home-{width}.png"))
            results["viewports"].append(page.evaluate("""() => ({
                width: innerWidth, height: innerHeight,
                scrollWidth: document.documentElement.scrollWidth,
                navVisible: getComputedStyle(document.querySelector('nav')).display !== 'none',
                leadTop: document.querySelector('.front-lead h3').getBoundingClientRect().top,
                smallText: [...document.querySelectorAll('p,span,a,button')].filter(e =>
                  e.getBoundingClientRect().height && parseFloat(getComputedStyle(e).fontSize) < 12).length
            })"""))
            if width == 1440:
                for i in range(8):
                    page.locator(".edition-tab").nth(i).click()
                    page.wait_for_timeout(250)
                    page.screenshot(path=str(folder / f"edition-{i+1:02}.png"))
                page.locator("#newspaper-select").select_option(index=1)
                page.locator(".front-lead h3").wait_for()
                page.wait_for_function("document.querySelector('.section-no').textContent.includes('2026-10-17')")
                page.screenshot(path=str(folder / "date-history.png"))
            for section in ["reports", "sources", "settings"]:
                page.locator(f"#{section}").scroll_into_view_if_needed()
                # Place the section below the sticky global navigation.
                page.evaluate("id => window.scrollTo(0, document.getElementById(id).offsetTop - 100)", section)
                if section == "sources":
                    page.get_by_role("button", name="数学 / AI for Math", exact=True).click()
                page.wait_for_timeout(300)
                page.screenshot(path=str(folder / f"{section}-{width}.png"))
            page.goto(BASE + "/admin.html", wait_until="networkidle")
            page.screenshot(path=str(folder / f"admin-{width}.png"))
        browser.close()
    (folder / "capture.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    capture(sys.argv[1] if len(sys.argv) > 1 else "before")
