#!/usr/bin/env python3
"""Task-16 fresh explanations, row-specific punctuation rules, hints and keys."""
import functools
import http.server
import json
from pathlib import Path
import threading
from browser_support import launch_chromium
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]


def main():
    registry = json.loads((ROOT / 'dev/data/knowledge/punctuation_card_reviews.json').read_text())
    external_sources = {source['id']:source for source in registry['externalSources']}
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors, failed = [], []
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            page = browser.new_page(viewport={'width':390,'height':1000})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('response', lambda r: failed.append(r.url) if r.status >= 400 else None)
            for review in registry['cards']:
                cid = review['id']
                raw = json.loads((ROOT / f'data/card_{cid}.json').read_text())
                page.goto(base+'#card/'+cid)
                page.get_by_text('КАРТОЧКА '+cid, exact=True).wait_for()
                options = page.locator('[name="answer-option"]')
                assert options.count() == 5, cid
                for digit in raw['answer']:
                    page.locator(f'[name="answer-option"][value="{digit}"]').check()
                page.locator('#answer-form button[type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible(), cid
                event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct'] and not event['assisted'] and event['attemptNumber'] == 1, cid
                page.locator('[data-action="reveal"]').click()
                explanation = page.locator('.explanation-text')
                assert sum(s.startswith('Предложение ') for s in explanation.locator('b').all_text_contents()) == 5, cid
                assert explanation.locator('strong').count() == 5, cid
                sources = page.locator('details').filter(has=page.get_by_text('Пунктуация: правила по предложениям', exact=True))
                sources.locator('summary').click()
                links = sources.locator('a')
                assert links.count() == sum(len(r['sourceIds']) for r in review['rows']), cid
                assert all(t.startswith('Предложение ') and 'Пунктуация' in t for t in links.all_text_contents()), cid
                assert all('-punctuation-' in h for h in links.evaluate_all('(links) => links.map(a => a.href)')), cid
                external = page.locator('details').filter(has=page.get_by_text('Пунктуация: комментарии к предложениям', exact=True))
                expected = sum(len(r.get('externalSourceIds', [])) for r in review['rows'])
                assert external.count() == int(expected > 0), cid
                if expected:
                    external.locator('summary').click()
                    expected_urls = [external_sources[sid]['url'] for row in review['rows'] for sid in row.get('externalSourceIds', [])]
                    self_urls = external.locator('a').evaluate_all('(links) => links.map(a => a.getAttribute("href"))')
                    assert sorted(self_urls) == sorted(expected_urls), cid
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), cid
                if cid == '08B326':
                    for width in [320, 390, 768, 1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    for width in [390, 1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        page.screenshot(path=f'/tmp/wbw-task16-{width}.png', full_page=True)
                    page.set_viewport_size({'width':390,'height':1000})
                links.first.click()
                page.locator('[data-source-id]').wait_for()
                assert '§' in page.locator('.source-paragraph').inner_text()
                page.get_by_role('link', name='Вернуться к карточке '+cid, exact=True).first.click()
                page.get_by_text('КАРТОЧКА '+cid, exact=True).wait_for()
            cid = registry['cards'][0]['id']
            page.goto(base+'#card/'+cid)
            page.get_by_text('КАРТОЧКА '+cid, exact=True).wait_for()
            page.get_by_role('button', name='Начать новую попытку', exact=True).click()
            page.locator('[data-action="hint"]').click()
            assert registry['cards'][0]['hint'] in page.locator('#hint').inner_text()
            for digit in json.loads((ROOT / f'data/card_{cid}.json').read_text())['answer']:
                page.locator(f'[name="answer-option"][value="{digit}"]').check()
            page.locator('#answer-form button[type=submit]').click()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and event['assisted']
            assert not errors and not failed, (errors, failed)
            browser.close()
        count = len(registry['cards'])
        print(f'PASS: {count} task-16 keys, {count * 5} sentence explanations/highlights, rule links/back, all primary commentaries, hint assistance and four widths')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
