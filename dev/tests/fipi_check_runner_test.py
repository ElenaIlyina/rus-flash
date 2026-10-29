"""Local protocol fixture: cookies, exact wire answers, pauses and resuming."""
import copy
from contextlib import redirect_stdout
import http.server
import io
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import check_fipi_answers as checker


class FipiCheckRunnerTest(unittest.TestCase):
    def test_pauses_between_all_requests_and_batches(self):
        pauses = []
        pacer = checker.RequestPacer(0.5, 2, 10, sleeper=pauses.append)
        with redirect_stdout(io.StringIO()):
            for _ in range(4):
                pacer.wait()
        self.assertEqual(pauses, [0.5, 0.5, 10, 0.5])
        self.assertEqual(pacer.requests, 4)

    def test_wire_formats_are_not_guessed_from_digits_alone(self):
        choice = {'number':'ABCDEF','answer_type':'bitmask','variants':['a','b','c','d','e']}
        self.assertEqual(checker.wire_answer(choice, '1235'), '11101')
        raw = {'number':'ABCDEF','html':'<input type="checkbox"><input type="checkbox"><input type="checkbox">'}
        self.assertEqual(checker.wire_answer(raw, '13'), '101')
        matching = {'number':'ABCDEF','question':'Установите соответствие', 'errors':['a'], 'sentences':['b']}
        self.assertEqual(checker.wire_answer(matching, '13254'), '13254')
        self.assertEqual(checker.wire_answer({'number':'ABCDEF'}, '18'), '18')

    def test_protocol_evidence_and_resume_do_not_repeat_final_results(self):
        calls = []
        failing = {'enabled':True}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append(('GET', self.path))
                self.send_response(200)
                self.send_header('Set-Cookie', 'test_session=fixture; Path=/')
                self.end_headers()
                self.wfile.write(b'bank')

            def do_POST(self):
                body = urllib.parse.parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
                calls.append(('POST', body))
                assert set(body) == {'guid','answer','ajax','proj'}
                assert self.headers['Cookie'] == 'test_session=fixture'
                answer = body['answer'][0]
                if answer == 'а' and failing['enabled']:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'3')  # Error body must never become acceptance.
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'2' if answer in {'а','позже'} else b'3')

        server = http.server.ThreadingHTTPServer(('127.0.0.1',0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / 'results.json'
                args = ['--output',str(output),'--base-url',f'http://127.0.0.1:{server.server_port}',
                        '--delay','0','--batch-delay','0']
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(checker.main(args), 2)
                first = json.loads(output.read_text())
                self.assertEqual(len(first['results']), 4)
                self.assertEqual(first['results'][0]['attempts'][0]['status'], 'accepted')
                self.assertEqual(first['results'][-1]['attempts'][-1]['status'], 'http_error')
                self.assertNotIn('test_session', output.read_text())
                before_posts = sum(c[0]=='POST' for c in calls)
                failing['enabled'] = False
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(checker.main(['--resume',str(output),*args[2:]]), 0)
                self.assertEqual(sum(c[0]=='POST' for c in calls), before_posts + 1)
                resumed = json.loads(output.read_text())
                self.assertEqual(len(resumed['runs']), 2)
                self.assertEqual(resumed['results'][-1]['attempts'][-1]['status'], 'rejected')

                # Copy just one Python file next to the user's src/cards sample.
                # No repository modules or separate plan may be required.
                standalone = Path(temp) / 'standalone'
                (standalone / 'src/cards').mkdir(parents=True)
                shutil.copyfile(ROOT / 'dev/scripts/check_fipi_answers.py', standalone / 'src/check_fipi_answers.py')
                sample = checker.load_plan(checker.DEFAULT_PLAN)['checks'][0]['sourceSnapshot']
                (standalone / 'src/cards/card_005141.json').write_text(json.dumps(sample, ensure_ascii=False))
                completed = subprocess.run([
                    sys.executable, 'src/check_fipi_answers.py', '--base-url',
                    f'http://127.0.0.1:{server.server_port}', '--delay','0','--batch-delay','0',
                ], cwd=standalone, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                report_file, = (standalone / 'fipi-results').glob('*.json')
                standalone_report = json.loads(report_file.read_text())
                self.assertEqual(len(standalone_report['results']), 1)
                self.assertEqual(standalone_report['results'][0]['attempts'][0]['answer'], 'неизбежность')
                self.assertEqual(standalone_report['summary']['withAcceptedAnswer'], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_changed_snapshot_is_rejected(self):
        plan = copy.deepcopy(checker.load_plan(checker.DEFAULT_PLAN))
        plan['checks'][0]['sourceSnapshot']['html'] += 'changed'
        with self.assertRaisesRegex(ValueError, 'хешу'):
            checker.validate_plan(plan)

    def test_raw_essay_is_skipped_without_hypothesis_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'card_ABCDEF.json'
            path.write_text(json.dumps({
                'number':'ABCDEF', 'guid':'00000000000000000000000000000000',
                'html':'<p>Напишите <b>сочинение</b> по прочитанному тексту.</p>',
            }, ensure_ascii=False), encoding='utf-8')
            plan = checker.plan_from_cards(path, {'project':checker.PROJECT,'checks':[]})
            checker.validate_plan(plan)
            self.assertEqual(plan['checks'][0]['candidates'], [])
            self.assertEqual(plan['checks'][0]['skipReason'], 'essay_not_automatically_graded')


if __name__ == '__main__':
    unittest.main()
