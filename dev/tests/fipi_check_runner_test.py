"""Local protocol fixture: cookies, exact wire answers, pauses and resuming."""
import copy
from contextlib import redirect_stdout
import http.server
import io
import json
from pathlib import Path
import sys
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import check_fipi_answers as checker


class FipiCheckRunnerTest(unittest.TestCase):
    def test_alternative_queue_checks_every_candidate_and_preserves_existing_plans(self):
        plan = checker.load_plan(ROOT / 'dev/data/fipi_answer_variants.json')
        self.assertEqual(len(plan['checks']), 109)
        self.assertTrue(all(c['mode']=='verify_alternatives' for c in plan['checks']))
        lacquer = next(c for c in plan['checks'] if c['cardId']=='012CAB')
        self.assertTrue({'лакировочным','лаковым','лакировальным'} <= {c['answer'] for c in lacquer['candidates']})
        time = next(c for c in plan['checks'] if c['cardId']=='12BBAB')
        self.assertIn('потом', {c['answer'] for c in time['candidates']})
        self.assertNotIn('позже', {c['answer'] for c in time['candidates']})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'card_012CAB.json'
            path.write_text(json.dumps(lacquer['sourceSnapshot'],ensure_ascii=False),encoding='utf-8')
            selected = checker.validate_plan(checker.plan_from_cards(path,plan,alternatives_only=True))
            self.assertEqual(selected['checks'][0]['mode'],'verify_alternatives')
            self.assertEqual(selected['checks'][0]['candidates'],lacquer['candidates'])

    def test_new_batch_is_bound_to_snapshot_and_excludes_existing_keys(self):
        plan = checker.load_plan(ROOT / 'dev/data/fipi_new_hypotheses.json')
        self.assertEqual(len(plan['checks']), 438)
        self.assertEqual(set(checker.EMBEDDED_NEW_HYPOTHESES), {c['guid'].lower() for c in plan['checks']})
        for check in plan['checks']:
            self.assertNotIn(check['guid'].lower(), checker.EMBEDDED_ANSWERS)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            sample = plan['checks'][0]
            path = directory / ('card_' + sample['cardId'] + '.json')
            path.write_text(json.dumps(sample['sourceSnapshot'], ensure_ascii=False), encoding='utf-8')
            selected = checker.validate_plan(checker.plan_from_cards(directory, plan, new_only=True))
            self.assertEqual(selected['checks'][0]['candidates'], sample['candidates'])
            changed = dict(sample['sourceSnapshot'], html=sample['sourceSnapshot']['html'] + 'changed')
            path.write_text(json.dumps(changed, ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Изменился исходник'):
                checker.plan_from_cards(directory, plan, new_only=True)
    @unittest.skipUnless(shutil.which('openssl'), 'openssl required for local TLS fixture')
    def test_tls_certificate_failure_and_explicit_curl_k_equivalent(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'3')

        with tempfile.TemporaryDirectory() as temp:
            cert, key = Path(temp) / 'cert.pem', Path(temp) / 'key.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                            '-keyout',str(key),'-out',str(cert),'-days','1',
                            '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],
                           check=True, capture_output=True)
            server = http.server.ThreadingHTTPServer(('127.0.0.1',0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f'https://localhost:{server.server_port}'
            try:
                with self.assertRaises(urllib.error.URLError):
                    checker.opener().open(url, timeout=3)
                with checker.opener(insecure=True).open(url, timeout=3) as response:
                    self.assertEqual(response.read(), b'3')
                with checker.opener(ca_file=cert).open(url, timeout=3) as response:
                    self.assertEqual(response.read(), b'3')
            finally:
                server.shutdown()
                server.server_close()

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
                new_sample = checker.load_plan(ROOT / 'dev/data/fipi_new_hypotheses.json')['checks'][0]
                (standalone / ('src/cards/card_' + new_sample['cardId'] + '.json')).write_text(
                    json.dumps(new_sample['sourceSnapshot'], ensure_ascii=False), encoding='utf-8')
                new_output = standalone / 'new-results.json'
                completed = subprocess.run([
                    sys.executable, 'src/check_fipi_answers.py', '--cards','src/cards','--new-only',
                    '--output',str(new_output), '--base-url',
                    f'http://127.0.0.1:{server.server_port}', '--delay','0','--batch-delay','0',
                ], cwd=standalone, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                new_report = json.loads(new_output.read_text())
                self.assertEqual([r['cardId'] for r in new_report['results']], [new_sample['cardId']])
                variant = next(c for c in checker.load_plan(ROOT / 'dev/data/fipi_answer_variants.json')['checks']
                               if c['cardId']=='012CAB')
                (standalone / 'src/cards/card_012CAB.json').write_text(
                    json.dumps(variant['sourceSnapshot'],ensure_ascii=False),encoding='utf-8')
                variant_output = standalone / 'variant-results.json'
                completed = subprocess.run([
                    sys.executable,'src/check_fipi_answers.py','--cards','src/cards','--alternatives-only',
                    '--output',str(variant_output),'--base-url',f'http://127.0.0.1:{server.server_port}',
                    '--delay','0','--batch-delay','0',
                ],cwd=standalone,capture_output=True,text=True)
                self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
                variant_report = json.loads(variant_output.read_text())
                self.assertEqual(len(variant_report['results'][0]['attempts']),3)
                self.assertEqual(variant_report['summary']['withMultipleAcceptedStrings'],1)
                pending = next(c for c in checker.load_plan(ROOT / 'dev/data/fipi_pending_checks.json')['checks']
                               if c['cardId']=='D30EAB')
                (standalone / 'src/cards/card_D30EAB.json').write_text(
                    json.dumps(pending['sourceSnapshot'],ensure_ascii=False),encoding='utf-8')
                pending_output = standalone / 'pending-results.json'
                completed = subprocess.run([
                    sys.executable,'src/check_fipi_answers.py','--cards','src/cards','--pending-only',
                    '--output',str(pending_output),'--base-url',f'http://127.0.0.1:{server.server_port}',
                    '--delay','0','--batch-delay','0',
                ],cwd=standalone,capture_output=True,text=True)
                self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
                pending_report = json.loads(pending_output.read_text())
                self.assertEqual([r['cardId'] for r in pending_report['results']], [new_sample['cardId'],'D30EAB'])
                self.assertEqual(pending_report['previousReportSha256'],checker.PENDING_REPORT_SHA256)
                self.assertEqual(next(r for r in pending_report['results'] if r['cardId']=='D30EAB')['attempts'][0]['wireAnswer'],'01001')
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
