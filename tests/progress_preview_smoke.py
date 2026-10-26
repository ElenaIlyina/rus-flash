#!/usr/bin/env python3
"""Acceptance of the synthetic progress concept; does not grade real learners."""
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
    base = f'http://127.0.0.1:{server.server_port}/'
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base + '#progress?view=history', wait_until='networkidle')
            before = page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            page.get_by_role('link', name='Новый дашборд · демо').click()
            page.locator('.learning-overview').wait_for()
            assert page.locator('.learning-number').inner_text() == '38%'
            assert page.locator('.coverage-number').inner_text() == '71%'
            assert page.locator('.preview-badge').inner_text() == 'ДЕМО'
            assert page.locator('.coverage-topic').count() == 4
            assert '6' in page.locator('.skill-legend').inner_text()
            folder = ROOT / 'docs/progress-preview'
            if '--screenshots' in sys.argv:
                folder.mkdir(parents=True, exist_ok=True)
            for width in [1440, 390, 320, 768]:
                page.set_viewport_size({'width': width, 'height': 1000 if width > 760 else 844})
                page.goto(base + '#progress?view=preview', wait_until='networkidle')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                if '--screenshots' in sys.argv and width in [1440, 390]:
                    page.screenshot(path=str(folder / f'overview-{width}.png'), full_page=True)
            page.get_by_role('link', name='Наступило повторение', exact=True).click()
            page.locator('.preview-scenarios [aria-current=true]').filter(has_text='Наступило').wait_for()
            assert page.locator('.learning-number').inner_text() == '38%'
            assert page.locator('.coverage-number').inner_text() == '71%'
            assert '5' in page.locator('.review-invitation h3').inner_text()
            page.get_by_role('link', name='Посмотреть навыки').click()
            page.locator('.skill-detail').wait_for()
            assert page.locator('.skill-row').count() == 5
            page.locator('.skill-row summary').first.click()
            assert 'Раньше получалось' in page.locator('.skill-row[open]').inner_text()
            page.get_by_role('link', name='В самом начале', exact=True).click()
            page.locator('.preview-scenarios [aria-current=true]').filter(has_text='В самом').wait_for()
            assert page.locator('.learning-number').inner_text() == '0%'
            assert page.locator('.coverage-number').inner_text() == '0%'
            page.get_by_role('link', name='Есть первые результаты', exact=True).click()
            page.locator('.coverage-topic').nth(1).click()
            page.locator('.skill-detail').wait_for()
            assert page.locator('.skill-row').count() == 6
            page.locator('.skill-row summary').first.click()
            assert page.locator('.skill-row[open]').count() == 1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            if '--screenshots' in sys.argv:
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.screenshot(path=str(folder / 'skills-1440.png'), full_page=True)
            page.get_by_role('link', name='Моя реальная история').click()
            page.locator('.progress-grid').wait_for()
            assert page.locator('.preview-badge').count() == 0
            after = page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            assert before == after, 'Preview must never mutate learner state'
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: progress 38%/71%, due preservation, empty example, topic drilldown, 4 widths, storage isolation')


if __name__ == '__main__':
    main()
