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
    catalog=json.loads((ROOT/'html/assets/data/catalog.json').read_text())['cards']
    for meta in catalog:
        if meta['task']!=5 or meta.get('explanationReviewStatus')!='awaiting_dictionary_verification':continue
        runtime=json.loads((ROOT/'html/assets/data/cards'/f"{meta['id']}.json").read_text())
        source=json.loads((ROOT/'data'/f"card_{meta['id']}.json").read_text())
        assert not runtime['explanation'] and not meta['paronymComparisons'] and not meta['strategyHint']
        assert {k:v for k,v in runtime.items() if k!='explanation'}=={k:v for k,v in source.items() if k!='explanation'}
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
                dictionary_pending=review['task']==5 and review.get('dictionaryReview',{}).get('status')!='verified'
                if dictionary_pending:
                    assert review['hint'] not in page.locator('#hint').inner_text()
                else:
                    assert review['hint'] in page.locator('#hint').inner_text()
                if page.locator('[name="answer-option"]').count():
                    for digit in card['answer']:page.locator(f'[name="answer-option"][value="{digit}"]').check()
                else:page.locator('#answer-input').fill(card['answer'])
                page.locator('#answer-form [type=submit]').click()
                assert page.locator('#answer-feedback .success').is_visible(),review['id']
                page.get_by_role('button',name='Показать ответ' if dictionary_pending else 'Ответ и разбор',exact=True).click()
                if dictionary_pending:
                    assert page.locator('#explanation .explanation-text').count()==0
                    assert page.locator('.paronym-comparison').count()==0
                    assert 'Объяснение пока недоступно' in page.locator('#explanation').inner_text()
                else:
                    assert page.locator('#explanation .explanation-text').is_visible()
                if review.get('paronymPairIds') and not dictionary_pending:
                    assert page.locator('.paronym-comparison').count()==len(review['paronymPairIds'])
                    assert page.locator('.paronym-word').count()==2
                    assert page.locator('.paronym-word li').count()==4
                    for width in [320,390,768,1440]:
                        page.set_viewport_size({'width':width,'height':900})
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(review['id'],width)
                        boxes=[word.bounding_box() for word in page.locator('.paronym-word').all()]
                        if width==390: assert boxes[1]['y']>boxes[0]['y'],boxes
                        if width==1440: assert abs(boxes[1]['y']-boxes[0]['y'])<1,boxes
                    page.set_viewport_size({'width':390,'height':900})
                assert page.locator('.debug-panel').count()==0
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),review['id']
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: urgent cards 1–6; source integrity; answer checking; dictionary gate for all pending paronym cards; mobile layout')
if __name__=='__main__':main()
