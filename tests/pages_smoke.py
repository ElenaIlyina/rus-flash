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
                page.locator('.hero .button').click()
                page.locator('.exercise').wait_for()
                assert page.url.startswith(base + '#card/')
                page.goto(base + '#progress?view=preview', wait_until='networkidle')
                assert page.locator('.learning-number').inner_text() == '38%'
                page.get_by_role('link', name='Моя реальная история').click()
                page.locator('.progress-grid').wait_for()
                page.locator('.design-review').click()
                page.locator('.edition-hero').wait_for()
                assert page.url.startswith(base + 'designs/')
                page.get_by_role('link', name='← Текущий дизайн', exact=True).click()
                page.locator('.hero').wait_for()
                assert page.url.startswith(base)
                assert not errors, errors
                assert not failed, failed
                browser.close()
        finally:
            server.shutdown()
    print('PASS: Pages publication copy works under /rus-flash/; app/card/designs/progress; no HTTP or JS errors')


if __name__ == '__main__':
    main()
