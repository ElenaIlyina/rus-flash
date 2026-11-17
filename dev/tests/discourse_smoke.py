#!/usr/bin/env python3
"""Task-24 selection direction, original-text evidence, warnings and assisted attempts."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]


def answer(page, key):
    if page.locator('[name="answer-option"]').count():
        for digit in key:
            page.locator(f'[name="answer-option"][value="{digit}"]').check()
    else:
        page.locator('#answer-input').fill(key)
    page.locator('#answer-form [type=submit]').click()


def main():
    registry = json.loads((ROOT / 'dev/data/knowledge/discourse_card_reviews.json').read_text())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors, failed = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':390, 'height':1000})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('response', lambda r: failed.append(r.url) if r.status >= 400 else None)
            for r in registry['cards']:
                cid = r['id']; raw = json.loads((ROOT / f'data/card_{cid}.json').read_text())
                page.goto(base + '#card/' + cid)
                page.get_by_text('КАРТОЧКА ' + cid, exact=True).wait_for()
                if cid == registry['cards'][0]['id']:
                    assert page.evaluate("""async () => {
                      const { richExplanation } = await import('./js/ui.js');
                      const literal = document.createElement('div');
                      literal.innerHTML = richExplanation('Сноска*) * Автор; сноска*) * Автор', { markdown: false });
                      return literal.textContent === 'Сноска*) * Автор; сноска*) * Автор'
                        && !literal.querySelector('em')
                        && richExplanation('**важно**').includes('<strong>важно</strong>');
                    }""")
                answer(page, raw['answer'])
                assert page.locator('#answer-feedback .success').is_visible(), cid
                event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct'] and not event['assisted'] and event['attemptNumber'] == 1, cid
                page.locator('[data-action="hint"]').click()
                assert r['hint'] in page.locator('#hint').inner_text(), cid
                page.locator('[data-action="reveal"]').click()
                explanation = page.locator('.explanation-text')
                citation = json.loads((ROOT / 'dev/data/knowledge/discourse_sources.json').read_text())['citationLabel']
                assert citation in explanation.inner_text(), cid
                headers = explanation.locator('b').all_text_contents()
                assert sum(t.startswith('Утверждение ') for t in headers) == 5, cid
                text = explanation.inner_text()
                for row in r['rows']:
                    assert row['reason'] in text, (cid, row['number'])
                    assert all(e['quote'] in text for e in row['evidence']), cid
                assert ('ОШИБОЧНЫЕ' in text) == (r['selection'] == 'incorrect'), cid
                assert page.locator('[data-explanation-review]').count() == int(bool(r.get('sourceReviewPending'))), cid
                if r.get('sourceReviewPending'):
                    assert r['sourceReviewNote'] in page.locator('[data-explanation-review]').inner_text(), cid
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), cid
                if cid in {'34DD9B', '24EAE1'}:
                    for width in [320, 390, 768, 1440]:
                        page.set_viewport_size({'width':width, 'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    for width in [390, 1440]:
                        page.set_viewport_size({'width':width, 'height':1000})
                        explanation.locator('b').filter(has_text='Утверждение 1').scroll_into_view_if_needed()
                        page.screenshot(path=f'/tmp/wbw-task24-{cid}-{width}.png')
                    page.set_viewport_size({'width':390, 'height':1000})
            r = registry['cards'][0]; cid = r['id']
            page.goto(base + '#card/' + cid)
            page.get_by_text('КАРТОЧКА ' + cid, exact=True).wait_for()
            page.get_by_role('button', name='Начать новую попытку', exact=True).click()
            page.locator('[data-action="hint"]').click()
            assert r['hint'] in page.locator('#hint').inner_text()
            answer(page, json.loads((ROOT / f'data/card_{cid}.json').read_text())['answer'])
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and event['assisted']
            assert not errors and not failed, (errors, failed)
            browser.close()
        print(f'PASS: {len(registry["cards"])} task-24 cards, all five statements and original quotes, negative selection, warning, hints and four widths')
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
