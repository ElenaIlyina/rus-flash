#!/usr/bin/env python3
"""Text tasks: theory does not count as help; sources, return and PDF pages work."""
import functools
import hashlib
import http.server
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]


def main():
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 390, 'height': 900})
            page.on('pageerror', lambda e: errors.append(str(e)))
            for cid, kind, label in [
                ('029926', 'connections', 'Средства связи: как подобрать слово'),
                ('62A8A9', 'meanings', 'Как определить значение слова в контексте'),
                ('4BF0EE', 'style', 'Как проверить характеристики текста'),
            ]:
                card = json.loads((ROOT / f'data/card_{cid}.json').read_text())
                page.goto(base + '#card/' + cid)
                page.get_by_role('link', name=label, exact=True).click()
                page.locator(f'[data-text-skill="{kind}"]').wait_for()
                for width in [320, 390, 768, 1440]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.reload()
                page.locator(f'[data-text-skill="{kind}"]').wait_for()
                page.get_by_role('link', name='Вернуться к карточке ' + cid, exact=True).first.click()
                page.locator('#answer-form').wait_for()
                if page.locator('[name="answer-option"]').count():
                    for digit in card['answer']:
                        page.locator(f'[name="answer-option"][value="{digit}"]').check()
                else:
                    page.locator('#answer-input').fill(card['answer'])
                page.locator('#answer-form [type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible()
                event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct'] and not event['assisted'] and event['attemptNumber'] == 1
                page.get_by_role('button', name='Ответ и разбор', exact=True).click()
                page.locator('.explanation-sources summary').click()
                page.locator('.explanation-sources a[href*="dictionary="]').first.click()
                page.locator('[data-dictionary-entry]').wait_for()
                assert page.locator(f'a[href*="list={kind}"]').is_visible()
                page.get_by_role('link', name='Вернуться к карточке ' + cid, exact=True).first.click()
                page.locator('[data-action="card-rules"]').last.click()
                page.locator(f'[data-text-skill="{kind}"]').wait_for()

            page.goto(base + '#card/7756B9')
            assert page.locator('[name="answer-option"]').count() == 5
            page.get_by_role('button', name='Ответ и разбор', exact=True).click()
            assert 'прежнего орфоэпического списка' in page.locator('.explanation-text').inner_text()
            page.locator('.explanation-sources summary').click()
            links = page.locator('.explanation-sources a')
            assert links.count() == 5
            assert '#page=5' in links.nth(1).get_attribute('href')
            response = page.request.get(links.first.get_attribute('href'))
            expected = json.loads((ROOT / 'data/knowledge/stress-list.json').read_text())['sourceSha256']
            assert response.ok and hashlib.sha256(response.body()).hexdigest() == expected
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: task 1–3 theory/dictionary/back/reload; reading vs help; task 4 packed variants and exact PDF pages; 4 widths')


if __name__ == '__main__':
    main()
