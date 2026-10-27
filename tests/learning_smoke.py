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
                const {defaults, coefficientForRetention, validateSettings} = await import('./js/settings.js');
                let cases=0;
                const assert=(v,m)=>{cases++;if(!v)throw new Error(m)};
                const near=(a,b)=>Math.abs(a-b)<1e-10;
                const pool=c.cards.filter(x=>x.task===5&&x.eligibleForProgress).slice(0,4);
                const start=Date.parse('2026-10-20T00:00:00Z'), H=3600000;
                const events=pool.map((card,i)=>({id:'unit-'+i,cardId:card.id,time:new Date(start+i*H).toISOString(),correct:true,assisted:false,materialVersion:card.materialVersion,scoringVersion:1,assignmentId:'assignment-'+i,attemptNumber:1,completed:true}));
                const group=(ev,now=start+4*H,settings=defaults)=>project(c,ev,now,settings).groups.find(g=>g.id===5);
                assert(defaults.cardA>defaults.topicA,'card responds faster than topic');
                for(const r of [0.01,0.001,0.0001]) assert(near((1/(1+coefficientForRetention(r)))**10,r),'retention formula');
                assert(group([]).status==='not_started','empty');
                assert(group(events.slice(0,1)).status==='practicing','topic not mastered on first success');
                assert(near(project(c,events.slice(0,1),start).cardScores.get(pool[0].id),1),'first card result used directly');
                assert(project(c,[],start).cardScores.get(pool[0].id)===null,'untried card null');
                assert(group(events).status==='demonstrated','four successes reach configured threshold');
                assert(group(events,start+3*H+7*24*H).status==='due','week review inclusive boundary');
                assert(group(events,start+3*H+7*24*H-1).status==='demonstrated','before deadline');
                assert(project(c,events,start+4*H).consolidated===project(c,events,start+200*H).consolidated,'due keeps achievement');
                assert(group(events.map(e=>({...e,assisted:true}))).score===0,'help yields zero');
                const retry={...events[0],attemptNumber:2};
                assert(project(c,[retry],start).cardScores.get(pool[0].id)===0.5,'retry score 1/n');
                const wrong={...events[0],correct:false,completed:false};
                assert(project(c,[wrong],start).cardScores.get(pool[0].id)===null,'abandoned not scored');
                const two=[events[0],{...events[0],id:'second',assignmentId:'second-assignment',assisted:true,time:new Date(start+H).toISOString()}];
                assert(near(project(c,two,start+H).cardScores.get(pool[0].id),1/(1+defaults.cardA)),'second result smooths card');
                const boundary={...defaults,masteryThreshold:1};
                assert(project(c,[events[0]],start,boundary).cardStates.get(pool[0].id)==='practicing','threshold strict');
                assert(group(events.map(e=>({...e,materialVersion:1}))).score===0,'old revision excluded');
                const legacy={...events[0]}; for(const k of ['scoringVersion','assignmentId','attemptNumber','completed'])delete legacy[k];
                assert(project(c,[legacy],start).cardScores.get(pool[0].id)===1,'legacy independent success');
                assert(project(c,[{...legacy,assisted:true}],start).cardScores.get(pool[0].id)===null,'ambiguous legacy excluded');
                assert(near(group([events[0],{...events[0],id:'duplicate-completion'}]).score,group([events[0]]).score),'assignment counted once');
                assert(project(c,[events[0],events[0]],start).events.length===1,'event deduplication');
                const p=project(c,events,start+4*H);
                assert(p.skillTotal===27&&p.covered===4,'stable denominators');
                assert(Object.values(p.counts).reduce((a,b)=>a+b,0)===c.cards.length,'card partition');
                assert(!c.cards.find(x=>x.id==='682A9C').eligibleForProgress,'quarantine');
                const simple={...c,cards:c.cards.map(x=>({...x,exerciseKind:'simple'}))};
                const simpleScore=project(simple,[events[0]],start).groups.find(g=>g.id===5).score;
                assert(simpleScore<group([events[0]]).score,'simple lower topic weight');
                assert(project(simple,[events[0]],start,{...defaults,simpleWeight:1}).groups.find(g=>g.id===5).score===group([events[0]]).score,'equal weight setting');
                assert(project(simple,[events[0]],start,{...defaults,simpleWeight:0}).groups.find(g=>g.id===5).score===0,'simple zero weight');
                for(const bad of [{...defaults,cardA:0},{...defaults,reviewDays:NaN},{...defaults,masteryThreshold:2},{...defaults,topicA:'1'},{...defaults,extra:1}]){
                  let rejected=false;try{validateSettings(bad)}catch{rejected=true}assert(rejected,'invalid settings');
                }
                const {parseProgress}=await import('./js/progress-transfer.js');
                const portable={schemaVersion:2,exportedAt:new Date(start).toISOString(),events,lastCard:null,tags:{}};
                assert(parseProgress(JSON.stringify(portable)).events.length===4,'v2 import');
                for(const ev of [{...events[0],attemptNumber:0},{...events[0],completed:false},{...events[0],scoringVersion:2}]){
                  let rejected=false;try{parseProgress(JSON.stringify({...portable,events:[ev]}))}catch{rejected=true}assert(rejected,'invalid scoring event');
                }
                const next=recommendPractice({catalog:c,progress:project(c,events,start+200*H),task:5,seed:42});
                assert(next.cardId&&next.reasonCode==='review_due','due recommendation');
                const none=recommendPractice({catalog:{...c,cards:c.cards.map(x=>({...x,eligibleForProgress:false}))},progress:p,task:5});
                assert(none.kind==='unavailable','no fabricated fallback');
                return {cases};
            }''')
            page.goto(base+'#card/012CAB',wait_until='networkidle')
            page.get_by_role('button',name='Подсказка',exact=True).click()
            assert page.locator('#hint').is_visible()
            if '--screenshots' in sys.argv:
                folder=Path('/tmp/rus-flash-screenshots/learning')
                folder.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(folder/'hint-390.png'),full_page=True)
            page.reload(wait_until='networkidle')
            answer=json.loads((ROOT/'data/card_012CAB.json').read_text())['answer']
            page.locator('#answer-input').fill(answer)
            page.locator('#answer-form [type=submit]').click()
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted')
            assert '0.000' in page.locator('[data-learning-score]').inner_text()
            before = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.length')
            page.locator('#answer-form [type=submit]').click()
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.length') == before
            page.get_by_role('button',name='Начать новую попытку',exact=True).click()
            page.locator('#answer-input').fill(answer)
            page.locator('#answer-form [type=submit]').click()
            assert not page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1).assisted')
            assert '0.602' in page.locator('[data-learning-score]').inner_text()
            page.evaluate("""async () => {
              const {store}=await import('./js/store.js');
              const {parseProgress,mergeProgress}=await import('./js/progress-transfer.js');
              const data=parseProgress(store.exportData());
              if(data.schemaVersion!==2||data.events.at(-1).attemptNumber!==1||!data.events.at(-1).completed) throw new Error('new export roundtrip');
              const conflict={...data,events:[{...data.events.at(-1),attemptNumber:2}]};
              if(mergeProgress(data,conflict).summary.conflicts!==1)throw new Error('new metadata conflict');
            }""")
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
                    page.screenshot(path=str(Path('/tmp/rus-flash-screenshots/learning')/f'overview-{width}.png'),full_page=True)
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
            for value in ['1','2']:
                http_page.locator(f'[name="answer-option"][value="{value}"]').check()
            http_page.locator('#answer-form [type=submit]').click()
            assert 'Верно не с первой попытки' in http_page.locator('#answer-feedback').inner_text()
            retry_event = http_page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert retry_event['completed'] and retry_event['attemptNumber']==2 and not retry_event['assisted']
            assert '0.699' in http_page.locator('[data-learning-score]').inner_text()
            assert http_page.locator('[data-learning-status]').inner_text()=='Практикую'
            http_page.reload(wait_until='networkidle')
            for value in ['1','2']:
                http_page.locator(f'[name="answer-option"][value="{value}"]').check()
            http_page.locator('#answer-form [type=submit]').click()
            assert http_page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.filter(e => e.cardId === "EECA69").length') == 3
            http_page.close()
            page.goto(base+'#settings',wait_until='networkidle')
            assert page.get_by_role('heading',name='Настройки обучения').is_visible()
            page.locator(".settings-form details summary").click()
            for key,step in [('masteryThreshold',0.01),('simpleWeight',0.05),('reviewDays',1),('cardA',0.01),('topicA',0.01)]:
                control=page.locator(f'[name="{key}"]')
                original=control.input_value()
                start=float(original)
                control.press('ArrowUp')
                assert abs(float(control.input_value())-(start+step))<1e-10,(key,'keyboard up')
                control.press('ArrowDown')
                assert abs(float(control.input_value())-start)<1e-10,(key,'keyboard down')
                up=page.locator(f'[data-action="adjust-setting"][data-target="{key}"][data-direction="1"]')
                down=page.locator(f'[data-action="adjust-setting"][data-target="{key}"][data-direction="-1"]')
                up.click()
                assert abs(float(control.input_value())-(start+step))<1e-10,(key,'button up')
                down.click()
                assert abs(float(control.input_value())-start)<1e-10,(key,'button down')
                control.fill(control.get_attribute('min'))
                down.click()
                assert float(control.input_value())==float(control.get_attribute('min')),(key,'lower bound')
                control.fill(control.get_attribute('max'))
                up.click()
                assert float(control.input_value())==float(control.get_attribute('max')),(key,'upper bound')
                control.fill(original)
            page.locator('[name="reviewDays"]').fill('10')
            page.locator('[name="masteryThreshold"]').fill('0.8')
            page.locator('[data-action="retention"][data-target="cardA"]').first.click()
            page.get_by_role('button',name='Сохранить настройки',exact=True).click()
            assert 'Настройки сохранены' in page.locator('#settings-feedback').inner_text()
            assert page.evaluate("""async () => {
                const {loadSettings,coefficientForRetention}=await import('./js/settings.js');
                return loadSettings().cardA===coefficientForRetention(0.01);
            }"""), 'preset precision must survive saving'
            page.reload(wait_until='networkidle')
            assert page.locator('[name="reviewDays"]').input_value()=='10'
            assert page.locator('[name="masteryThreshold"]').input_value()=='0.8'
            page.locator(".settings-form details summary").click()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),width
            page.get_by_role('button',name='По умолчанию',exact=True).click()
            page.get_by_role('button',name='Сохранить настройки',exact=True).click()
            assert float(page.locator('[name="cardA"]').input_value())>float(page.locator('[name="topicA"]').input_value())
            assert not errors, errors
            browser.close()
        print(f'PASS: {result["cases"]} learning/recommendation invariants + response policies; persisted hint, new assignment, real progress, 4 widths')
    finally:
        server.shutdown()


if __name__=='__main__':
    main()
