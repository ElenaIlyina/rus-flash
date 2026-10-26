#!/usr/bin/env python3
"""Offline inventory of historically FIPI-checked answers and candidate task positions.

Does not query FIPI, change source cards, or change the runtime classifier.
Position candidates are NOT an officially verified EGE-2027 mapping.
"""
import argparse
import csv
import hashlib
import html
import io
import json
from collections import Counter
from pathlib import Path
import re
from generate_manifest import classify, load_cards
from exam_2027 import mapping

ROOT = Path(__file__).resolve().parents[1]


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value))).strip()


def answer_relation(card):
    answer, payload = card['answer'].strip(), card['answer_verify'].strip()
    if answer == payload:
        return 'same_string'
    if len(payload) > 1 and set(payload) <= {'0', '1'} and re.fullmatch('[1-9]+', answer):
        expected = ''.join(str(i + 1) for i, bit in enumerate(payload) if bit == '1')
        if ''.join(sorted(answer)) == expected and len(set(answer)) == len(answer):
            return 'equivalent_enum_bitmask'
    return 'needs_answer_format_review'


def explanation_check(card):
    if not card['explanation'].strip():
        return 'missing'
    match = re.match(r'Верно:\s*(.*?)(?:\.|$)', plain(card['explanation']))
    if not match:
        return 'not_machine_checked'
    head = match.group(1)
    pairs = re.findall(r'([АБВГД])\s*[–—-]\s*(\d+)', head)
    if len(pairs) == 5 and [p[0] for p in pairs] == list('АБВГД'):
        claimed = ''.join(p[1] for p in pairs)
    elif re.fullmatch(r'(?:ряды?\s+)?[\d,\sи–—-]+', head):
        claimed = ''.join(re.findall(r'\d+', head))
    else:
        return 'not_machine_checked'
    return 'header_matches_answer' if claimed == card['answer'].strip() else 'header_conflicts_with_answer'


def inventory(cards):
    rows = []
    for card in cards:
        if not card.get('answer_verify', '').strip():
            continue
        position = mapping(card)
        group, candidate, reason, form = position['basis'], position['task'], position['basis'], position['formatStatus']
        rows.append({
            'id': card['number'], 'guid': card['guid'],
            'answer_status': 'historical_fipi_check_user_confirmed',
            'answer': card['answer'], 'answer_verify': card['answer_verify'],
            'answer_representation': answer_relation(card),
            'current_task': classify(card), 'semantic_group': group,
            'candidate_task': candidate,
            'position_status': position['mappingStatus'],
            'reason': reason, 'format_status': form,
            'stored_answer_type': card.get('answer_type', ''),
            'explanation_status': 'missing' if not card['explanation'].strip() else 'pending_subject_review',
            'explanation_header_check': explanation_check(card),
            'explanation_format': 'markdown_supported' if re.search(r'\*\*[^*]+\*\*', card['explanation']) else 'html_or_plain',
            'kes': ' | '.join(card.get('kes', [])),
            'question_excerpt': plain(card['question'])[:320],
            'source_sha256': hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        })
    return rows


def report(cards, rows):
    counts = Counter((r['current_task'], r['candidate_task'], r['semantic_group']) for r in rows)
    changes = sum(r['candidate_task'] is not None and r['candidate_task'] != r['current_task'] for r in rows)
    out = ['# Аудит карточек с ранее проверенными ответами', '',
           'Дата: **27.10.2026**. Проверка карточек выполнена офлайн; solve.php не запрашивался.', '',
           '## Границы подтверждения', '',
           f'В банке {len(cards)} карточек; у **{len(rows)}** заполнен answer_verify. Владелец подтвердил, что ответы ранее проверялись запросами к сайту ФИПИ. Этот набор — отправная точка работы, а не новый результат сетевой проверки.', '',
           'В JSON не сохранены время запроса, исходный ответ solve.php и хеш тогдашнего условия. GUID и answer_verify сохранены. Исторические сведения о проверках есть в [fipi_notes.md](../../fipi_notes.md), в том числе 71 соответствие и 48 словарных статей. answer_verify — проверочная строка, не boolean-флаг и не номер задания.', '',
           'Сопоставления позиций определены по формулировке, вариантам и КЭС. Для первых трёх заданий использован ранее согласованный цикл №3→2→1→3, но только после разделения смешанных тем. Остальные номера — рабочие кандидаты для предметной и официальной сверки. Официальный проект профиля получен и прочитан: см. [таблицу позиций](../ege-2027-card-mapping.md). Сопоставление каждой карточки выполнено алгоритмом; это не полное предметное ревью всех условий.', '',
           'Ответы не изменены. Отображаемые группы пересобираются по официальному проекту-2027; столбец current_task в реестре фиксирует прежнюю классификацию для сравнения. Исправления объяснений записаны отдельно в explanation-reviews.json. Отдельные статусы ответа, позиции, формата и объяснения нельзя объединять в один флаг «проверено».', '',
           '## Изменения позиций', '',
           f'Для **{changes}** карточек предложен номер, отличный от текущего. Это число изменённых назначений, включая пересмотр первых трёх групп; не показатель качества всех материалов.', '',
           '| Прежняя группа | Позиция по проекту-2027 | Основание | Карточек |', '|---|---|---|---|']
    for (old, new, group), n in sorted(counts.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0, x[0][2])):
        out.append(f'| {old} | {new if new is not None else "ручной разбор"} | {group} | {n} |')
    out += ['', '## Представление ответа', '',
            '| Проверка строк | Карточек |', '|---|---|']
    for kind, n in sorted(Counter(r['answer_representation'] for r in rows).items()):
        out.append(f'| {kind} | {n} |')
    out += ['', 'same_string — строки совпадают; equivalent_enum_bitmask — перечень номеров совпал с позициями единиц битмаски; needs_answer_format_review — отличие не объяснено этим правилом и требует проверки. Это не новая оценка правильности ответа.', '',
            '## Объяснения', '', f"Из {len(rows)} карточек объяснение есть у {sum(r['explanation_status'] != 'missing' for r in rows)}. Отсутствующие объяснения: " + ', '.join(r['id'] for r in rows if r['explanation_status'] == 'missing') + '.', '', 'Все объяснения ещё требуют предметного ревью. Исправления текущего этапа: [журнал](explanation-reviews.json). Markdown-выделения теперь поддержаны безопасным рендерером; преобразование не делает само объяснение предметно проверенным.', '', 'Проверка заголовков объяснений (это только соответствие заявленных номеров/пар эталону, не проверка правил): ' + str(dict(Counter(r['explanation_header_check'] for r in rows))) + '.', '', '## Как использовать реестр', '',
            '- [CSV всех карточек](verified-cards.csv): текущая группа, кандидат, основание, формат ответа, КЭС, фрагмент условия.',
            '- [JSON всех карточек](verified-cards.json): те же сведения и SHA-256 текущей исходной карточки для обнаружения последующих изменений.',
            '- Повторить: `python3 scripts/audit_verified_cards.py`. Генератор читает data/, пишет только этот каталог документации.',
            '- Сначала разобрать historical_main_information и rhetorical_review_old_format, а также места смешения типов речи, лексического редактирования и глагольных окончаний.',
            '- Затем провести предметную проверку сопоставлений и форматов по сохранённому официальному проекту. Старый формат можно сохранить как упражнение по навыку, не выдавая за точную экзаменационную форму.',
            '- Отдельно проверить смысловые выделения, полноту текста/вариантов и объяснения. Принятый сайтом ответ не подтверждает качество объяснения.',
            '- Реестр изменений всех 2140 карточек хранится в position-changes.jsonl; старые формы помечены отдельно. Только после предметной приёмки модуль можно использовать в исследовании.', '']
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/content-audit')
    args = parser.parse_args()
    cards = load_cards()
    rows = inventory(cards)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'verified-cards.json').write_text(json.dumps({'schemaVersion': 1, 'auditDate': '2026-10-27', 'examYear': 2027, 'officialSourceStatus': 'official_fipi_draft', 'cards': rows}, ensure_ascii=False, indent=2) + '\n')
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else [], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    (args.output / 'verified-cards.csv').write_text('\ufeff' + buf.getvalue(), encoding='utf-8')
    changes = []
    for card in cards:
        mapped = mapping(card)
        if mapped['task'] != classify(card):
            changes.append({'changeId': 'MAP-' + card['number'], 'date': '2026-10-27',
                'cardId': card['number'], 'where': 'generated catalog: task',
                'before': classify(card), 'after': mapped['task'],
                'why': mapped['basis'], 'formatStatus': mapped['formatStatus'],
                'source': 'docs/ege-2027-card-mapping.md',
                'sourceStatus': 'official_fipi_draft', 'subjectReview': 'pending'})
    (args.output / 'position-changes.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in changes))
    (args.output / 'README.md').write_text(report(cards, rows))
    print(f'Audited {len(rows)} historical answer checks; outputs: {args.output}')


if __name__ == '__main__':
    main()
