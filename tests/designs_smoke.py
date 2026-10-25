#!/usr/bin/env python3
"""Compare design directions on desktop and mobile. Optional --screenshots."""
import functools
import http.server
from pathlib import Path
import sys
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parent.parent


def main():
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    errors = []
    failed = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('response', lambda r: failed.append(r.url) if r.status >= 400 else None)
            for variant in ['edition', 'focus', 'studio']:
                for width in [1440, 390, 320, 768]:
                    page.set_viewport_size({'width': width, 'height': 1000 if width > 760 else 844})
                    page.goto(base + '/designs/?v=' + variant, wait_until='networkidle')
                    assert page.locator('h1').count() == 1
                    assert page.locator('.topic').count() == 4
                    assert page.locator('[aria-current=page]').get_attribute('href') == '?v=' + variant
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (variant, width)
                    assert page.locator('body').get_attribute('class') == variant
                    if '--screenshots' in sys.argv and width in [1440, 390]:
                        folder = ROOT / 'docs/design-directions'
                        folder.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(folder / f'{variant}-{width}.png'), full_page=True)
                # Both prominent CTAs and topic links lead to actual working screens.
                page.locator('.cta' if variant != 'studio' else '.studio-main-note').click()
                page.locator('.exercise').wait_for()
                assert '/#card/' in page.url
                page.goto(base + '/designs/?v=' + variant, wait_until='networkidle')
                page.locator('.topic').first.click()
                page.locator('.bank-row').first.wait_for()
                assert '#bank?topic=0' in page.url
            page.goto(base + '/designs/?v=invalid', wait_until='networkidle')
            assert page.locator('body').get_attribute('class') == 'edition'
            page.locator('.review-bar nav a[href="?v=focus"]').click()
            page.locator('.focus-dashboard').wait_for()
            assert not errors, errors
            assert not failed, failed
            browser.close()
    finally:
        server.shutdown()
    print('PASS: 3 designs × 4 viewport widths; card/topic navigation; variant switch; no JS or HTTP errors')


if __name__ == '__main__':
    main()
