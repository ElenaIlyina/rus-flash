#!/usr/bin/env python3
"""Separate review workbench; local acceptance never adds learning events."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT=Path(__file__).resolve().parents[2]


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url))
            page.goto(base+'/html/#settings',wait_until='networkidle')
            page.evaluate('localStorage.setItem("slovo_review_debug_v1","true")')
            page.reload(wait_until='networkidle')
            assert page.locator('.debug-settings,.debug-panel,a[href="#debug"]').count()==0
            assert not any('review-data.json' in url or 'review-debug.js' in url for url in requests)
            page.goto(base+'/html/#card/003B4D',wait_until='networkidle')
            history=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events')
            page.goto(base+'/dev/review/#debug?filter=all',wait_until='networkidle')
            page.locator('a[href="#card/003B4D"]').click()
            page.locator('.debug-panel').wait_for()
            page.frame_locator('#preview').locator('#answer-form').wait_for()
            page.get_by_role('button',name='Разбор принят',exact=True).click()
            page.get_by_role('button',name='Вернуть на ревью',exact=True).wait_for()
            page.reload(wait_until='networkidle')
            page.get_by_role('button',name='Вернуть на ревью',exact=True).wait_for()
            payload=json.loads((ROOT/'dev/review/review-data.json').read_text())
            next(e for e in payload if e['id']=='003B4D')['version']='changed-version'
            page.route('**/review-data.json',lambda route:route.fulfill(json=payload))
            page.reload(wait_until='networkidle')
            page.get_by_role('button',name='Разбор принят',exact=True).wait_for()
            page.goto(base+'/dev/review/#debug?filter=issues',wait_until='networkidle')
            assert page.locator('a[href="#card/493862"]').count()==1
            assert page.locator('a[href="#card/279C1A"]').count()==0
            page.goto(base+'/dev/review/#debug?filter=all',wait_until='networkidle')
            assert page.locator('a[href="#card/2A9943"],a[href="#card/135475"]').count()==0
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events')==history
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: standalone review; no production hooks; versioned local acceptance; preview; learning isolation; four widths')


if __name__=='__main__':main()
