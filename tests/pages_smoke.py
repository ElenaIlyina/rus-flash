#!/usr/bin/env python3
"""Check a real publication copy under GitHub project-site /rus-flash/ prefix.

Build first. Requires local Playwright and /usr/bin/chromium, not used by CI build.
"""
import functools
import http.server
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory(prefix='rusflash-pages-') as temporary:
        public = Path(temporary) / 'rus-flash'
        shutil.copytree(ROOT / 'html', public)
        (public / '.nojekyll').touch()
        subprocess.run(['python3', str(ROOT / 'scripts/check_pages_artifact.py'), str(public)], check=True)
        server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), functools.partial(QuietHandler, directory=temporary))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/rus-flash/'
        errors = []
        failed = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
                page = browser.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda response: failed.append(response.url) if response.status >= 400 else None)
                page.goto(base, wait_until='networkidle')
                page.evaluate('window.documentMarker = 123')
                page.locator('.study-poster').click()
                page.locator('.exercise').wait_for()
                assert page.url.startswith(base + 'card.html?id=')
                assert page.evaluate('window.documentMarker === undefined'), 'Navigation must load a new document'
                page.reload(wait_until='networkidle')
                page.locator('.exercise').wait_for()
                page.goto(base + 'progress.html?view=preview', wait_until='networkidle')
                assert page.locator('.learning-number').inner_text() == '38%'
                page.get_by_role('link', name='Моя реальная история').click()
                page.locator('.progress-grid').wait_for()
                assert page.locator('.design-review').count() == 0
                page.locator('#desktop-nav a[href="index.html"]').click()
                page.locator('.hero').wait_for()
                assert page.url.startswith(base)
                # Direct links and returning to the filtered bank work under a subpath.
                page.goto(base + 'card.html?id=0ABFEC', wait_until='networkidle')
                page.locator('.passage').wait_for()
                assert page.url == base + 'card.html?id=0ABFEC'
                page.goto(base + 'bank.html?topic=2', wait_until='networkidle')
                page.locator('#bank-search').fill('012CAB')
                page.locator('.bank-row').click()
                page.locator('.exercise').wait_for()
                page.get_by_role('link', name='К банку заданий').click()
                page.locator('#bank-search').wait_for()
                assert page.locator('#bank-search').input_value() == '012CAB'
                assert 'topic=2' in page.url and 'q=012CAB' in page.url
                assert not errors, errors
                assert not failed, failed
                browser.close()
        finally:
            server.shutdown()
    print('PASS: Pages publication copy works under /rus-flash/; app/card/progress; no HTTP or JS errors')


if __name__ == '__main__':
    main()
