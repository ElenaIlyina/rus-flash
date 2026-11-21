#!/usr/bin/env python3
"""Issue descriptions work with mouse, keyboard and touch without recording help."""
import functools
import http.server
import json
from pathlib import Path
import threading
from browser_support import launch_chromium
from playwright.sync_api import sync_playwright, expect
from ui_smoke import QuietHandler

ROOT=Path(__file__).resolve().parents[2]


def main():
    assets = ROOT / 'html/assets/data'
    catalog = json.loads((assets / 'catalog.json').read_text())
    issues = {c['id']: json.loads((assets / 'cards' / (c['id'] + '.json')).read_text())['content_issue']
              for c in catalog['cards'] if c['hasContentIssue']}
    resolved = ('F8BFF9', '6E2A0F', '802933')
    assert not set(resolved).intersection(issues)
    fixture_id = 'F8BFF9'
    fixture = None
    if not issues:
        fixture = json.loads((assets / 'cards' / (fixture_id + '.json')).read_text())
        fixture['content_issue'] = 'Условие требует сверки с исходником.'
        issues[fixture_id] = fixture['content_issue']
    mobile_card = next(iter(issues))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'html')))
    threading.Thread(target=server.serve_forever,daemon=True).start();errors=[]
    try:
        with sync_playwright() as p:
            browser=launch_chromium(p)
            page=browser.new_page(viewport={'width':1100,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
            base=f'http://127.0.0.1:{server.server_port}/'
            for cid in resolved:
                page.goto(base+'#card/'+cid)
                page.get_by_text('КАРТОЧКА '+cid, exact=True).wait_for()
                assert page.locator('.content-issue').count()==0
            if fixture is not None:
                page.route('**/cards/' + fixture_id + '.json', lambda route: route.fulfill(json=fixture))
            for cid,description in issues.items():
                page.goto(base+'#card/'+cid);button=page.get_by_role('button',name='Замечание к заданию',exact=True)
                button.wait_for();tip=page.locator('[role="tooltip"]')
                before=page.evaluate('localStorage.getItem("rusflash_learning_v1")')
                expect(tip).to_be_hidden();button.hover();expect(tip).to_be_visible();expect(tip).to_have_text(description)
                assert button.get_attribute('aria-describedby')==tip.get_attribute('id')
                page.mouse.move(0,0);expect(tip).to_be_hidden()
                button.focus();page.keyboard.press('Enter');expect(tip).to_be_visible()
                page.keyboard.press('Escape');expect(tip).to_be_hidden()
                assert page.evaluate('localStorage.getItem("rusflash_learning_v1")')==before
            mobile=browser.new_page(viewport={'width':320,'height':850},is_mobile=True,has_touch=True)
            if fixture is not None:
                mobile.route('**/cards/' + fixture_id + '.json', lambda route: route.fulfill(json=fixture))
            mobile.on('pageerror',lambda e:errors.append(str(e)));mobile.goto(base+'#card/'+mobile_card)
            button=mobile.get_by_role('button',name='Замечание к заданию',exact=True);tip=mobile.locator('[role="tooltip"]')
            button.tap();expect(tip).to_be_visible()
            bounds=tip.bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=320
            assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
            mobile.locator('.card-breadcrumb > span').tap();expect(tip).to_be_hidden()
            button.tap();expect(tip).to_be_visible();button.tap();expect(tip).to_be_hidden()
            mobile.goto(base+'#bank');mobile.locator('#bank-search').wait_for() if mobile.locator('#bank-search').count() else mobile.locator('.bank-tools').wait_for()
            mobile.goto(base+'#card/'+mobile_card);button.wait_for();expect(tip).to_be_hidden()
            assert not errors,errors;browser.close()
    finally:server.shutdown()
    print(f'PASS: {len(issues)} issue descriptions; hover/keyboard/Escape/touch/outside dismissal; 320px layout; no learning/help events')


if __name__=='__main__':main()
