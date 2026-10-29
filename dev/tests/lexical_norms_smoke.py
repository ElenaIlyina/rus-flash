#!/usr/bin/env python3
"""Task 6 source navigation, multiword key, assistance and narrow-screen theory."""
import functools
import http.server
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'dev/scripts'))
sys.path.insert(0,str(ROOT/'scripts'))


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base+'#card/060C0F',wait_until='networkidle')
            page.get_by_role('link',name='Лексические нормы: как редактировать предложение',exact=True).click()
            page.locator('[data-lexical-theory]').wait_for()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width':390,'height':900})
            page.get_by_role('link',name='Вернуться к карточке 060C0F',exact=True).first.click()
            page.locator('#answer-input').fill('народный')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            event=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and not event['assisted'] and event['attemptNumber']==1
            page.get_by_role('button',name='Ответ и разбор',exact=True).click()
            page.locator('.explanation-sources summary').click()
            page.locator('.explanation-sources a[href*="dictionary="]').first.click()
            page.locator('[data-dictionary-entry]').wait_for()
            assert 'Народное творчество' in page.locator('.source-paragraph').inner_text()
            assert page.get_by_role('link',name='Лексические нормы',exact=True).is_visible()
            page.reload(wait_until='networkidle')
            page.get_by_role('link',name='Вернуться к карточке 060C0F',exact=True).first.click()
            page.locator('#answer-form').wait_for()
            page.locator('[data-action="card-rules"]').last.click()
            page.locator('[data-lexical-theory]').wait_for()
            assert 'list=lexical' in page.url
            page.goto(base+'#card/B5E8E4',wait_until='networkidle')
            page.locator('#answer-input').fill('большую')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .warning').is_visible()
            page.locator('#answer-input').fill('большую часть')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            page.get_by_role('button',name='Ответ и разбор',exact=True).click()
            assert 'В ответе два слова' in page.locator('.explanation-text').inner_text()
            page.goto(base+'#card/C1F6AE',wait_until='networkidle')
            page.locator('#answer-input').fill('последствия')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .warning').is_visible()
            page.locator('#answer-input').fill('результаты')
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible()
            page.get_by_role('button',name='Ответ и разбор',exact=True).click()
            assert 'нейтрально' in page.locator('.explanation-text').inner_text()
            assert page.locator('.debug-panel').count()==0
            page.goto(base+'#card/1D1FBE',wait_until='networkidle')
            page.get_by_role('button',name='Ответ и разбор',exact=True).click()
            page.locator('.explanation-sources summary').click()
            link=page.locator('.explanation-sources a[href*="fipi-lexicon-2025.pdf"]')
            assert '#page=11' in link.get_attribute('href')
            assert page.request.get(link.get_attribute('href')).ok
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: task 6 theory; dictionary/back/reload; assistance; multiword key; exact FIPI page; 4 widths')


if __name__=='__main__':main()
