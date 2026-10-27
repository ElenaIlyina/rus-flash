#!/usr/bin/env python3
"""Meaningful ordering, direct paragraph links, local handbook and assistance."""
import functools
import http.server
import json
from pathlib import Path
import threading
import sys
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT=Path(__file__).resolve().parents[1]


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#bank',wait_until='networkidle')
            page.evaluate('''async () => {
                const {orderCards} = await import('./js/bank-order.js');
                const cards=[{id:'000001',task:1,eligibleForProgress:false},
                  {id:'FF0001',task:10,eligibleForProgress:true},
                  {id:'000002',task:3,eligibleForProgress:true},
                  {id:'000003',task:2,eligibleForProgress:true}];
                const progress={cardStates:new Map([['FF0001','due'],['000002','not_started'],['000003','practicing']])};
                const tags=id=>({hard:id==='000003'});
                const before=JSON.stringify(cards);
                const a=orderCards(cards,'practice',progress,[],tags,42);
                if (a[0].id!=='FF0001' || a[1].id!=='000003') throw new Error('due/hard priority');
                const b=orderCards(cards,'exam',progress,[],tags,42);
                if (b.map(c=>c.task).join(',')!=='1,2,3,10') throw new Error('exam order');
                const c=orderCards(cards,'shuffle',progress,[],tags,42);
                if (c.map(c=>c.id).join()!==orderCards(cards,'shuffle',progress,[],tags,42).map(c=>c.id).join()) throw new Error('unstable shuffle');
                const fav=orderCards(cards,'practice',progress,[],id=>({...tags(id),fav:true}),42);
                if (fav.map(c=>c.id).join()!==a.map(c=>c.id).join()) throw new Error('favorite changes recommendation');
                if (JSON.stringify(cards)!==before) throw new Error('mutated catalog');
            }''')
            assert page.locator('#bank-sort').input_value()=='practice'
            page.locator('#bank-sort').select_option('exam')
            groups=page.locator('.group-number').all_inner_texts()
            assert groups==sorted(groups,key=lambda s:int(s) if s.isdigit() else 99)
            page.locator('#bank-sort').select_option('shuffle')
            first=page.locator('.bank-row').first.get_attribute('href')
            page.locator('[data-action=more]').click()
            assert page.locator('.bank-row').first.get_attribute('href')==first
            page.goto(base+'#card/09169B',wait_until='networkidle')
            page.locator('.practice-aside .rule-links').get_by_role('link',name='§2. И и Ы после приставок',exact=True).click()
            page.locator('#rule-prefixes-i-y').wait_for()
            assert page.locator('.knowledge-rule').count()==1
            assert 'подыграть' in page.locator('.knowledge-rule').inner_text()
            page.reload(wait_until='networkidle')
            assert page.locator('#rule-prefixes-i-y').is_visible()
            page.get_by_role('link',name='Орфография, §12 · Эксмо, 2007',exact=True).click()
            page.locator('[data-source-id="lopatin-2007-orthography-12"]').wait_for()
            assert 'После русских приставок' in page.locator('.source-paragraph').inner_text()
            assert '2007' in page.locator('.page-heading').inner_text()
            page.reload(wait_until='networkidle')
            page.locator('[data-source-id="lopatin-2007-orthography-12"]').wait_for()
            if '--screenshots' in sys.argv:
                folder=Path('/tmp/rus-flash-screenshots/knowledge')
                folder.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(folder/'source-12-390.png'),full_page=True)
            page.get_by_role('link',name='Оглавление книги',exact=True).click()
            page.locator('.source-index').first.wait_for()
            assert page.locator('.source-index').count()==2
            assert page.locator('.source-index-links a').count()==386
            page.goto(base+'#knowledge?source=lopatin-2007-punctuation-11',wait_until='networkidle')
            page.locator('[data-source-id="lopatin-2007-punctuation-11"]').wait_for()
            assert 'Тире' in page.locator('.source-paragraph').inner_text()
            page.goto(base+'#knowledge?rule=prefixes-i-y&card=09169B',wait_until='networkidle')
            page.locator('#rule-prefixes-i-y').wait_for()

            page.get_by_role('link',name='Вернуться к карточке 09169B').click()
            for value in ['2','3','4']:
                page.locator(f'[name=answer-option][value="{value}"]').check()
            page.locator('#answer-form [type=submit]').click()
            assert not page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted')
            page.goto(base+'#bank?status=verified',wait_until='networkidle')
            assert page.locator('#answer-availability').input_value()=='verified'
            assert 'С ответом' not in page.locator('.filter-tabs').inner_text()
            assert 'Без ответа' not in page.locator('.filter-tabs').inner_text()
            for button in page.locator('.filter-tab').all():
                assert button.locator('svg, span[aria-hidden=true]').count() > 0
            page.locator('[data-filter=practiced]').click()
            assert page.locator('.bank-row').count()==1
            assert '09169B' in page.locator('.bank-row').inner_text()
            page.locator('[data-filter=new]').click()
            assert page.locator('.bank-row[href="#card/09169B"]').count()==0
            page.locator('#answer-availability').select_option('missing')
            assert page.locator('.bank-row').count()>0
            assert 'Эталон ещё не подготовлен' in page.locator('.bank-row').first.inner_text()
            page.locator('[data-filter=fav]').click()
            assert 'закладки' in page.locator('#bank-filter-help').inner_text()
            page.locator('[data-filter=all]').click()
            page.locator('#answer-availability').select_option('verified')
            page.goto(base+'#knowledge?rule=does-not-exist',wait_until='networkidle')
            assert 'Параграф не найден' in page.locator('main').inner_text()
            for route in ['bank','knowledge','knowledge?rule=prefixes-z-s','knowledge?source=lopatin-2007-orthography-82']:
                for width in [320,390,768,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    page.goto(base+'#'+route,wait_until='networkidle')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(route,width)
            page.goto(base+'#card/09169B',wait_until='networkidle')
            page.locator('[data-action=reveal]').click()
            page.locator('.explanation-sources summary').click()
            if '--screenshots' in sys.argv:
                page.screenshot(path=str(Path('/tmp/rus-flash-screenshots/knowledge')/'prefix-09169B-1440.png'),full_page=True)
            page.get_by_role('link',name='Ряд 4: Орфография, §12 · Эксмо, 2007',exact=True).click()
            page.locator('[data-source-id="lopatin-2007-orthography-12"]').wait_for()
            payload=json.loads((ROOT/'html/assets/data/handbook-sources/lopatin-2007-orthography-12.json').read_text())
            payload['edition']['title']='<img src=x onerror="window.sourceInjected=true">'
            page.route('**/handbook-sources/lopatin-2007-orthography-12.json',lambda route:route.fulfill(json=payload))
            page.goto(base+'#knowledge?source=lopatin-2007-orthography-12',wait_until='networkidle')
            page.locator('[data-source-id="lopatin-2007-orthography-12"]').wait_for()
            assert page.locator('.page-heading img').count()==0
            assert not page.evaluate('Boolean(window.sourceInjected)')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: practice/exam/shuffle order; direct rules and edition-scoped source links; 386-paragraph index; assistance; 4 widths')


if __name__=='__main__':main()
