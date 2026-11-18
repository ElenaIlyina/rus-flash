#!/usr/bin/env python3
"""Check fresh task-8 explanations and grammar citations in real Chromium.

Build application data first. Uses system Chromium when available, otherwise the
browser installed by 'python3 -m playwright install chromium'. Screenshots go to /tmp.
"""
import argparse
import functools
import http.server
import json
from pathlib import Path
import threading
from browser_support import launch_chromium
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium')
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'html')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    errors, checked = [], 0
    try:
        with sync_playwright() as p:
            browser = launch_chromium(p, args.chromium)
            for width in (1440, 390):
                context = browser.new_context(viewport={'width':width, 'height':1000})
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                for cid in ('03ADF2', '04E391', 'D4CBF0', '0C92F7', '1A8A12', '4ED72E', '8C2046', 'D9E1DD', '02E7EB', '09C42C'):
                    page.goto(base+'/#card/'+cid, wait_until='networkidle')
                    page.locator('[data-action="reveal"]').click()
                    explanation = page.locator('.explanation-text')
                    explanation.wait_for()
                    style = cid in ('02E7EB', '09C42C')
                    if not style:
                        labels = explanation.locator('b').all_text_contents()
                        assert sum(label.startswith('Предложение ') for label in labels) == 9
                    if cid in ('0C92F7', '1A8A12'):
                        assert page.locator('[data-explanation-review]').filter(has_text='Одно соответствие').count() == 1
                        assert page.locator('#answer-form button[type=submit]').count() == 1
                        assert 'спорное соответствие' in explanation.inner_text()
                        assert 'Нейтральная редакция' in explanation.inner_text()
                        answer = json.loads((ROOT / 'data' / f'card_{cid}.json').read_text())['answer']
                        page.locator('#answer-input').fill(answer)
                        page.locator('#answer-form button[type=submit]').click()
                        event = page.evaluate('JSON.parse(localStorage.getItem("rusflash_learning_v1")).events.at(-1)')
                        assert event['cardId'] == cid and event['correct'], event
                    if cid == '03ADF2':
                        assert 'неожиданно закончился' in explanation.inner_text()
                    if cid == '04E391':
                        assert 'инфинитиву' in explanation.inner_text()
                    sources = page.locator('details.explanation-sources').filter(has_text='Источники по стилистике' if style else 'Грамматические источники разбора')
                    assert sources.count() == 1
                    sources.locator('summary').click()
                    links = sources.locator('a')
                    assert links.count() >= (5 if style else 9)
                    assert all(('Вариант ' if style else 'Предложение ') in text for text in links.all_text_contents())
                    assert all(links.nth(i).get_attribute('rel') == 'noopener noreferrer' for i in range(links.count()))
                    assert not any('Эксмо' in text for text in links.all_text_contents())
                    if cid in ('4ED72E', '8C2046'):
                        assert page.locator('[data-explanation-review]').count() == 0
                        assert 'спорное соответствие' not in explanation.inner_text()
                        assert sources.locator('a[href*="cyberleninka.ru/article/n/"]').count() == 1
                    if cid == 'D9E1DD':
                        assert page.locator('[data-explanation-review]').count() == 0
                        assert sources.locator('a[href="https://dcl.bas.bg/wp-content/uploads/2022/11/08_Letuchiy_STONTBgRu2022.pdf#page=24"]').count() == 1
                    if cid == 'D4CBF0':
                        assert sources.locator('a[href="https://doc.fipi.ru/zhurnal-fipi/PI-2024-03.pdf#page=14"]').count() >= 1
                    assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), (cid, width)
                    if args.screenshots and cid in ('03ADF2', '02E7EB', '0C92F7'):
                        folder = Path('/tmp/rus-flash-screenshots/grammar')
                        folder.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(folder / f'card-{cid}-{width}.png'), full_page=True)
                    checked += 1
                context.close()
            browser.close()
        assert not errors, errors
        print(f'Grammar/style browser checks passed: {checked}; desktop and mobile; no JavaScript errors')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
