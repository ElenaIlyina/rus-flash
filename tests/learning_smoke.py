#!/usr/bin/env python3
"""Deterministic learning transitions, content versions, assistance and real UI."""
import functools
import http.server
import json
from pathlib import Path
import threading
import sys
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':390,'height':900})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base, wait_until='networkidle')
            result = page.evaluate('''async () => {
                const { projectProgress: project } = await import('./js/learning.js');
                const { checkResponse: check } = await import('./js/assessment.js');
                if (!check('position_set','4, 1, 3','134')) throw new Error('position set order');
                if (check('position_set','113','13')) throw new Error('duplicate selection');
                if (check('matching','52341','13254')) throw new Error('matching order');
                if (check('short_text','62','26')) throw new Error('sentence number');
                if (!check('short_text',' ЁЛКА ','елка')) throw new Error('yo normalization');
                const {recommendPractice} = await import('./js/adaptive.js');
                const c = await (await fetch('./assets/data/catalog.json')).json();
                const pool = c.cards.filter(x => x.task === 5 && x.eligibleForProgress).slice(0,3);
                const start = Date.parse('2026-10-20T00:00:00Z'), H=3600000;
                const events = pool.map((card,i) => ({id:'unit-'+i,cardId:card.id,
                    time:new Date(start+[0,1,25][i]*H).toISOString(),correct:true,assisted:false,materialVersion:card.materialVersion}));
                const group = (events, now=start+25*H) => project(c,events,now).groups.find(g=>g.id===5);
                const assert = (v,m) => { if (!v) throw new Error(m); };
                assert(group([]).status==='not_started', 'empty');
                assert(group(events.slice(0,1)).status==='practicing', 'one success is not mastery');
                assert(group(events).status==='demonstrated', 'three distinct / two sessions / 24h');
                assert(group(events,start+98*H).status==='due', 'review due');
                assert(project(c,events,start+25*H).consolidated===project(c,events,start+98*H).consolidated, 'due preserves achievement');
                assert(group(events.map(e=>({...e,assisted:true}))).status==='practicing', 'assistance');
                assert(group(events.map(e=>({...e,cardId:pool[0].id,materialVersion:pool[0].materialVersion}))).status==='practicing', 'same card');
                assert(group(events.map(e=>({...e,materialVersion:1}))).status==='practicing', 'old material versions');
                assert(group(events.map((e,i)=>({...e,time:new Date(start+i*H).toISOString()}))).status==='practicing','insufficient span');
                const error=i=>({...events[0],id:'error-'+i,correct:false,time:new Date(start+(25+i)*H).toISOString()});
                assert(group([...events,error(1)],start+27*H).status==='demonstrated','one error');
                assert(group([...events,error(1),error(2)],start+28*H).status==='practicing','two errors');
                assert(project(c,[...events,events[0]],start+26*H).events.length===3,'deduplicate');
                const p=project(c,events,start+25*H);
                assert(p.skillTotal===27 && p.covered===3,'stable denominators');
                assert(Object.values(p.counts).reduce((a,b)=>a+b,0)===c.cards.length,'card status partition');
                assert(!c.cards.find(x=>x.id==='682A9C').eligibleForProgress,'quarantined contradiction');
                const next = recommendPractice({catalog:c,progress:project(c,events,start+98*H),task:5,seed:42});
                assert(next.cardId && next.reasonCode==='review_due', 'old due cards must not be blocked by recent-list cooling');
                assert(c.cards.find(x=>x.id===next.cardId).eligibleForProgress, 'eligible selection');
                const noPool = recommendPractice({catalog:{...c,cards:c.cards.map(x=>({...x,eligibleForProgress:false}))},progress:p,task:5});
                assert(noPool.kind==='unavailable' && noPool.cardId===null,'no fabricated fallback');
                const noRepeat = recommendPractice({catalog:c,progress:p,task:5,excludeIds:[next.cardId],seed:42});
                assert(noRepeat.cardId!==next.cardId,'explicit exclusion');
                return {cases:19, events};
            }''')
            page.goto(base+'#card/012CAB',wait_until='networkidle')
            page.get_by_role('button',name='Подсказка',exact=True).click()
            assert page.locator('#hint').is_visible()
            if '--screenshots' in sys.argv:
                folder=ROOT/'docs/learning'
                folder.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(folder/'hint-390.png'),full_page=True)
            page.reload(wait_until='networkidle')
            answer=json.loads((ROOT/'data/card_012CAB.json').read_text())['answer']
            page.locator('#answer-input').fill(answer)
            page.locator('#answer-form [type=submit]').click()
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted')
            page.get_by_role('button',name='Начать новую попытку',exact=True).click()
            page.locator('#answer-input').fill(answer)
            page.locator('#answer-form [type=submit]').click()
            assert not page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted')
            page.goto(base+'#progress',wait_until='networkidle')
            assert page.locator('.preview-badge').count()==0
            assert page.locator('.learning-number').inner_text()=='0%'
            assert page.locator('.coverage-number').inner_text()=='0%'
            assert 'Попробовали 1 из 2140' in page.locator('.coverage-panel').inner_text()
            page.locator('.coverage-topic').filter(has_text='Нормы языка').locator('summary').first.click()
            page.locator('.coverage-topic[open] .skill-row').first.locator('summary').click()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                if '--screenshots' in sys.argv and width in [390,1440]:
                    page.screenshot(path=str(ROOT/'docs/learning'/f'overview-{width}.png'),full_page=True)
            # EECA69 must submit even when randomUUID is unavailable (HTTP / older browsers).
            http_page = browser.new_page()
            http_page.on('pageerror', lambda e: errors.append(str(e)))
            http_page.add_init_script('Object.defineProperty(crypto, "randomUUID", {value: undefined, configurable: true})')
            http_page.goto(base+'index.html#card/EECA69',wait_until='networkidle')
            http_page.locator('#answer-form [type=submit]').click()
            assert 'Сначала укажите ответ' in http_page.locator('#answer-feedback').inner_text()
            for value in ['1','2']:
                http_page.locator(f'[name="answer-option"][value="{value}"]').check()
            http_page.locator('#answer-form [type=submit]').click()
            assert http_page.locator('#answer-feedback .success').is_visible()
            http_page.get_by_role('button',name='Начать новую попытку',exact=True).click()
            http_page.locator('[name="answer-option"][value="3"]').check()
            http_page.locator('#answer-form [type=submit]').click()
            assert http_page.locator('#answer-feedback .warning').is_visible()
            saved = http_page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.filter(e => e.cardId === "EECA69")')
            assert len(saved) == 2 and saved[0]['correct'] and not saved[1]['correct']
            assert saved[0]['id'] != saved[1]['id']
            assert all(len(event['id']) == 36 for event in saved)
            http_page.reload(wait_until='networkidle')
            assert http_page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.filter(e => e.cardId === "EECA69").length') == 2
            http_page.close()
            assert not errors, errors
            browser.close()
        print(f'PASS: {result["cases"]} learning/recommendation invariants + response policies; persisted hint, new assignment, real progress, 4 widths')
    finally:
        server.shutdown()


if __name__=='__main__':
    main()
