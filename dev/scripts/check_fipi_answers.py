#!/usr/bin/env python3
"""Check only the explicit FIPI answer candidates in a plan; save evidence as JSON.

Uses the Python standard library. Does not enumerate answers, change cards or
save session cookies. Protocol: questions.php session, solve.php POST; 3=yes,
2=no. All candidates are explicit; a successful answer never changes application keys.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = Path(__file__).resolve().parent
_candidate_root = SCRIPT_DIR.parent.parent
ROOT = (_candidate_root if (_candidate_root / 'scripts/card_data.py').is_file()
        else Path.cwd())
IN_PROJECT = (ROOT / 'scripts/card_data.py').is_file()
DEFAULT_PLAN = ROOT / 'dev/data/answer_alternative_checks.json'
PROJECT = 'AF0ED3F2557F8FFC4C06F80B6803FD26'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_plan(path):
    return validate_plan(json.loads(path.read_text(encoding='utf-8')))


def validate_plan(plan):
    if plan.get('schemaVersion') != 1 or not re.fullmatch(r'[0-9a-fA-F]{32}', plan.get('project', '')):
        raise ValueError('Неверная версия плана или project')
    seen = set()
    if not plan.get('checks'):
        raise ValueError('План пуст')
    for check in plan['checks']:
        cid = check.get('cardId', '')
        if not re.fullmatch(r'[0-9A-F]{6}', cid) or cid in seen:
            raise ValueError('Неверный или повторный код: ' + cid)
        seen.add(cid)
        if not re.fullmatch(r'[0-9a-fA-F]{32}', check.get('guid', '')):
            raise ValueError('Неверный GUID: ' + cid)
        snapshot = check['sourceSnapshot']
        digest = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if digest != check['sourceContentSha256'] or snapshot['number'] != cid or snapshot['guid'] != check['guid']:
            raise ValueError('Исходник не соответствует хешу/GUID: ' + cid)
        answers = check.get('candidates', [])
        if not answers and not check.get('skipReason'):
            raise ValueError('Нет кандидатов или причины пропуска: ' + cid)
        wires = []
        for answer in answers:
            if not all(isinstance(answer.get(k), str) and answer[k].strip() for k in ['answer', 'wireAnswer']):
                raise ValueError('Ответ и wireAnswer должны быть непустыми строками: ' + cid)
            wires.append(answer['wireAnswer'])
        if len(set(wires)) != len(wires):
            raise ValueError('Повторные запросы в плане: ' + cid)
    return plan


def opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


class AnswerInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.checkboxes = 0
        self.textareas = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type', '').lower() == 'checkbox':
            self.checkboxes += 1
        if tag == 'textarea':
            self.textareas += 1


def options_count(card):
    options = card.get('variants') or []
    if len(options) == 1 and re.match(r'^\s*\d\)', str(options[0])):
        return len(re.findall(r'\d\)', options[0]))
    return len(options)


def wire_answer(card, answer):
    """Only explicit choice forms become masks; matching/sequences keep order."""
    if card.get('html'):
        inputs = AnswerInputs()
        inputs.feed(card['html'])
        count = inputs.checkboxes
    else:
        question = card.get('question', '').lower()
        choice = (card.get('answer_type') == 'bitmask' or 'словарной статьи' in question or
                  re.search(r'(?:укажите|запишите)\s+(?:все\s+)?(?:варианты|номера)', question))
        count = options_count(card) if choice and not (card.get('errors') and card.get('sentences')) else 0
    if not count:
        return answer
    if not answer.isdigit() or not set(answer) <= set('123456789') or len(set(answer)) != len(answer):
        raise ValueError('Для выбора вариантов нужен перечень номеров: ' + card['number'])
    if any(int(d) > count for d in answer):
        raise ValueError('Номер ответа вне числа вариантов: ' + card['number'])
    return ''.join('1' if str(i) in answer else '0' for i in range(1, count + 1))


def plan_from_cards(directory, seed_plan):
    """Accept raw {number,guid,html} or project JSON, without changing either."""
    seeds = {c['guid'].lower():c for c in seed_plan['checks']}
    project_cards = {}
    for path in (ROOT / 'data').glob('card_*.json'):
        card = json.loads(path.read_text(encoding='utf-8'))
        project_cards[card['guid'].lower()] = card
    checks = []
    paths = [directory] if directory.is_file() else sorted(directory.glob('card_*.json'))
    for path in paths:
        card = json.loads(path.read_text(encoding='utf-8'))
        cid = card['number']
        snapshot = {k:v for k,v in card.items() if k != 'explanation'}
        check = {'caseId':'BANK-' + cid,'cardId':cid,'guid':card['guid'],
                 'sourceSnapshot':snapshot,'sourceContentSha256':hashlib.sha256(
                     json.dumps(snapshot,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                 'mode':'find_accepted','candidates':[]}
        previous = project_cards.get(card['guid'].lower(), {})
        answer = (card.get('answer') or previous.get('answer') or '').strip()
        if answer:
            try:
                wire = wire_answer(card, answer)
                check['candidates'].append({'answer':answer,'wireAnswer':wire,'role':'existing_key_hypothesis'})
            except ValueError as error:
                check['encodingIssue'] = str(error)
        seed = seeds.get(card['guid'].lower())
        if seed is None and cid == '005141' and card['guid'].lower() == '025825474e8290034db847dc9562ae6c':
            seed = {'mode':'find_accepted', 'candidates':[
                {'answer':'неизбежность','wireAnswer':'неизбежность','role':'hypothesis'}]}
        if seed:
            check['mode'] = seed['mode']
            for candidate in seed['candidates']:
                candidate = {**candidate,'wireAnswer':wire_answer(card,candidate['answer'])}
                if candidate['wireAnswer'] not in {a['wireAnswer'] for a in check['candidates']}:
                    check['candidates'].append(candidate)
        if not check['candidates']:
            question = card.get('question', '').lower()
            inputs = AnswerInputs()
            inputs.feed(card.get('html', ''))
            essay = inputs.textareas or re.search(r'напишите\s+сочинение|сочинение-рассуждение', question)
            check['skipReason'] = ('essay_not_automatically_graded' if essay
                                   else 'hypotheses_not_prepared_yet')
        checks.append(check)
    if not checks:
        raise ValueError('В каталоге нет card_*.json: ' + str(directory))
    return {'schemaVersion':1,'project':seed_plan['project'],'checks':checks}


def response_info(response):
    raw = response.read(1048576)
    text = raw.decode('utf-8', errors='replace').strip()
    return {'httpStatus': response.status, 'response': text[:300],
            'responseSha256': hashlib.sha256(raw).hexdigest(),
            'status': 'accepted' if text == '3' else 'rejected' if text == '2' else 'unexpected_response'}


def check_answer(client, base_url, project, init_url, guid, answer, timeout):
    data = urllib.parse.urlencode({'guid': guid, 'answer': answer['wireAnswer'],
                                   'ajax': '1', 'proj': project}).encode('utf-8')
    request = urllib.request.Request(base_url + '/bank/solve.php', data=data, headers={
        'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest', 'Referer': init_url})
    result = {'time': now(), **answer}
    try:
        with client.open(request, timeout=timeout) as response:
            result.update(response_info(response))
    except urllib.error.HTTPError as error:
        result.update(response_info(error))
        result['status'] = 'http_error'
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        result.update(status='network_error', error=str(error))
    return result


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def summarize(plan, report):
    rows = report['results']
    report['summary'] = {
        'cardsInPlan': len(plan['checks']),
        'withAcceptedAnswer': sum(any(a['status']=='accepted' for a in r['attempts']) for r in rows),
        'withRequestError': sum(r['status']=='request_error' for r in rows),
        'notChecked': len(plan['checks']) - sum(bool(r['attempts']) for r in rows),
    }


class RequestPacer:
    def __init__(self, delay, batch_size, batch_delay, sleeper=time.sleep):
        self.delay = delay
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.sleeper = sleeper
        self.requests = 0

    def wait(self):
        if self.requests:
            if self.delay:
                self.sleeper(self.delay)
            if self.requests % self.batch_size == 0 and self.batch_delay:
                print(f'  Пауза между пачками: {self.batch_delay:g} с', flush=True)
                self.sleeper(self.batch_delay)
        self.requests += 1


def run(plan, client, base_url, timeout, pacer, report, output):
    init_url = base_url + '/bank/questions.php?' + urllib.parse.urlencode({
        'proj': plan['project'], 'page': '1', 'pagesize': '1'})
    run_info = report['runs'][-1]
    try:
        request = urllib.request.Request(init_url, headers={'User-Agent': 'Mozilla/5.0'})
        pacer.wait()
        run_info['requests'] = pacer.requests
        with client.open(request, timeout=timeout) as response:
            response.read(1048576)
            run_info['session'] = {'status': 'opened', 'httpStatus': response.status}
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        run_info['session'] = {'status': 'network_error', 'error': str(error)}
        report.update(status='connection_failed', finishedAt=now())
        summarize(plan, report)
        save_report(output, report)
        print('Банк недоступен. Это ошибка соединения, а не отказ в ответе.')
        return 2

    by_id = {r['cardId']:r for r in report['results']}
    consecutive_errors = 0
    for index, check in enumerate(plan['checks'], 1):
        result = by_id.get(check['cardId'])
        if result is None:
            result = {k: check[k] for k in ['caseId', 'cardId', 'guid', 'sourceContentSha256']}
            result.update(liveTextCompared=False,
                          mode=check.get('mode', 'find_accepted'), attempts=[])
            report['results'].append(result)
            by_id[check['cardId']] = result
        if not check.get('candidates'):
            result.update(status='not_checked', reason=check['skipReason'])
            continue
        prior = {a['wireAnswer']:a for a in result['attempts'] if a['status'] in {'accepted','rejected'}}
        stop_at_first = check.get('mode', 'find_accepted') != 'verify_alternatives'
        if stop_at_first and any(a['status']=='accepted' for a in prior.values()):
            continue
        pending = [a for a in check['candidates'] if a['wireAnswer'] not in prior]
        if not pending:
            continue
        print(f'[{index}/{len(plan["checks"])}] {check["cardId"]}', flush=True)
        for answer in pending:
            pacer.wait()
            outcome = check_answer(client, base_url, plan['project'], init_url, check['guid'], answer, timeout)
            result['attempts'].append(outcome)
            run_info['requests'] = pacer.requests
            label = {'accepted':'ПРИНЯТ','rejected':'НЕ ПРИНЯТ'}.get(outcome['status'],'ОШИБКА ЗАПРОСА')
            print(f'  {answer["answer"]!r}: {label}', flush=True)
            result['status'] = 'accepted' if any(a['status']=='accepted' for a in result['attempts']) else 'no_accepted_answer'
            save_report(output, report)
            if outcome['status'] in {'accepted','rejected'}:
                consecutive_errors = 0
            if outcome['status'] == 'accepted' and stop_at_first:
                break
            if outcome['status'] not in {'accepted','rejected'}:
                # Do not turn an unavailable endpoint into many false rejections.
                result['status'] = 'request_error'
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    report.update(status='stopped_after_request_errors', finishedAt=now())
                    summarize(plan, report)
                    save_report(output, report)
                    print('Три ошибки запросов подряд. Результат сохранён; продолжение через --resume.')
                    return 2
                break
    report.update(status='finished', finishedAt=now())
    run_info['requests'] = pacer.requests
    summarize(plan, report)
    save_report(output, report)
    return 2 if any(r['status']=='request_error' for r in report['results']) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--cards', type=Path, help='проверить все card_*.json из каталога; принимает сырой HTML или формат проекта')
    parser.add_argument('--answer', action='append', help='кандидат для одного JSON; параметр можно повторять')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--resume', type=Path, help='продолжить результат с тем же планом; принятые/отклонённые запросы не повторяются')
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--batch-delay', type=float, default=10)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--delay', type=float, default=0.5)
    parser.add_argument('--base-url', default='https://ege.fipi.ru', help='normally unchanged; local test server is supported')
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.delay < 0 or args.batch_size <= 0 or args.batch_delay < 0:
        parser.error('timeout и batch-size должны быть положительными; паузы — неотрицательными')
    try:
        if args.plan:
            plan = load_plan(args.plan)
        elif DEFAULT_PLAN.is_file():
            plan = load_plan(DEFAULT_PLAN)
        else:
            plan = {'schemaVersion':1,'project':PROJECT,'checks':[]}
            if args.cards is None:
                args.cards = next((p for p in [SCRIPT_DIR/'cards', Path.cwd()/'src/cards', Path.cwd()/'cards']
                                   if p.is_dir()), None)
        if args.cards:
            plan = validate_plan(plan_from_cards(args.cards, plan))
        if args.answer:
            if len(plan['checks']) != 1:
                raise ValueError('--answer используется с одним JSON, указанным через --cards')
            check = plan['checks'][0]
            check['mode'] = 'verify_alternatives'
            check['candidates'] = [{'answer':a,'wireAnswer':wire_answer(check['sourceSnapshot'],a),
                                    'role':'explicit_hypothesis'} for a in args.answer]
        plan = validate_plan(plan)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    plan_hash = hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    endpoint = args.base_url.rstrip('/') + '/bank/solve.php'
    if args.resume:
        if args.output:
            parser.error('Для --resume не задавайте --output: продолжается тот же файл')
        output = args.resume
        try:
            report = json.loads(output.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        if (report.get('schemaVersion') != 1 or report.get('planSha256') != plan_hash or
                report.get('endpoint') != endpoint or report.get('project') != plan['project']):
            parser.error('Результат относится к другому плану или серверу; смешивать их нельзя')
        report['status'] = 'running'
    else:
        output_dir = ROOT / ('dev/generated' if IN_PROJECT else 'fipi-results')
        output = args.output or output_dir / ('fipi-checks-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
        if output.exists():
            parser.error('Файл результата уже существует; используйте --resume или другое имя: ' + str(output))
        report = {'schemaVersion':1,'startedAt':now(),'status':'running','planSha256':plan_hash,
                  'project':plan['project'],'endpoint':endpoint,'results':[],'runs':[]}
    report['runs'].append({'startedAt':now(),'delay':args.delay,'batchSize':args.batch_size,
                           'batchDelay':args.batch_delay,'requests':0})
    save_report(output, report)
    pacer = RequestPacer(args.delay, args.batch_size, args.batch_delay)
    print(f'Карточек в плане: {len(plan["checks"])}; максимум ответов: {sum(len(c.get("candidates",[])) for c in plan["checks"])}')

    try:
        code = run(plan, opener(), args.base_url.rstrip('/'), args.timeout, pacer, report, output)
    except KeyboardInterrupt:
        report.update(status='interrupted', finishedAt=now())
        summarize(plan, report)
        save_report(output, report)
        code = 130
    print('Файл результата:', output.resolve())
    return code


if __name__ == '__main__':
    sys.exit(main())
