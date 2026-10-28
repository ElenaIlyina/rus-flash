#!/usr/bin/env python3
"""Real-browser acceptance checks. Build data first; requires Playwright + Chromium.

python3 tests/ui_smoke.py [--screenshots]
No source data is modified. The HTTP server lives only for this test process.
"""
import functools
import http.server
import json
from pathlib import Path
import sys
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    catalog = json.loads((ROOT / 'html/assets/data/catalog.json').read_text())
    assert len(catalog['cards']) == len(list((ROOT / 'data').glob('card_*.json')))
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    errors = []
    checks = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1440, 'height': 1100})
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            requests = []
            page.on('request', lambda request: requests.append(request.url))
            page.goto(base, wait_until='networkidle')
            assert page.locator('h1').inner_text().startswith('Не всё сразу')
            assert len(page.locator('.topic-card').all()) == 4
            assert not any('/cards/' in url for url in requests), 'Home must not preload the bank'
            checks += 1
            if '--screenshots' in sys.argv:
                folder = Path('/tmp/rus-flash-screenshots/ui')
                folder.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(folder / 'desktop-home.png'), full_page=True)
            page.locator('#desktop-nav a[href="#bank"]').click()
            page.locator('#bank-search').fill('012CAB')
            assert page.locator('.bank-row').count() == 1
            assert page.locator('.group-number').inner_text() == '5'
            assert page.locator('.group-number svg').count() == 0
            assert 'Соответствие ЕГЭ-2027' not in page.locator('main').inner_text()
            assert '⭐' in page.locator('[data-filter=fav]').inner_text()
            assert '⏳' in page.locator('[data-filter=hard]').inner_text()
            page.locator('.bank-row').click()
            page.locator('#answer-input').wait_for()
            answer = json.loads((ROOT / 'data/card_012CAB.json').read_text())['answer']
            page.locator('#answer-input').fill('НЕВЕРНЫЙ ОТВЕТ')
            page.locator('#answer-form [type=submit]').click()
            assert 'не совпало' in page.locator('#answer-feedback').inner_text()
            page.locator('#answer-input').fill(answer)
            page.locator('#answer-form [type=submit]').click()
            assert 'Верно не с первой попытки' in page.locator('#answer-feedback').inner_text()
            history = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events')
            assert len(history) == 2 and not history[-1]['assisted'] and history[-1]['attemptNumber'] == 2
            page.locator('[data-action="favorite"]').click()
            assert page.evaluate('JSON.parse(localStorage.getItem("task_tags_012CAB")).fav')
            page.reload(wait_until='networkidle')
            assert page.locator('[data-action="favorite"]').get_attribute('aria-pressed') == 'true'
            page.locator('#desktop-nav a[href="#bank"]').click()
            page.locator('[data-filter=fav]').click()
            assert page.locator('[data-filter=fav]').get_attribute('aria-pressed') == 'true'
            assert page.locator('[data-filter=fav]').evaluate('e=>getComputedStyle(e).backgroundColor') == 'rgb(255, 240, 184)'
            assert page.locator('.bank-row').count() == 1
            assert page.locator('.bank-favorite').inner_text() == '⭐'
            page.locator('[data-filter=hard]').click()
            assert page.locator('.bank-row').count() == 0
            page.locator('[data-filter=all]').click()
            page.locator('#bank-search').fill('012CAB')
            page.locator('.bank-row[href="#card/012CAB"]').click()
            page.locator('#answer-input').wait_for()
            checks += 1
            page.locator('[data-action="card-rules"]').click()
            page.get_by_role('heading', name='Справочник правил').wait_for()
            assert 'Связанные правила ещё готовятся' in page.locator('main').inner_text()
            page.go_back(wait_until='networkidle')
            page.locator('#answer-input').wait_for()
            assert '012CAB' in page.locator('main').inner_text()
            checks += 1
            page.locator('#desktop-nav a[href="#progress"]').click()
            page.locator('.learning-overview').wait_for()
            page.locator('a[href="#progress?view=history"]').click()
            page.locator('.attempt-row').first.wait_for()
            assert page.locator('.attempt-row').count() == 2
            with page.expect_download() as info:
                page.locator('[data-action="export"]').click()
            exported = json.loads(Path(info.value.path()).read_text())
            assert len(exported['events']) == 2 and exported['tags']['012CAB']['fav']
            checks += 1
            no_answer = next(c['id'] for c in catalog['cards'] if not c['hasAnswer'])
            page.goto(base + '/#card/' + no_answer)
            page.locator('.exercise').wait_for()
            assert page.locator('#answer-form [type=submit]').count() == 0
            assert 'Самостоятельная проверка' in page.locator('.exercise-status').inner_text()
            checks += 1
            bitmask = next(json.loads(f.read_text()) for f in (ROOT / 'data').glob('card_*.json')
                           if json.loads(f.read_text()).get('answer_type') == 'bitmask')
            page.goto(base + '/#card/' + bitmask['number'])
            page.locator('[name=answer-option]').first.wait_for()
            for digit in bitmask['answer']:
                page.locator(f'[name=answer-option][value="{digit}"]').check()
            page.locator('#answer-form [type=submit]').click()
            assert 'Верно с первой попытки' in page.locator('#answer-feedback').inner_text()
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted') is False
            checks += 1
            # Imported markup may contain formatting, but never executable content.
            payload = json.loads((ROOT / 'data/card_012CAB.json').read_text())
            payload['question'] = '<b>Безопасное выделение</b><img src=x onerror="window.pwned=true"><script>window.pwned=true</script>'
            page.route('**/cards/012CAB.json', lambda route: route.fulfill(json=payload))
            page.goto(base + '/#card/012CAB')
            page.locator('.question-text b').wait_for()
            assert not page.evaluate('Boolean(window.pwned)')
            assert page.locator('.question-text img, .question-text script').count() == 0
            checks += 1
            page.unroute('**/cards/012CAB.json')
            # Corrupt one legacy entry: the application must continue working.
            page.evaluate('localStorage.setItem("task_tags_012CAB", "bad json")')
            page.reload(wait_until='networkidle')
            page.locator('.exercise').wait_for()
            checks += 1
            mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
            m = mobile.new_page(); m.on('pageerror', lambda e: errors.append(str(e)))
            for path in ['', '#bank', '#progress', '#knowledge', '#card/012CAB', '#card/03ADF2']:
                m.goto(base + '/' + path, wait_until='networkidle')
                assert m.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow: {path}'
                assert m.locator('#mobile-nav').is_visible()
            m.set_viewport_size({'width': 320, 'height': 740})
            for path in ['', '#bank', '#progress', '#knowledge', '#card/03ADF2']:
                m.goto(base + '/' + path, wait_until='networkidle')
                assert m.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'320px overflow: {path}'
            m.set_viewport_size({'width': 390, 'height': 844})
            checks += 1
            m.goto(base + '/#card/0ABFEC', wait_until='networkidle')
            assert m.locator('.passage').count() == 1
            assert m.locator('.question-section').is_visible()
            assert m.locator('.option').count() == 5
            m.locator('.passage summary').click()
            assert not m.locator('.passage-content').is_visible()
            assert m.locator('.question-section').is_visible()
            m.locator('.passage summary').click()
            if '--screenshots' in sys.argv:
                m.screenshot(path=str(folder / 'mobile-card.png'), full_page=True)
                m.goto(base, wait_until='networkidle')
                m.screenshot(path=str(folder / 'mobile-home.png'), full_page=True)
                page.goto(base + '/#bank', wait_until='networkidle')
                page.screenshot(path=str(folder / 'desktop-bank.png'), full_page=True)
            m.goto(base + '/#card/NOTVALID', wait_until='networkidle')
            assert 'Некорректный номер' in m.locator('main').inner_text()
            checks += 1
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print(f'PASS: {checks} browser scenarios, desktop + mobile, no JavaScript errors')


if __name__ == '__main__':
    main()
