#!/usr/bin/env python3
"""Render all 1–15 explanations and source lists; exercise all pending notes in UI."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[2]


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors, failed = [], []
    catalog = json.loads((ROOT / 'html/assets/data/catalog.json').read_text())['cards']
    scope = [c for c in catalog if c['task'] and c['task'] <= 15]
    by_id = {c['id']:c for c in scope}
    cases = {c['id'] for c in scope if c.get('explanationNeedsSourceReview')}
    cases.update(next(c['id'] for c in scope if c['task'] == task and c['eligibleForProgress']) for task in range(1, 16))
    cases.update(['8C38AE', 'B5E8E4', 'BD75A1', '55C0E8', 'BF989E', '1A8A12', '4ED72E', '8C2046', 'D9E1DD'])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None, args=['--no-sandbox'])
            page = browser.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('response', lambda r: failed.append(r.url) if r.status >= 400 else None)
            page.goto(base, wait_until='networkidle')
            batch = page.evaluate('''async () => {
                const {loadCatalog, loadCard} = await import('./js/data.js');
                const {richExplanation} = await import('./js/ui.js');
                const {renderGrammarReferences} = await import('./js/grammar-sources.js');
                const {renderDictionaryReferences} = await import('./js/paronyms.js');
                const {renderStressReferences} = await import('./js/stress-list.js');
                const {checkResponse} = await import('./js/assessment.js');
                const catalog = await loadCatalog();
                const cards = catalog.cards.filter(c => c.task >= 1 && c.task <= 15);
                let rendered = 0, references = 0, corrections = 0;
                const badCorrections = [];
                for (let start = 0; start < cards.length; start += 24) {
                    const loaded = await Promise.all(cards.slice(start, start + 24).map(async meta => ({...await loadCard(meta.id), ...meta})));
                    for (const card of loaded) {
                        const node = document.createElement('div');
                        node.innerHTML = richExplanation(card.explanation);
                        if (!node.textContent.trim() || node.querySelector('script,style,iframe,img')) throw Error('Unsafe or empty explanation '+card.id);
                        if (!checkResponse(card.responseType, card.answer, card.acceptedAnswers)) throw Error('Rejected saved key '+card.id);
                        if (/^(?:правильный\\s+)?ответ\\s*:/im.test(card.strategyHint)) throw Error('Answer-labelled hint '+card.id);
                        const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
                        while (walker.nextNode()) {
                            const text = walker.currentNode;
                            if (!/(?:Правильно|Возможное исправление|Нейтральная редакция):$/.test(text.textContent.trim())) continue;
                            corrections++;
                            let next = text.nextSibling;
                            if (!next && ['B','STRONG'].includes(text.parentElement.tagName)) next = text.parentElement.nextSibling;
                            while (next && next.nodeType === Node.TEXT_NODE && !next.textContent.trim()) next = next.nextSibling;
                            if (!next || !['B','STRONG'].includes(next.nodeName)) badCorrections.push(card.id);
                        }
                        const kind = card.task === 1 ? 'cohesion' : card.task === 6 ? 'lexical' : card.task === 7 ? 'morphology' : 'grammar';
                        for (const [refs, html] of [
                            [card.grammarSourceRefs || [], renderGrammarReferences(card.grammarSourceRefs, {kind})],
                            [card.styleSourceRefs || [], renderGrammarReferences(card.styleSourceRefs, {kind:'style'})],
                            [Array.from(new Map((card.dictionarySourceRefs || []).map(ref => [`${ref.dictionaryId}:${ref.entryId || ref.pdfPage}:${ref.headword}`, ref])).values()), renderDictionaryReferences(card.dictionarySourceRefs, card.id)],
                            [card.stressSourceRefs || [], renderStressReferences(card.stressSourceRefs)]
                        ]) {
                            const links = document.createElement('div'); links.innerHTML = html;
                            if (links.querySelectorAll('a').length !== refs.length) throw Error('Missing visible source '+card.id);
                            references += refs.length;
                        }
                        rendered++;
                    }
                }
                return {rendered, references, corrections, badCorrections};
            }''')
            assert batch['rendered'] == 1145, batch
            assert not batch['badCorrections'], batch['badCorrections']
            ui_checks = 0
            for width in (1440, 390):
                context = browser.new_context(viewport={'width':width, 'height':1000})
                tab = context.new_page()
                tab.on('pageerror', lambda e: errors.append(str(e)))
                tab.on('response', lambda r: failed.append(r.url) if r.status >= 400 else None)
                for cid in sorted(cases):
                    meta = by_id[cid]
                    raw = json.loads((ROOT / f'data/card_{cid}.json').read_text())
                    tab.goto(base+'#card/'+cid)
                    tab.get_by_text('КАРТОЧКА '+cid, exact=True).wait_for()
                    options = tab.locator('[name="answer-option"]')
                    if options.count():
                        for digit in raw['answer']:
                            tab.locator(f'[name="answer-option"][value="{digit}"]').check()
                    else:
                        tab.locator('#answer-input').fill(raw['answer'])
                    tab.locator('#answer-form button[type=submit]').click()
                    assert tab.locator('#answer-feedback .success').is_visible(), cid
                    event = tab.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                    assert event['correct'] and not event['assisted'], cid
                    tab.locator('[data-action="reveal"]').click()
                    tab.locator('.explanation-text').wait_for()
                    assert tab.locator('[data-explanation-review]').count() == int(bool(meta.get('explanationNeedsSourceReview'))), cid
                    for summary in tab.locator('details.explanation-sources > summary').all():
                        summary.click()
                    assert tab.evaluate('document.documentElement.scrollWidth <= innerWidth'), (cid, width)
                    if cid == 'BD75A1':
                        assert 'Грохот ближнего боя нарушил зимнюю спячку медведя' in tab.locator('.explanation-text').inner_text()
                    ui_checks += 1
                context.close()
            browser.close()
        assert not errors and not failed, (errors, failed)
        result = {**batch, 'uiChecks':ui_checks, 'distinctUiCards':len(cases), 'widths':[1440,390], 'pendingUiCards':22, 'javascriptErrors':len(errors), 'failedLocalRequests':len(failed)}
        Path('/tmp/wbw-final-browser.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print('PASS: '+json.dumps(result, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
