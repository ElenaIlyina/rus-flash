#!/usr/bin/env python3
"""Alphabetical index, theory, local electronic entries and assistance boundaries."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base+'#knowledge?list=paronyms', wait_until='networkidle')
            assert page.locator('.paronym-list li').count()==127
            assert page.locator('.paronym-list [data-paronym-group]').count()==127
            assert page.locator('.paronym-comparison').count()==0
            assert '2025' in page.locator('main').inner_text()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width':390,'height':900})
            page.goto(base+'#card/DA5810', wait_until='networkidle')
            page.get_by_role('link', name='Как различать паронимы', exact=True).click()
            page.get_by_role('heading', name='Как различать паронимы', exact=True).wait_for()
            page.get_by_role('link', name='Вернуться к карточке DA5810', exact=True).first.click()
            page.locator('#answer-input').fill('информации')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            event=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and not event['assisted'] and event['attemptNumber']==1
            page.get_by_role('button', name='Ответ и разбор', exact=True).click()
            link=page.locator('.paronym-word .dictionary-sources a[href*="dictionary="]').first
            link.click()
            page.locator('[data-dictionary-entry]').wait_for()
            assert 'Передача информации' in page.locator('.source-paragraph').inner_text()
            assert page.locator('.source-paragraph script, .source-paragraph [onclick]').count()==0
            page.reload(wait_until='networkidle')
            page.locator('[data-dictionary-entry]').wait_for()
            page.get_by_role('link', name='Вернуться к карточке DA5810', exact=True).first.click()
            page.locator('#answer-form').wait_for()
            source=json.loads((ROOT/'docs/references/ozhegov-shvedova-user-mobi/read-articles.json').read_text())
            for head in ['эффективный','эффект','сравнить','представлять']:
                article=next(a for a in source['entries'] if a['headword']==head)
                page.goto(base+f'#knowledge?dictionary=ozhegov-shvedova-user-copy&entry={article["id"]}',wait_until='networkidle')
                assert ' '.join(page.locator('.source-paragraph').inner_text().split())==' '.join(article['text'].split())
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.goto(base+'#knowledge?dictionary=ozhegov-shvedova-user-copy&entry=missing',wait_until='networkidle')
            assert page.get_by_role('heading', name='Статья не найдена').is_visible()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: 127 groups; theory; local dictionary entries; back/reload; theory does not mark an attempt assisted')


if __name__=='__main__':
    main()
