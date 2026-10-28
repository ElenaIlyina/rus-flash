#!/usr/bin/env python3
"""Balanced urgent set: source integrity, per-card hints and real answer checking."""
import functools,hashlib,http.server,json,threading
from collections import Counter
from pathlib import Path
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
def main():
    reviews=json.loads((ROOT/'data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']
    assert Counter(r['task'] for r in reviews)==Counter({i:2 for i in range(1,7)})
    for review in reviews:
        card=json.loads((ROOT/'data'/f"card_{review['id']}.json").read_text())
        source={k:v for k,v in card.items() if k!='explanation'}
        assert hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==review['sourceContentSha256']
        assert hashlib.sha256(card['explanation'].encode()).hexdigest()==review['explanationSha256']
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start();errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
            for review in reviews:
                card=json.loads((ROOT/'data'/f"card_{review['id']}.json").read_text())
                page.goto(f'http://127.0.0.1:{server.server_port}/#card/{review["id"]}',wait_until='networkidle')
                page.get_by_role('button',name='Подсказка',exact=True).click()
                assert review['hint'] in page.locator('#hint').inner_text()
                if page.locator('[name="answer-option"]').count():
                    for digit in card['answer']:page.locator(f'[name="answer-option"][value="{digit}"]').check()
                else:page.locator('#answer-input').fill(card['answer'])
                page.locator('#answer-form [type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible(),review['id']
                page.get_by_role('button',name='Ответ и разбор',exact=True).click()
                assert page.locator('#explanation .explanation-text').is_visible()
                assert page.locator('.debug-panel').count()==0
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),review['id']
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: 12 cards, two per EGE position 1–6; immutable source hashes; individual hints; correct keys; mobile layout')
if __name__=='__main__':main()
