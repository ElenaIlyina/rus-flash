#!/usr/bin/env python3
"""Local import/export: preview, cancellation, merge, duplicates and rollback."""
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parent.parent


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/#progress'
    old = {'id':'local-1', 'cardId':'012CAB', 'time':'2026-10-25T10:00:00.000Z', 'correct':False, 'assisted':False, 'materialVersion':1}
    new = {**old, 'id':'import-1', 'correct':True, 'time':'2026-10-25T11:00:00.000Z'}
    payload = {'schemaVersion':1, 'exportedAt':'2026-10-25T12:00:00.000Z', 'events':[{**old, 'correct':True},new], 'lastCard':'012CAB', 'tags':{'012CAB':{'fav':False,'hard':True}}}
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':390,'height':844})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base, wait_until='networkidle')
            page.evaluate('(event) => { localStorage.setItem("rusflash_learning_v1", JSON.stringify({events:[event],lastCard:null})); localStorage.setItem("task_tags_012CAB", JSON.stringify({fav:true,hard:false})); }',old)
            page.reload(wait_until='networkidle')
            assert page.get_by_role('button',name='Скачать прогресс',exact=True).is_visible()
            with page.expect_file_chooser() as choice:
                page.get_by_role('button',name='Загрузить прогресс',exact=True).click()
            choice.value.set_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(payload).encode()})
            page.get_by_role('button',name='Объединить прогресс',exact=True).wait_for()
            assert 'Конфликтов ID: 1' in page.locator('#dialog-body').inner_text()
            before = page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            page.get_by_role('button',name='Отмена',exact=True).click()
            assert before == page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            def upload(data):
                page.locator('#progress-import').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(data).encode()})
            upload(payload)
            page.get_by_role('button',name='Объединить прогресс',exact=True).click()
            page.locator('#info-dialog').wait_for(state='hidden')
            state = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1"))')
            assert len(state['events']) == 2 and state['events'][0]['correct'] is False
            tags = page.evaluate('JSON.parse(localStorage.getItem("task_tags_012CAB"))')
            assert tags == {'fav':True,'hard':True}
            upload(payload)
            page.get_by_role('button',name='Объединить прогресс',exact=True).click()
            page.locator('#info-dialog').wait_for(state='hidden')
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.length') == 2
            before = page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            for invalid in [{**payload,'schemaVersion':99},{**payload,'events':[{**new,'correct':'true'}]}]:
                upload(invalid)
                page.get_by_role('heading',name='Не удалось загрузить прогресс').wait_for()
                assert page.locator('[data-action=apply-import]').count() == 0
                page.get_by_role('button',name='Понятно',exact=True).click()
                assert before == page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            # Simulate failure after state was written, before tag writes completed.
            page.evaluate('''() => {
                const original = Storage.prototype.setItem;
                let failed = false;
                Storage.prototype.setItem = function(key,value) {
                    if (key === 'task_tags_012CAB' && !failed) { failed = true; throw new DOMException('Full','QuotaExceededError'); }
                    return original.call(this,key,value);
                };
            }''')
            upload({**payload,'events':[{**new,'id':'import-rollback'}]})
            page.get_by_role('button',name='Объединить прогресс',exact=True).click()
            page.get_by_role('heading',name='Загрузка отменена').wait_for()
            assert before == page.evaluate('JSON.stringify(Object.entries(localStorage).sort())')
            page.locator('#info-dialog form button').click()
            with page.expect_download() as download:
                page.get_by_role('button',name='Скачать прогресс',exact=True).click()
            exported = json.loads(Path(download.value.path()).read_text())
            assert len(exported['events']) == 2 and 'demo' not in exported and 'counts' not in exported
            page.reload(wait_until='networkidle')
            assert page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.length') == 2
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: default-page export/import, preview/cancel, union merge, ID conflict, idempotency, invalid files, quota rollback, reload')


if __name__ == '__main__':
    main()
