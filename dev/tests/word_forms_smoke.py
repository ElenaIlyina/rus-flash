#!/usr/bin/env python3
"""Task 7: all keys, help, dictionary navigation, theory and mobile layout."""
import functools
import http.server
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]


def main():
    reviews = json.loads((ROOT / 'dev/data/knowledge/task_7_card_reviews.json').read_text())['cards']
    assert len(reviews) == 72
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
            for index, review in enumerate(reviews):
                if index % 20 == 0:
                    print(f'Task 7: {index}/72', flush=True)
                cid = review['id']
                form = review['morphologyReview']
                page.goto(base + '#card/' + cid)
                page.locator('#answer-input').fill(form['answer'].upper())
                page.locator('#answer-form [type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible(), cid
                event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct'] and not event['assisted'] and event['attemptNumber'] == 1, cid
                page.get_by_role('button', name='Подсказка', exact=True).click()
                assert review['hint'] in page.locator('#hint').inner_text(), cid
                page.get_by_role('button', name='Ответ и разбор', exact=True).click()
                assert form['correctedExcerpt'] in page.locator('.explanation-text').inner_text(), cid
                page.locator('.explanation-sources summary').click()
                links = page.locator('.explanation-sources a[href*="dictionary="]')
                assert links.count() == len(review['dictionaryReview']['sourceRefs']), cid
                links.first.click()
                page.locator('[data-dictionary-entry]').wait_for()
                quote = ' '.join(review['dictionaryReview']['sourceRefs'][0]['definitionQuote'].split())
                assert quote in ' '.join(page.locator('.source-paragraph').inner_text().split()), cid
                assert page.get_by_role('link', name='Формы слов', exact=True).is_visible()
                page.get_by_role('link', name='Вернуться к карточке ' + cid, exact=True).first.click()
                page.get_by_role('link', name='Формы слов: как выбрать правильную', exact=True).click()
                page.locator('[data-word-forms-theory]').wait_for()
                assert page.locator('.debug-panel').count() == 0
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), cid

            # Reading theory is not assistance. The accepted answer remains the FIPI key.
            context = browser.new_context(viewport={'width': 390, 'height': 900})
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base + '#card/1F3478')
            page.get_by_role('link', name='Формы слов: как выбрать правильную', exact=True).click()
            page.locator('[data-word-forms-theory]').wait_for()
            for width in [320, 390, 768, 1440]:
                page.set_viewport_size({'width': width, 'height': 900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.reload()
            page.locator('[data-word-forms-theory]').wait_for()
            page.get_by_role('link', name='Вернуться к карточке 1F3478', exact=True).first.click()
            page.locator('#answer-input').fill('клал')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and not event['assisted']

            page.goto(base + '#card/848E52')
            page.locator('#answer-input').fill('адресы')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .warning').is_visible()
            page.locator('#answer-input').fill('адреса')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and event['attemptNumber'] == 2
            score = page.evaluate('async (event) => (await import("./js/learning.js")).completionScore(event)', event)
            assert score == 0.5
            page.get_by_role('button', name='Ответ и разбор', exact=True).click()
            assert 'письменные приветствия' in page.locator('.explanation-text').inner_text()

            page.goto(base + '#card/F5ED6D')
            page.get_by_role('button', name='Подсказка', exact=True).click()
            page.locator('#answer-input').fill('ему')
            page.locator('#answer-form [type=submit]').click()
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and event['assisted']
            page.locator('[data-action="card-rules"]').last.click()
            page.locator('[data-word-forms-theory]').wait_for()
            assert 'list=word-forms' in page.url
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: all 72 task 7 keys/explanations/hints/source readers; theory/back/reload; assistance; strict keys; 4 widths')


if __name__ == '__main__':
    main()
