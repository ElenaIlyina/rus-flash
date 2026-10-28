#!/usr/bin/env python3
"""Layout and navigation accepted from the owner's PDF collage and clarification."""
import functools
import http.server
from pathlib import Path
import sys
import threading
from playwright.sync_api import sync_playwright
from ui_smoke import QuietHandler

ROOT = Path(__file__).resolve().parent.parent


def main():
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/'
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            folder = Path('/tmp/rus-flash-screenshots/home')
            if '--screenshots' in sys.argv:
                folder.mkdir(parents=True, exist_ok=True)
            for width in [1440, 1024, 768, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 1000 if width > 760 else 844})
                page.goto(base, wait_until='networkidle')
                assert page.locator('.study-poster').is_visible()
                assert page.locator('.site-logo img').evaluate('e => e.complete && e.naturalWidth > 0')
                assert page.locator('.site-logo img').get_attribute('alt') == 'Слово за слово'
                assert page.locator('.poster-cta').inner_text() == 'Начать заниматься'
                assert 'В ЭТОМ НОМЕРЕ' not in page.locator('.study-poster').inner_text()
                assert 'ТОЧКА ОПОРЫ' not in page.locator('.study-poster').inner_text()
                assert page.evaluate("""() => {
                    const card = document.querySelector('.study-poster');
                    const style = getComputedStyle(card);
                    const art = document.querySelector('.poster-art');
                    const footer = document.querySelector('.poster-cta');
                    return style.backgroundColor === 'rgba(0, 0, 0, 0)' &&
                        style.padding === '0px' &&
                        art.offsetTop + art.offsetHeight <= footer.offsetTop;
                }"""), ('Poster frame or overlapping rows', width)
                assert page.locator('.topic-note').count() == 4
                assert page.locator('.study-hero .button').count() == 0
                assert page.locator('.study-hero .stat-strip').count() == 1
                assert page.evaluate("document.querySelector('.home-coverage').previousElementSibling.matches('.stat-strip')")
                assert page.locator('.aggregate-progress .skill-segment').count() == 1
                assert page.locator('.aggregate-demo-badge').count() == 0
                assert 'Охват 0 / 2140' in page.locator('.aggregate-caption').inner_text()
                assert 'Пора повторить: 0' in page.locator('.aggregate-caption').inner_text()
                assert page.locator('.stat-strip strong').nth(1).inner_text() == '0'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                if width > 760:
                    assert page.locator('.sidebar').bounding_box()['width'] == 84
                    assert page.locator('#desktop-nav a[aria-label]').count() == 4
                if width == 1440:
                    note = page.locator('.topic-note').first
                    before_motion = note.evaluate('e => { const m = new DOMMatrix(getComputedStyle(e).transform); return [m.a,m.b,m.c,m.d,m.f]; }')
                    note.hover()
                    page.wait_for_timeout(450)
                    after_motion = note.evaluate('e => { const m = new DOMMatrix(getComputedStyle(e).transform); return [m.a,m.b,m.c,m.d,m.f]; }')
                    assert before_motion[:4] == after_motion[:4], 'Hover must preserve tilt'
                    assert abs(after_motion[4] + 4) < .01
                    page.emulate_media(reduced_motion='reduce')
                    assert note.evaluate('e => getComputedStyle(e).transitionDuration') == '0s'
                    page.mouse.move(0, 0)
                    page.emulate_media(reduced_motion='no-preference')
                    page.wait_for_timeout(450)
                if '--screenshots' in sys.argv and width in [1440, 390]:
                    page.screenshot(path=str(folder / f'home-{width}.png'), full_page=True)
            page.locator('#mobile-nav a[href="#progress"]').click()
            page.locator('.learning-overview').wait_for()
            assert page.locator('.preview-badge').count() == 0
            page.locator('a[href="#progress?view=history"]').click()
            page.locator('.progress-grid').wait_for()
            assert page.url.endswith('#progress?view=history')
            page.goto(base + '#study', wait_until='networkidle')
            page.locator('.topic-note').nth(2).click()
            page.locator('.bank-row').first.wait_for()
            assert '#bank?topic=2' in page.url
            page.goto(base + '#study', wait_until='networkidle')
            page.locator('.study-poster').click()
            page.locator('.exercise').wait_for()
            page.locator('#answer-input, [name=answer-option]').first.wait_for()
            card_id = page.url.split('#card/')[1]
            page.evaluate("""id => localStorage.setItem('rusflash_learning_v1', JSON.stringify({
                events: [1,2].map(i => ({id: 'coverage-test-' + i, cardId: id,
                    time: new Date().toISOString(), correct: false, assisted: false})), lastCard: id
            }))""", card_id)
            page.goto(base, wait_until='networkidle')
            assert 'Охват 1 / 2140' in page.locator('.aggregate-caption').inner_text()
            assert page.locator('.stat-strip strong').nth(1).inner_text() == '1'
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('PASS: composed home at 5 widths; notes/poster links; icon rail; real progress and history')


if __name__ == '__main__':
    main()
