#!/usr/bin/env python3
"""Opt-in local review, version invalidation and learner-state isolation."""
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url))
            page.goto(base+'#card/003B4D',wait_until='networkidle')
            assert page.locator('.debug-panel').count()==0
            assert not any('review-debug.json' in url for url in requests)
            history=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events')
            page.goto(base+'#settings',wait_until='networkidle')
            page.locator('.debug-settings summary').click()
            page.get_by_role('button',name='Включить ревью карточек',exact=True).click()
            page.locator('.debug-settings summary').click()
            page.get_by_role('link',name='Открыть очередь ревью →',exact=True).click()
            page.get_by_role('heading',name='Ревью карточек').wait_for()
            page.locator('a[href="#card/003B4D"]').click()
            page.locator('.debug-panel').wait_for()
            page.get_by_role('button',name='Разбор принят',exact=True).click()
            page.get_by_role('button',name='Вернуть на ревью',exact=True).wait_for()
            page.reload(wait_until='networkidle')
            page.get_by_role('button',name='Вернуть на ревью',exact=True).wait_for()
            payload=json.loads((ROOT/'html/assets/data/review-debug.json').read_text())
            next(entry for entry in payload if entry['id']=='003B4D')['version']='changed-version'
            page.route('**/review-debug.json',lambda route:route.fulfill(json=payload))
            page.reload(wait_until='networkidle')
            page.get_by_role('button',name='Разбор принят',exact=True).wait_for()
            page.goto(base+'#debug?filter=issues',wait_until='networkidle')
            assert page.locator('a[href="#card/493862"]').count()==1
            assert page.locator('a[href="#card/279C1A"]').count()==0
            page.goto(base+'#debug?filter=all',wait_until='networkidle')
            assert page.locator('a[href="#card/2A9943"], a[href="#card/135475"]').count()==0
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            page.goto(base+'#settings',wait_until='networkidle')
            page.locator('.debug-settings summary').click()
            page.get_by_role('button',name='Выключить ревью карточек',exact=True).click()
            page.goto(base+'#bank',wait_until='networkidle')
            assert page.locator('.debug-badge, .debug-panel, a[href="#debug"]').count()==0
            page.goto(base+'#debug',wait_until='networkidle')
            page.get_by_role('heading',name='Отладка выключена').wait_for()
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events')==history
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: debug off by default/lazy loading; queue/issues; versioned acceptance; persistence; disabling; learning isolation; 4 widths')
if __name__=='__main__':main()
