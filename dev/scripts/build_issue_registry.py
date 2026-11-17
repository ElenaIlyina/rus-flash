#!/usr/bin/env python3
"""Build the local issue index; source records are never rewritten."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ID = re.compile(r'(?<![0-9A-Za-z])[0-9A-F]{6}(?![0-9A-Za-z])')
RECORDS = []
SOURCES = set()


def add(source, title, text, status='История: статус требует сверки', cards=None, category='Замечание / вопрос'):
    SOURCES.add(source)
    RECORDS.append(dict(source=source, title=title, text=text, status=status,
                        cards=sorted(set(cards if cards is not None else ID.findall(text))), category=category))


def pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def build():
    # Markdown is retained verbatim in small sections / table rows, including old claims.
    docs = list((ROOT / 'dev/docs').rglob('*.md'))
    pattern = re.compile(r'issue|review|correction|approval|answer-check|disput|self-review|source|question|audit', re.I)
    for path in sorted(docs):
        if not pattern.search(path.name) or '/references/' in str(path):
            continue
        source = str(path.relative_to(ROOT))
        heading = path.stem
        block = []
        def flush():
            if block and any(line.strip() for line in block):
                add(source, heading, '\n'.join(block))
            block.clear()
        for line in path.read_text().splitlines():
            if line.startswith('#'):
                flush()
                heading = line.lstrip('# ').strip()
            elif line.startswith('|') and ID.search(line):
                flush()
                add(source, heading, line)
            else:
                block.append(line)
        flush()

    # Author-facing comparison tables, preserving their exact wording.
    from lxml import html as html_parser
    for name in ['dev/disagreements.html', 'dev/task-19-review.html']:
        document = html_parser.fromstring((ROOT / name).read_text())
        title = document.find('.//title')
        for row in document.xpath('//tr[td]'):
            add(name, title.text_content() if title is not None else name,
                ' | '.join(text.strip() for text in row.itertext() if text.strip()),
                category='Таблица разночтений')

    # Explicit issue lists and resolved records, rather than routine explanation rewrites.
    paths = ['dev/data/knowledge/review_issues.json',
             'dev/docs/content-audit/grammar-review-pending.json',
             'dev/docs/content-audit/task-19-review-pending.json',
             'dev/docs/content-audit/task-19-source-issues.json',
             'dev/docs/content-audit/card-edit-proposals.json',
             'dev/docs/content-audit/explanations-20-26-issues.json']
    for source in paths:
        data = json.loads((ROOT / source).read_text())
        for key in ['cards', 'resolved', 'proposals', 'resolvedAssignments', 'issues']:
            values = data.get(key, [])
            if isinstance(values, dict):
                values = [dict(value, cardId=card) for card, value in values.items()]
            for value in values:
                status = ('Решено' if key in ['resolved', 'resolvedAssignments'] or value.get('status') in ['applied', 'resolved_by_author', 'resolved']
                          else 'Открыто' if key == 'cards' or value.get('status') == 'open' else 'История: статус требует сверки')
                card = value.get('cardId', value.get('id', ''))
                add(source, value.get('issueId', card or 'Предложение'), pretty(value), status,
                    value.get('cardIds') or ([card] if re.fullmatch(r'[0-9A-F]{6}', card) else None))

    for name, key, status in [
        ('stress-dictionary-crosscheck.json', 'forms', 'Сверка источников зафиксирована'),
        ('punctuation-16-17-recheck.json', 'editorialCorrections', 'Исправлено при самопроверке')]:
        source = 'dev/docs/content-audit/' + name
        for value in json.loads((ROOT / source).read_text()).get(key, []):
            add(source, value.get('form', value.get('id', 'Сверка')), pretty(value), status)

    # Supplemental evidence and old queues remain linked, not asserted to be current issues.
    for folder in ['dev/docs/content-audit', 'dev/data']:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and path.suffix in ['.json', '.jsonl', '.md', '.csv'] and '/references/' not in str(path):
                if path.name != 'issue_registry.json' and (pattern.search(path.name) or 'fipi_pending' in path.name):
                    SOURCES.add(str(path.relative_to(ROOT)))

    # Every actual repair event is discoverable by card; hash-only bookkeeping is omitted.
    for name in ['raw-format-changes.jsonl', 'full-page-passage-changes.jsonl', 'card-content-issues.jsonl']:
        source = 'dev/docs/content-audit/' + name
        grouped = {}
        for line in (ROOT / source).read_text().splitlines():
            value = json.loads(line)
            if value.get('event') == 'coverage_hash_rebound':
                continue
            card = value.get('cardId')
            if not card:
                continue
            # Keep full original events in the linked journal, use readable metadata here.
            selected = {k: v for k, v in value.items() if k in
                        ['event', 'date', 'reason', 'description', 'fields', 'previousNotes', 'authorization']}
            grouped.setdefault(card, []).append(selected)
        for card, events in grouped.items():
            add(source, 'История восстановления / замечания ' + card, pretty(events),
                'История: статус требует сверки' if name == 'card-content-issues.jsonl' else 'Восстановление выполнено',
                [card], 'История восстановления')

    # Current state is shown independently from historical wording; it does not erase history.
    support_source = 'data/knowledge/card_support.json'
    support = json.loads((ROOT / support_source).read_text())['cards']
    for card, value in support.items():
        if value.get('explanationNeedsSourceReview'):
            note = value.get('explanationReviewNote', '')
            add(support_source, 'Объяснение требует сверки', str(note), 'Открыто', [card], 'Текущий статус')
    for path in sorted((ROOT / 'data').glob('card_*.json')):
        value = json.loads(path.read_text())
        if value.get('content_issue'):
            add(str(path.relative_to(ROOT)), 'Замечание к текущему условию', str(value['content_issue']),
                'Открыто', [path.stem[5:]], 'Текущий статус')
    source = 'dev/data/content_review_overrides.json'
    for card, value in json.loads((ROOT / source).read_text())['cards'].items():
        add(source, 'Ограничение проверки карточки', pretty(value), 'Открыто', [card], 'Текущий статус')

    # Cross-link every record for the two author-resolved questions without changing the quotation.
    resolutions = {
        'F22DF5': 'Решено автором: «не скрывал» и «обращался» — однородные сказуемые; придаточное относится к «не скрывал». Ключ 2356 сохранён, вариант 236 отозван.',
        '5D6C52': 'Решено автором: замечание о лишней кавычке снято; при совпадении вложенных кавычек число знаков само по себе не доказывает дефекта. Условие и ключ 14 сохранены.'}
    for index, record in enumerate(RECORDS, 1):
        record['id'] = f'REG-{index:05d}'
        record['resolution'] = '\n'.join(resolutions[c] for c in record['cards'] if c in resolutions)
        if len(record['cards']) == 1 and record['cards'][0] in resolutions:
            record['status'] = 'Решено'
    result = dict(schemaVersion=1, sources=sorted(SOURCES), records=RECORDS)
    (ROOT / 'dev/data/issue_registry.json').write_text(pretty(result) + '\n')
    template = (ROOT / 'dev/scripts/issue_registry_template.html').read_text()
    payload = json.dumps(result, ensure_ascii=False).replace('<', '\\u003c')
    (ROOT / 'dev/issues.html').write_text(template.replace('__DATA__', payload))
    print(f'{len(RECORDS)} records; {len(SOURCES)} sources')


if __name__ == '__main__':
    build()
