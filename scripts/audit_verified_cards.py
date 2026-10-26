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
from generate_manifest import classify, extract_codes, load_cards

ROOT = Path(__file__).resolve().parents[1]


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value))).strip()


def propose(card):
    """Use content before KES; return semantic group, candidate number, evidence, format."""
    q = plain(card['question']).lower()
    options = ' '.join(plain(str(v)).lower() for v in card['variants'])
    codes = set(extract_codes(card))
    old = classify(card)
    if 'отредактируйте предложение' in q and 'лексическ' in q:
        return 'lexical_editing', 6, 'Лексическое редактирование в формулировке', 'needs_format_review'
    if 'пароним' in q:
        return 'paronyms', 5, 'Исправление паронима в формулировке', 'needs_format_review'
    if 'ударени' in q or 'ударный гласный' in q:
        return 'stress', 4, 'Проверка ударения в формулировке', ('historical_format' if 'выпишите это слово' in q else 'needs_format_review')
    if 'образовании формы слова' in q or ('выделенных ниже слов' in q and 'грамматическая ошибка' in q):
        return 'word_forms', 7, 'Исправление формы слова', 'needs_format_review'
    if 'соответствие' in q and 'грамматическ' in q:
        return 'syntax_errors', 8, 'Соответствие ошибок и предложений', 'needs_format_review'
    if 'характеристик' in q and ('текста' in q or 'фрагмента' in q):
        return 'stylistic_analysis', 3, 'Характеристики текста; согласованный цикл прежних №1→3', 'needs_format_review'
    if 'словарной статьи' in q or ('пять слов' in q and 'лексическ' in q):
        return 'contextual_meaning', 2, 'Лексическое значение в контексте; прежний №3→2', ('historical_format' if 'словарной статьи' in q else 'needs_format_review')
    if 'на месте пропуска' in q and ('самостоятельно подберите' in q or 'должно стоять' in q):
        return 'missing_link_word', 1, 'Подбор пропущенного слова в тексте; прежний №2→1', ('historical_format' if 'самостоятельно' not in q else 'needs_format_review')
    if ('среди предложений' in q or 'среди предложении' in q) and 'с предыдущим' in q:
        return 'sentence_links', 26, 'Поиск связи предложений; номер требует внешней сверки', 'needs_format_review'
    if re.search(r'из предложени[йя].*выпишите', q):
        return 'text_vocabulary', 25, 'Извлечение лексической единицы из текста; номер требует внешней сверки', 'needs_format_review'
    if 'утвержден' in q and any(s in options for s in ['повествован', 'рассужден', 'описан']):
        return 'speech_types', 24, 'Типы речи/логика предложений видны в вариантах; номер требует внешней сверки', 'needs_format_review'
    if 'список терминов' in q or ('троп' in q and re.search(r'\(?а\)?\s*_', q)):
        return 'legacy_rhetorical_review', None, 'Рецензия с пропусками: нельзя переносить автоматически в новый формат', 'historical_format'
    if '3.7.5' in codes and '3.7.8' in codes:
        return 'verb_endings_participles', 12, 'КЭС суффиксов + окончаний; варианты содержат глагольные формы', ('historical_format' if 'выпишите слово' in q else 'needs_format_review')
    if codes == {'3.7.5'}:
        return 'suffixes', 11, 'КЭС суффиксов; без комбинированного КЭС окончаний', ('historical_format' if 'выпишите слово' in q else 'needs_format_review')
    if codes == {'3.7.4'}:
        return 'prefixes', 10, 'КЭС приставок', 'needs_format_review'
    if codes == {'3.7.2'}:
        return 'roots', 9, 'КЭС корня и орфографическая формулировка', ('historical_format' if 'определите слово' in q else 'needs_format_review')
    if old in {13, 15, 16, 17, 18, 20}:
        return f'candidate_group_{old}', old, 'Прежний КЭС и формулировка: требуется предметное подтверждение позиции', 'needs_manual_review'
    return 'unresolved', None, 'Недостаточно однозначных признаков: ручной разбор', 'needs_manual_review'


def answer_relation(card):
    answer, payload = card['answer'].strip(), card['answer_verify'].strip()
    if answer == payload:
        return 'same_string'
    if len(payload) > 1 and set(payload) <= {'0', '1'} and re.fullmatch('[1-9]+', answer):
        expected = ''.join(str(i + 1) for i, bit in enumerate(payload) if bit == '1')
        if ''.join(sorted(answer)) == expected and len(set(answer)) == len(answer):
            return 'equivalent_enum_bitmask'
    return 'needs_answer_format_review'


def inventory(cards):
    rows = []
    for card in cards:
        if not card.get('answer_verify', '').strip():
            continue
        group, candidate, reason, form = propose(card)
        rows.append({
            'id': card['number'], 'guid': card['guid'],
            'answer_status': 'historical_fipi_check_user_confirmed',
            'answer': card['answer'], 'answer_verify': card['answer_verify'],
            'answer_representation': answer_relation(card),
            'current_task': classify(card), 'semantic_group': group,
            'candidate_task': candidate,
            'position_status': 'pending_manual_and_official_2027_review',
            'reason': reason, 'format_status': form,
            'stored_answer_type': card.get('answer_type', ''),
            'explanation_status': 'missing' if not card['explanation'].strip() else 'pending_subject_review',
            'explanation_format': 'markdown_not_rendered' if re.search(r'\*\*[^*]+\*\*', card['explanation']) else 'html_or_plain',
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
           'Кандидаты позиций определены по формулировке, вариантам и КЭС. Для первых трёх заданий использован ранее согласованный цикл №3→2→1→3, но только после разделения смешанных тем. Остальные номера — рабочие кандидаты для предметной и официальной сверки. Официальный профиль ЕГЭ-2027 в этом аудите не получен. Ни одна позиция не помечена официально подтверждённой.', '',
           'Ответы, классификатор сайта и отображаемые группы этим аудитом **не изменены**. Исправления объяснений записаны отдельно в explanation-reviews.json. Отдельные статусы ответа, позиции, формата и объяснения нельзя объединять в один флаг «проверено».', '',
           '## Предложения по позициям', '',
           f'Для **{changes}** карточек предложен номер, отличный от текущего. Это кандидаты, а не {changes} доказанных ошибок нумерации ЕГЭ-2027.', '',
           '| Сейчас | Кандидат | Содержание | Карточек |', '|---|---|---|---|']
    for (old, new, group), n in sorted(counts.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0, x[0][2])):
        out.append(f'| {old} | {new if new is not None else "ручной разбор"} | {group} | {n} |')
    out += ['', '## Представление ответа', '',
            '| Проверка строк | Карточек |', '|---|---|']
    for kind, n in sorted(Counter(r['answer_representation'] for r in rows).items()):
        out.append(f'| {kind} | {n} |')
    out += ['', 'same_string — строки совпадают; equivalent_enum_bitmask — перечень номеров совпал с позициями единиц битмаски; needs_answer_format_review — отличие не объяснено этим правилом и требует проверки. Это не новая оценка правильности ответа.', '',
            '## Объяснения', '', f"Из {len(rows)} карточек объяснение есть у {sum(r['explanation_status'] != 'missing' for r in rows)}. Отсутствующие объяснения: " + ', '.join(r['id'] for r in rows if r['explanation_status'] == 'missing') + '.', '', 'Все объяснения ещё требуют предметного ревью. Исправления текущего этапа: [журнал](explanation-reviews.json). Markdown-звёздочки не интерпретируются нынешним HTML-рендерером; это отдельный дефект оформления, не признак неверного правила.', '', '## Как использовать реестр', '',
            '- [CSV всех карточек](verified-cards.csv): текущая группа, кандидат, основание, формат ответа, КЭС, фрагмент условия.',
            '- [JSON всех карточек](verified-cards.json): те же сведения и SHA-256 текущей исходной карточки для обнаружения последующих изменений.',
            '- Повторить: `python3 scripts/audit_verified_cards.py`. Генератор читает data/, пишет только этот каталог документации.',
            '- Сначала разобрать unresolved и legacy_rhetorical_review, а также места смешения типов речи, лексического редактирования и глагольных окончаний.',
            '- Затем подтвердить позиции и форматы по официальной спецификации/демоверсии нужного года. Старый формат можно сохранить как упражнение по навыку, не выдавая за точную экзаменационную форму.',
            '- Отдельно проверить смысловые выделения, полноту текста/вариантов и объяснения. Принятый сайтом ответ не подтверждает качество объяснения.',
            '- После предметной проверки выпустить отдельную таблицу соответствия ID → экзаменационная позиция с источником. Только затем менять отображение банка и выбирать учебный модуль.', '']
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/content-audit')
    args = parser.parse_args()
    cards = load_cards()
    rows = inventory(cards)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'verified-cards.json').write_text(json.dumps({'schemaVersion': 1, 'auditDate': '2026-10-27', 'examYear': 2027, 'officialMappingConfirmed': False, 'cards': rows}, ensure_ascii=False, indent=2) + '\n')
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]) if rows else [], lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    (args.output / 'verified-cards.csv').write_text('\ufeff' + buf.getvalue(), encoding='utf-8')
    (args.output / 'README.md').write_text(report(cards, rows))
    print(f'Audited {len(rows)} historical answer checks; outputs: {args.output}')


if __name__ == '__main__':
    main()
