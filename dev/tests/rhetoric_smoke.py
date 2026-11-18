#!/usr/bin/env python3
"""Task-22 matching explanations, public references and assisted answers."""
import argparse
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
    registry = json.loads((ROOT / 'dev/data/knowledge/rhetoric_card_reviews.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card')
    args = parser.parse_args()
    if args.card:
        registry['cards'] = [r for r in registry['cards'] if r['id'] == args.card]
        if not registry['cards']:
            parser.error('Unknown reviewed task-22 card')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    catalog = {s['id']:s for s in json.loads((ROOT / 'dev/data/knowledge/rhetoric_sources.json').read_text())['sources']}
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
                page.locator('#answer-input').fill(raw['answer'])
                page.locator('#answer-form button[type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible(), cid
                event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct'] and not event['assisted'] and event['attemptNumber'] == 1, cid
                page.locator('[data-action="reveal"]').click()
                explanation = page.locator('.explanation-text')
                headers = explanation.locator('b').all_text_contents()
                assert all(any(h.startswith(row['letter'] + ' — ' + str(row['termNumber']) + ')') for h in headers) for row in review['rows']), cid
                assert all(row['reason'] in explanation.inner_text() for row in review['rows']), cid
                pending = bool(review.get('sourceReviewPending'))
                assert page.locator('[data-explanation-review]').count() == int(pending), cid
                if pending:
                    assert review['sourceReviewNote'] in page.locator('[data-explanation-review]').inner_text(), cid
                sources = page.locator('details').filter(has=page.get_by_text('Источники по средствам выразительности', exact=True))
                local = page.locator('details').filter(has=page.get_by_text('Правила для фрагментов задания', exact=True))
                if sources.count():
                    sources.locator('summary').click()
                    links = sources.locator('a')
                    expected = [e for row in review['rows'] for e in row['sourceEvidence'] if (catalog[e['sourceId']].get('url') or '').startswith('https:')]
                    assert links.count() == len(expected), cid
                    assert all(t.startswith('Фрагмент ') for t in links.all_text_contents()), cid
                    assert all(h.startswith('https:') for h in links.evaluate_all('(links) => links.map(a => a.href)')), cid
                if local.count():
                    local.locator('summary').click()
                    assert all(t.startswith('Фрагмент ') for t in local.locator('a').all_text_contents()), cid
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), cid
                if cid == '1E12FC':
                    for width in [320, 390, 768, 1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    for width in [390, 1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        page.screenshot(path=f'/tmp/wbw-task22-{width}.png', full_page=True)
                    page.set_viewport_size({'width':390,'height':1000})
                if local.count():
                    local.locator('a').first.click()
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
            page.locator('#answer-input').fill(json.loads((ROOT / f'data/card_{cid}.json').read_text())['answer'])
            page.locator('#answer-form button[type=submit]').click()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and event['assisted']
            assert not errors and not failed, (errors, failed)
            browser.close()
        count = len(registry['cards'])
        print(f'PASS: {count} task-22 keys/explanations, all matching fragments and source links, hint assistance' + (' and four widths' if any(r['id'] == '1E12FC' for r in registry['cards']) else ' at 390 px'))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
