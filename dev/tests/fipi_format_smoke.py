#!/usr/bin/env python3
"""Exercise all 2140 card adapters and representative source restorations in Chromium."""
import functools
import http.server
import json
from pathlib import Path
import sys
import threading

from browser_support import launch_chromium
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
            browser=launch_chromium(p)
            page=browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{server.server_port}/'
            page.goto(base)
            result=page.evaluate('''async ({cards, choiceIds}) => {
                const {adaptCard}=await import('./js/data.js');
                const {rich,plain}=await import('./js/ui.js');
                const choices=new Set(choiceIds);
                let matched=0;
                let rhetoricLists=0;
                let punctuationLists=0;
                for(const raw of cards){
                    const c=adaptCard(raw);
                    const sourceQuestion=plain(raw.question);
                    if(/одним\\s+и\\s+тем\\s+же\\s+правилом\\s+пунктуации/.test(sourceQuestion)){
                        const compact=value=>value.replace(/\\s+/g,' ').trim();
                        const restored=plain(c.instruction)+' '+c.options.map((text,i)=>`(${i+1})${plain(text)}`).join(' ');
                        if(c.responseType==='multiple_choice' || !c.options.length || compact(restored)!==compact(sourceQuestion)){
                            throw new Error('Wrong punctuation example layout: '+c.id);
                        }
                        punctuationLists++;
                    }
                    if(sourceQuestion.includes('Список терминов:')){
                        const [review, list]=sourceQuestion.split('Список терминов:');
                        const normalized=value=>value.replace(/\\s+/g,' ').trim();
                        if(!c.rhetoric || c.rhetoric.terms.length!==9 ||
                            normalized(plain(c.rhetoric.instruction))!==normalized(review) ||
                            !plain(c.instruction).startsWith('Установите соответствие и впишите ответ.') ||
                            normalized(c.rhetoric.terms.map((term,i)=>`${i+1}) ${plain(term)}`).join(' '))!==normalized(list)){
                            throw new Error('Wrong historical rhetoric layout: '+c.id);
                        }
                        rhetoricLists++;
                    }
                    if(choices.has(c.id)){
                        if(c.responseType!=='multiple_choice')throw new Error('Wrong checkbox type: '+c.id);
                        if(c.options.length!==raw.variants.length)throw new Error('Option count: '+c.id);
                        matched++;
                    } else if(c.options.length && c.responseType==='multiple_choice'){
                        throw new Error('Static list became checkboxes: '+c.id);
                    }
                    for(const value of [c.instruction,c.passage,...c.options,...c.errors,...c.sentences,
                        ...(c.rhetoric?.sentences || []),...(c.rhetoric?.terms || [])]){
                        const dom=new DOMParser().parseFromString(rich(value),'text/html');
                        if(dom.querySelector('script,style,iframe,input,[onclick],[style]'))throw new Error('Unsafe markup: '+c.id);
                        if(plain(value).replace(/\\s/g,'')!==dom.body.textContent.replace(/\\s/g,''))throw new Error('Lost visible text: '+c.id);
                    }
                }
                return {cards:cards.length,checkboxCards:matched,rhetoricLists,punctuationLists};
            }''',{'cards':cards,'choiceIds':choice_ids})
            assert result=={'cards':2140,'checkboxCards':701,'rhetoricLists':58,'punctuationLists':58},result
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
            for cid in ['CA147A', 'F23DF9']:
                page.goto(base+'#card/'+cid)
                instruction = page.locator('.question-text')
                instruction.wait_for()
                assert 'и запишите слово правильно' in instruction.inner_text(), cid
            rhetoric_cards = [c for c in cards if '<b><u>ИЗОБРАЗИТЕЛЬНО-ВЫРАЗИТЕЛЬНЫЕ СРЕДСТВА ЯЗЫКА</u></b>' in c['question']]
            assert len(rhetoric_cards) == 13
            for card in rhetoric_cards:
                cid = card['number']
                page.goto(base+'#card/'+cid)
                columns = page.locator('.rhetoric-matching section')
                columns.first.wait_for()
                assert columns.locator('h3').all_text_contents() == ['Предложения', 'Средства выразительности'], cid
                assert columns.nth(0).locator('p').count() == 5, cid
                assert columns.nth(1).locator('p').count() == 9, cid
                assert 'Запишите в таблицу' in page.locator('.question-text').inner_text(), cid
            page.goto(base+'#card/00EA20')
            page.locator('.rhetoric-matching').wait_for()
            assert page.locator('.rhetoric-matching section').nth(0).locator('b i').count() == 2
            assert page.locator('.rhetoric-matching section').nth(1).locator('p').nth(6).inner_text() == '7. синтаксический параллелизм'
            page.goto(base+'#card/6A4DD9')
            terms = page.get_by_role('heading', name='Список терминов', exact=True)
            terms.wait_for()
            assert page.locator('.passage-content').is_visible()
            assert 'Список терминов' not in page.locator('.question-text').inner_text()
            assert page.locator('.rhetoric-terms p').count() == 9
            assert page.locator('.rhetoric-terms p').nth(3).inner_text() == '4. просторечное слово'
            assert page.locator('#answer-input').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.goto(base+'#card/C96DCA')
            page.get_by_text('КАРТОЧКА C96DCA', exact=True).wait_for()
            prompt = page.locator('.question-text')
            assert prompt.locator('b').first.inner_text() == 'Установите соответствие и впишите ответ.'
            assert all(f'({letter})' in prompt.inner_text() for letter in 'АБВГ')
            assert page.locator('.rhetoric-terms p').count() == 9
            assert page.locator('[data-action="content-issue"]').count() == 0
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#answer-input').fill('3685')
            page.locator('#answer-form [type=submit]').click()
            page.locator('#answer-feedback .success').wait_for()
            page.locator('[data-action="reveal"]').click()
            guide = page.locator('.explanation-text table')
            assert guide.locator('tbody th').all_text_contents() == ['Троп', 'Приём', 'Синтаксическое средство']
            for width in [320, 390]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.goto(base+'#card/139F0C')
            page.get_by_text('КАРТОЧКА 139F0C', exact=True).wait_for()
            assert '(1)' not in page.locator('.question-text').inner_text()
            assert page.locator('.static-option').count() == 9
            assert page.locator('.static-option').last.locator('span').last.inner_text().startswith('Большую часть года')
            assert page.locator('[data-action="content-issue"]').count() == 0
            page.locator('#answer-input').fill('58')
            page.locator('#answer-form [type=submit]').click()
            page.locator('#answer-feedback .success').wait_for()
            page.goto(base+'#card/E6A81A')
            page.get_by_text('КАРТОЧКА E6A81A', exact=True).wait_for()
            assert page.locator('.question-text b').inner_text().strip() == 'тире'
            assert page.locator('.static-option').first.locator('span').last.inner_text().startswith('У каждого человека')
            assert page.locator('[name="answer-option"]').count() == 0
            page.locator('#answer-input').fill('45')
            page.locator('#answer-form [type=submit]').click()
            page.locator('#answer-feedback .success').wait_for()
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
