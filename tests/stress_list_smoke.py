#!/usr/bin/env python3
"""Read the full local stress list without losing or assisting a card attempt."""
import functools
import hashlib
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / 'data/knowledge/stress-list.json').read_text())
    assert [len(g['entries']) for g in data['groups']] == [60, 9, 83, 25, 7, 8]
    assert hashlib.sha256((ROOT / data['sourceFile']).read_bytes()).hexdigest() == data['sourceSha256']
    # Serve below /html/ to exercise project Pages paths as well as local navigation.
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/html/'
    errors, requests = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 390, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            page.goto(base + '#card/011AA6', wait_until='networkidle')
            assert not any('stress-list.json' in url for url in requests)
            page.locator('[name=answer-option][value="4"]').check()
            page.locator('#answer-form [type=submit]').click()
            state = page.evaluate('localStorage.getItem("rusflash_learning_v1")')
            assignment = page.evaluate('localStorage.getItem("slovo_assignment_011AA6")')
            page.locator('.practice-aside').get_by_role('link', name='Полный список ударений по частям речи').click()
            page.locator('.stress-group').first.wait_for()
            assert page.locator('.stress-group').count() == 6
            assert page.locator('.stress-words li').count() == 192
            assert '2026' in page.locator('.page-heading').inner_text()
            nouns = page.locator('[data-stress-group=nouns]')
            nouns.locator('summary').click()
            assert 'Отзыв (о книге)' in nouns.inner_text()
            assert 'отзЫв (посла из страны)' in nouns.inner_text()
            verbs = page.locator('[data-stress-group=verbs]')
            verbs.locator('summary').click()
            assert 'принЯть; прИнял, принялА, прИняли' in verbs.inner_text()
            assert verbs.locator('b').count() > 80
            response = page.request.get(page.get_by_role('link', name='Открыть исходный PDF').get_attribute('href'))
            assert response.ok
            assert hashlib.sha256(response.body()).hexdigest() == data['sourceSha256']
            assert page.evaluate('localStorage.getItem("rusflash_learning_v1")') == state
            assert page.evaluate('localStorage.getItem("slovo_assignment_011AA6")') == assignment
            page.reload(wait_until='networkidle')
            page.get_by_role('link', name='Вернуться к карточке 011AA6').first.click()
            for digit in '1235':
                page.locator(f'[name=answer-option][value="{digit}"]').check()
            page.locator('#answer-form [type=submit]').click()
            assert 'Верно не с первой попытки' in page.locator('#answer-feedback').inner_text()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['attemptNumber'] == 2 and not event['assisted'] and event['correct']
            page.get_by_role('button', name='Ответ и разбор', exact=True).click()
            page.locator('#explanation').get_by_role('link', name='Полный список ударений по частям речи').click()
            page.locator('.stress-group').first.wait_for()
            for width in [320, 390, 768, 1440]:
                page.set_viewport_size({'width': width, 'height': 900})
                page.locator('.stress-group').evaluate_all('(nodes) => nodes.forEach(node => node.open = true)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            page.goto(base + '#card/121C9D', wait_until='networkidle')
            page.locator('.practice-aside [data-action=card-rules]').click()
            page.locator('.stress-group').first.wait_for()
            assert 'card=121C9D' in page.url
            page.goto(base + '#knowledge', wait_until='networkidle')
            page.get_by_role('link', name='Полный список ударений по частям речи · ФИПИ, 2026').click()
            page.locator('.stress-group').first.wait_for()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: full stress list, six sections, source PDF, nested path, lazy load, return/reload, unassisted second attempt and four widths')


if __name__ == '__main__':
    main()
