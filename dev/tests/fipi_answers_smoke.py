#!/usr/bin/env python3
"""Check every imported FIPI answer and both confirmed alternatives in Chromium."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright, expect
from ui_smoke import QuietHandler

ROOT=Path(__file__).resolve().parents[2]


def main():
    cards={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
    ledger=json.loads((ROOT/'dev/data/fipi-results/merged-ledger.json').read_text())
    cases=[{'card':cards[r['cardId']],'accepted':list(dict.fromkeys(a['answer'] for a in r['attempts'] if a['status']=='accepted'))}
           for r in ledger['cards'] if r['status']=='accepted']
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start();errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':390,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{server.server_port}/';page.goto(base)
            count=page.evaluate('''async(cases)=>{
                const {adaptCard}=await import('./js/data.js');
                const {checkResponse}=await import('./js/assessment.js');
                for(const item of cases){
                    const c=adaptCard(item.card);
                    for(const answer of item.accepted)
                        if(!checkResponse(c.responseType,answer,c.acceptedAnswers))throw new Error('Accepted key rejected: '+c.id+' '+answer);
                }
                return cases.length;
            }''',cases);assert count==2069
            for cid,answer,accepted in [('005141','неизбежность',True),('D30EAB','235',True),('6E2A0F','3133',True),
                                        ('8CD68D','2526',True),('09C71B','затем',True),('432ADD','а',True),
                                        ('12BBAB','позже',False),('012CAB','лаковым',False)]:
                page.goto(base+'#card/'+cid);page.locator('#answer-form').wait_for()
                if cid=='6E2A0F':
                    page.get_by_role('button',name='Замечание к заданию',exact=True).click()
                    page.keyboard.press('Escape')
                if page.locator('[name="answer-option"]').count():
                    for digit in answer:page.locator(f'[name="answer-option"][value="{digit}"]').check()
                else:page.locator('#answer-input').fill(answer)
                page.locator('#answer-form [type="submit"]').click()
                expect(page.locator('#answer-feedback .success' if accepted else '#answer-feedback .warning')).to_be_visible()
                event=page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                assert event['correct']==accepted and not event['assisted'],(cid,event)
                if cid in ['09C71B','432ADD']:
                    page.get_by_role('button',name='Ответ и разбор',exact=True).click()
                    assert 'Также принимается' in page.locator('#explanation').inner_text()
            essays=[r['cardId'] for r in ledger['cards'] if r['status']=='essay_not_automatically_graded']
            assert len(essays)==71
            page.goto(base+'#card/'+essays[0]);page.locator('#answer-form').wait_for()
            assert page.locator('#answer-form [type="submit"]').count()==0
            assert not errors,errors;browser.close()
    finally:server.shutdown()
    print('PASS: all 2069 evidence-backed answers; both alternatives; strict rejection of unconfirmed synonyms; actual UI grading; no essay autograding')


if __name__=='__main__':main()
