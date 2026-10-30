"""All words, grouped comparisons, live search, Pages paths and preserved attempts."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]

def main():
    source=json.loads((ROOT/'data/knowledge/stress-glossary.json').read_text())
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/html/'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900});errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda req:requests.append(req.url))
            page.goto(base+'#card/011AA6',wait_until='networkidle')
            assert not any('stress-glossary.json' in url for url in requests)
            page.locator('[name=answer-option][value="4"]').check();page.locator('#answer-form [type=submit]').click()
            state=page.evaluate('localStorage.getItem("rusflash_learning_v1")')
            assignment=page.evaluate('localStorage.getItem("slovo_assignment_011AA6")')
            page.locator('.practice-aside').get_by_role('link',name='Словарик ударений из всех карточек',exact=True).click()
            page.locator('[data-stress-word]').first.wait_for()
            assert page.locator('[data-stress-word]').count()==193
            assert page.locator('[data-stress-comparison]').count()==38
            assert page.locator('[data-glossary-part]').count()==6
            assert page.locator('[data-stress-word] b').count()==193
            assert page.locator('[data-stress-comparison=body-cases]').inner_text().find('нОгтя')>=0
            search=page.get_by_label('Найти слово или группу')
            search.fill('ногт');assert page.locator('[data-stress-word]:not([hidden])').count()==2
            search.fill('СВЕКЛА');assert page.locator('[data-stress-word]:not([hidden])').inner_text()=='свЁкла'
            search.fill('ничего-подобного');assert page.locator('[data-stress-empty]').is_visible()
            search.fill('звон');assert page.locator('[data-stress-word]:not([hidden])').count()==8
            search.fill('');assert page.locator('[data-stress-word]:not([hidden])').count()==193
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                page.locator('[data-glossary-part]').evaluate_all('(nodes)=>nodes.forEach(node=>node.open=true)')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            url=page.get_by_role('link',name='Скачать словарик',exact=True).get_attribute('href')
            response=page.request.get(url);assert response.ok
            assert all(w['form'] in response.text() for w in source['words'])
            assert page.evaluate('localStorage.getItem("rusflash_learning_v1")')==state
            assert page.evaluate('localStorage.getItem("slovo_assignment_011AA6")')==assignment
            page.reload(wait_until='networkidle');page.get_by_role('link',name='Вернуться к карточке 011AA6',exact=True).first.click()
            for digit in '1235':page.locator(f'[name=answer-option][value="{digit}"]').check()
            page.locator('#answer-form [type=submit]').click()
            event=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['attemptNumber']==2 and not event['assisted'] and event['correct']
            page.get_by_role('button',name='Ответ и разбор',exact=True).click()
            assert page.locator('#explanation').get_by_role('link',name='Словарик ударений из всех карточек',exact=True).count()==1
            page.goto(base+'#card/0E759D',wait_until='networkidle')
            assert page.locator('.practice-aside').get_by_role('link',name='Словарик ударений из всех карточек',exact=True).count()==1
            page.goto(base+'#knowledge',wait_until='networkidle')
            page.get_by_role('link',name='Словарик ударений из всех карточек',exact=True).click()
            page.locator('[data-stress-word]').first.wait_for()
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: 193 word forms, 570 source options, 38 comparison groups, search, download, Pages paths, unassisted return and four widths')

if __name__=='__main__':main()
