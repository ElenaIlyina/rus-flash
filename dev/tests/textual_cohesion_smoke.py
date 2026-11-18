#!/usr/bin/env python3
"""Task-26 adjacent links, original evidence, theory citations and assisted attempts."""
import functools
import http.server
import json
from pathlib import Path
import threading
from browser_support import launch_chromium
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
    registry = json.loads((ROOT / 'dev/data/knowledge/textual_cohesion_card_reviews.json').read_text())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors, failed = [], []
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
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
                text = explanation.inner_text()
                assert r['reason'] in text and r['otherCandidates'] in text, cid
                assert all(e['quote'] in text for e in r['evidence']), cid
                assert 'Конкретные связи установлены по тексту' in text, cid
                for link in r['links']:
                    assert link['token'] in text and link['antecedent'] in text and link['reason'] in text, cid
                refs = page.locator('.explanation-sources a').evaluate_all('(links) => links.map(a => a.href)')
                catalog = json.loads((ROOT / 'dev/data/knowledge/textual_cohesion_sources.json').read_text())
                sources = {src['id']:src for src in catalog['sources']}
                assert all(sources[e['sourceId']]['url'] in refs for e in r['theoryEvidence']), cid
                assert page.locator('[data-explanation-review]').count() == int(bool(r.get('sourceReviewPending'))), cid
                if r.get('sourceReviewPending'):
                    assert r['sourceReviewNote'] in page.locator('[data-explanation-review]').inner_text(), cid
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), cid
                if cid in {'22B2FF', '694236', 'DABD69', '38150E'}:
                    for width in [320, 390, 768, 1440]:
                        page.set_viewport_size({'width':width, 'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    for width in [390, 1440]:
                        page.set_viewport_size({'width':width, 'height':1000})
                        explanation.scroll_into_view_if_needed()
                        page.screenshot(path=f'/tmp/wbw-task26-{cid}-{width}.png')
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
        print(f'PASS: {len(registry["cards"])} task-26 cards, adjacent links and original quotes, theory links, warnings, hints and four widths')
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
