#!/usr/bin/env python3
"""Exercise all 2140 card adapters and representative source restorations in Chromium."""
import functools
import http.server
import json
from pathlib import Path
import sys
import threading

from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import audit_fipi_format as audit


def main():
    source=audit.snapshots()
    cards=[json.loads(p.read_text()) for p in sorted((ROOT/'data').glob('card_*.json'))]
    choice_ids=[]
    for cid,raw in source.items():
        tree=audit.html.fragment_fromstring(raw['html'],create_parent='div')
        if tree.xpath('.//table[@class="distractors-table"]'):choice_ids.append(cid)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{server.server_port}/'
            page.goto(base)
            result=page.evaluate('''async ({cards, choiceIds}) => {
                const {adaptCard}=await import('./js/data.js');
                const {rich,plain}=await import('./js/ui.js');
                const choices=new Set(choiceIds);
                let matched=0;
                for(const raw of cards){
                    const c=adaptCard(raw);
                    if(choices.has(c.id)){
                        if(c.responseType!=='multiple_choice')throw new Error('Wrong checkbox type: '+c.id);
                        if(c.options.length!==raw.variants.length)throw new Error('Option count: '+c.id);
                        matched++;
                    } else if(c.options.length && c.responseType==='multiple_choice'){
                        throw new Error('Static list became checkboxes: '+c.id);
                    }
                    for(const value of [c.instruction,...c.options,...c.errors,...c.sentences]){
                        const dom=new DOMParser().parseFromString(rich(value),'text/html');
                        if(dom.querySelector('script,style,iframe,input,[onclick],[style]'))throw new Error('Unsafe markup: '+c.id);
                        if(plain(value).replace(/\\s/g,'')!==dom.body.textContent.replace(/\\s/g,''))throw new Error('Lost visible text: '+c.id);
                    }
                }
                return {cards:cards.length,checkboxCards:matched};
            }''',{'cards':cards,'choiceIds':choice_ids})
            assert result=={'cards':2140,'checkboxCards':701},result
            for cid,count in [('279C1A',5),('2D813D',5),('AC9F9C',5),('B7E06E',5),('C0A0ED',5),('14AF4C',5),('E0107D',5),('1CB807',5),('082CB8',5),('011AA6',5)]:
                page.goto(base+'#card/'+cid)
                page.locator('.options').wait_for()
                assert page.locator('[name="answer-option"]').count()==count,cid
                assert all(text.strip() for text in page.locator('.option span').all_text_contents()),cid
            page.goto(base+'#card/082CB8')
            page.locator('.options').wait_for()
            assert page.locator('.option b').count()>=5
            assert page.locator('.option i').count()>=5
            for cid in ['012CAB','3AE61A','64CB69','DE0170','005141']:
                page.goto(base+'#card/'+cid)
                page.locator('.options').wait_for()
                assert page.locator('.static-option').count()==5,cid
                assert page.locator('[name="answer-option"]').count()==0,cid
                assert page.locator('#answer-input').count()==1,cid
            page.goto(base+'#card/03ADF2')
            page.locator('.matching').wait_for()
            assert page.locator('.matching section').nth(0).locator('p').count()==5
            assert page.locator('.matching section').nth(1).locator('p').count()==9
            assert 'Вчера дождь' not in page.locator('.question-text').inner_text()
            for cid in ['0ABFEC','279C1A','012CAB','03ADF2','368BDC']:
                page.goto(base+'#card/'+cid)
                page.locator('.question-text').wait_for()
                for width in [320,390,768,1440]:
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(cid,width)
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('PASS: all 2140 adapters; 701 checkbox cards; restored options, formatting, static/matching lists and four viewport widths')


if __name__=='__main__':main()
