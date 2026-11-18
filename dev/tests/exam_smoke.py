#!/usr/bin/env python3
"""End-to-end variants: resume, theory, grading, history, failures and mobile."""
import functools
import http.server
import json
from pathlib import Path
import threading
from browser_support import launch_chromium
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]
KEY = 'rusflash_variants_v1'


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/#variants'
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p)
            errors = []
            for mode in ['scored', 'learning', 'exam']:
                context = browser.new_context(viewport={'width':390,'height':844})
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base)
                page.locator(f'[data-mode="{mode}"]').click()
                page.locator('#exam-answer').wait_for()
                s = page.evaluate(f'JSON.parse(localStorage.getItem("{KEY}")).sessions.at(-1)')
                assert len(s['items']) == 26
                assert not page.locator('[data-exam-storage]').is_visible()
                assert page.locator('[data-exam-theory]').count() == int(mode == 'learning')
                if mode == 'learning':
                    page.locator('[data-exam-theory] summary').click()
                    page.wait_for_function(f'JSON.parse(localStorage.getItem("{KEY}")).sessions.at(-1).theoryUsed.length===1')
                first = s['items'][0]['id']
                page.locator('#exam-answer').fill('черновой ответ')
                page.reload()
                page.locator('#exam-answer').wait_for()
                assert page.locator('#exam-answer').input_value() == 'черновой ответ'
                page.locator('[data-exam="jump"][data-index="7"]').click()
                page.locator('#exam-answer').wait_for()
                assert 'ЗАДАНИЕ 8' in page.locator('.exercise .eyebrow').inner_text()
                page.reload()
                page.locator('#exam-answer').wait_for()
                assert 'ЗАДАНИЕ 8' in page.locator('.exercise .eyebrow').inner_text()
                for i, item in enumerate(s['items']):
                    page.locator(f'[data-exam="jump"][data-index="{i}"]').click()
                    page.locator('#exam-answer').wait_for()
                    raw = json.loads((ROOT / f'data/card_{item["id"]}.json').read_text())
                    answer = raw['answer']
                    if mode == 'scored' and item['task'] in [8,22]:
                        answer = answer[:-1] + ('9' if answer[-1] != '9' else '8')
                    page.locator('#exam-answer').fill(answer)
                    assert page.locator('.exam-result').count() == 0
                for width in [320,390,768,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (mode,width)
                if mode == 'learning':
                    page.locator('[data-exam="jump"][data-index="0"]').click()
                    page.locator('#exam-answer').wait_for()
                    page.locator('[data-exam-theory] summary').click()
                    page.screenshot(path='/tmp/wbw-exam-learning-1440.png',full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path='/tmp/wbw-exam-learning-390.png',full_page=True)
                page.locator('[data-exam="finish-ask"]').click()
                page.locator('[data-exam="finish"]').click()
                page.locator('.exam-result').first.wait_for()
                saved = page.evaluate(f'JSON.parse(localStorage.getItem("{KEY}")).sessions.at(-1)')
                assert saved['finishedAt'] and len(saved['results']) == 26
                assert sum(r['points'] for r in saved['results']) == (24 if mode=='scored' else 28)
                assert sum(r['correct'] for r in saved['results']) == (24 if mode=='scored' else 26)
                if mode == 'scored':
                    assert '24 из 28 баллов' in page.locator('h2').first.inner_text()
                    assert all(r['points']==0 and r['max']==2 for r in saved['results'] if r['task'] in [8,22])
                assert len(saved['theoryUsed']) == int(mode=='learning')
                assert page.evaluate('localStorage.getItem("rusflash_learning_v1")') is None
                assert page.locator('#exam-answer').count() == 0
                page.locator('[data-exam="home"]').click()
                page.locator('[data-exam="result"]').click()
                page.locator('.exam-result').first.wait_for()
                page.locator('[data-exam="home"]').click()
                page.locator(f'[data-mode="{mode}"]').click()
                page.locator('#exam-answer').wait_for()
                nxt = page.evaluate(f'JSON.parse(localStorage.getItem("{KEY}")).sessions.at(-1)')
                assert all(a['id']!=b['id'] for a,b in zip(saved['items'],nxt['items']))
                # Stale material cannot receive a new score, nor lose its draft silently.
                page.evaluate(f'''() => {{ const x=JSON.parse(localStorage.getItem('{KEY}'));x.sessions.at(-1).items[0].version++;localStorage.setItem('{KEY}',JSON.stringify(x)); }}''')
                page.reload()
                page.get_by_role('alert').wait_for()
                assert 'Материал варианта изменился' in page.get_by_role('alert').inner_text()
                context.close()
            # Storage failure must be visible, not a false promise of saved answers.
            context=browser.new_context()
            context.add_init_script("const set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='rusflash_variants_v1')throw new Error('quota');return set.call(this,k,v)}")
            page=context.new_page();page.goto(base)
            page.locator('[data-mode="scored"]').click();page.locator('#exam-answer').wait_for()
            assert page.locator('[data-exam-storage]').is_visible()
            context.close()
            assert not errors, errors
            browser.close()
        print('PASS: three modes, 26 tasks, exact 0/2 scoring, theory assistance, autosave/resume, history, rotation, stale versions, storage failure and four widths')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
