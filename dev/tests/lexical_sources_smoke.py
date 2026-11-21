"""Task-6 source links, retained keys and pending notes; standalone review table."""
import functools, hashlib, http.server, json, threading, sys
from pathlib import Path
from browser_support import launch_chromium
from playwright.sync_api import sync_playwright
root = Path(__file__).resolve().parents[2]
Path('/tmp/wbw-lexical-review').mkdir(exist_ok=True)
sys.path.insert(0, str(root / 'dev/tests'))
from ui_smoke import QuietHandler
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(root / 'html')))
threading.Thread(target=server.serve_forever, daemon=True).start()
reviews = [r for r in json.loads((root / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if 'lexicalSourceReview' in r]
books = json.loads((root / 'data/knowledge/lexical_sources.json').read_text())['sources']
byid = {b['id']: b for b in books}
errors = []
try:
    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={'width': 390, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        for r in reviews:
            cid = r['id']
            card = json.loads((root / f'data/card_{cid}.json').read_text())
            page.goto(f'http://127.0.0.1:{server.server_port}/#card/{cid}')
            page.locator('#answer-input').fill(card['answer'])
            page.locator('#answer-form [type=submit]').click()
            assert page.locator('#answer-feedback .success').is_visible(), cid
            event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
            assert event['correct'] and (not event['assisted']), cid
            page.get_by_role('button', name='Ответ и разбор', exact=True).click()
            block = page.locator('details').filter(has=page.get_by_text('Источники проверки лексики', exact=True))
            block.locator('summary').click()
            check = r['lexicalSourceReview']
            assert block.locator('a').count() == len(check['grammarEvidence']) + len(check['bookEvidence']), cid
            assert page.locator('[data-explanation-review]').count() == int(check['status'] == 'context_scope_pending'), cid
            if check['status'] == 'context_scope_pending':
                assert check['reason'] in page.locator('[data-explanation-review]').inner_text(), cid
            if cid in ['B5E8E4', 'D52745', 'C50FE5']:
                for width in [320, 390, 768, 1440]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (cid, width)
                if cid == 'C50FE5':
                    page.screenshot(path='/tmp/wbw-lexical-review/card-C50FE5-1440.png')
                    page.set_viewport_size({'width': 390, 'height': 900})
                    page.screenshot(path='/tmp/wbw-lexical-review/card-C50FE5-390.png')
            for a in block.locator('a[href*="lexical-sources/"]').all():
                href = a.get_attribute('href')
                response = page.request.get(a.evaluate('(a) => a.href'))
                sid = href.split('/')[-1].split('.pdf')[0]
                assert response.ok and hashlib.sha256(response.body()).hexdigest() == byid[sid]['sha256'], cid
        page.goto((root / 'dev/disagreements.html').as_uri())
        assert page.locator('tbody tr').count() == 25
        page.locator('#search').fill('C50FE5')
        assert page.locator('tbody tr:visible').count() == 1
        assert 'Целеустремлённо' in page.locator('tbody tr:visible').inner_text()
        for width in [390, 1440]:
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=f'/tmp/wbw-lexical-review/disagreements-{width}.png', full_page=True)
        assert not errors, errors
        browser.close()
finally:
    server.shutdown()
print('PASS: 21 task-6 keys without assistance; source review visibility; book PDF hashes; four widths; standalone 25-group HTML search')
