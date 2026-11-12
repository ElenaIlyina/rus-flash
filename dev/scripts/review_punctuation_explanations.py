#!/usr/bin/env python3
"""Validate manually reviewed task-16 sentences and reproduce their explanations."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import sys
import subprocess
import tarfile
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping
from handbook_fb2 import read_handbook
from review_grammar_explanations import digest, frozen

BASHKIROVA_URL = 'https://profcentr.ggtu.ru/images/documents/materials_vebinar/2023/november/2811Bashkirova.pdf#page=22'
PENDING_NOTE = 'Пунктуация одного предложения требует уточнения. Разбор по сохранённому ключу и альтернативное прочтение отмечены отдельно.'


def read_registry():
    return json.loads((ROOT / 'dev/data/knowledge/punctuation_card_reviews.json').read_text())


def external_sources(registry):
    allowed = {
        'bashkirova-2023-punctuation-commentary-22': (BASHKIROVA_URL, 'web_indexed_pdf_text_read', False, False),
        'fipi-selfprep-2023-punctuation-12': ('https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2023/rus_yaz_2023.pdf#page=12', 'pdf_page_text_and_image_read', True, True),
        'gramota-285111-object-infinitive': ('https://gramota.ru/spravka/vopros/285111', 'html_article_text_read', True, False),
        'gramota-332573-room-silence': ('https://gramota.ru/spravka/vopros/332573', 'html_article_text_read', True, False),
    }
    sources = {}
    for source in registry.get('externalSources', []):
        sid = source['id']
        if sid in sources or sid not in allowed:
            raise ValueError('Unknown or duplicate punctuation commentary')
        url, method, original, image = allowed[sid]
        if source['url'] != url or source['readMethod'] != method or source['originalFileAvailable'] is not original or source['pageImageRead'] is not image or digest(source['excerpt']) != source['excerptSha256']:
            raise ValueError('Commentary evidence or access limits changed')
        hash_fields = ('fileSha256', 'pageTextSha256') if method == 'pdf_page_text_and_image_read' else ('htmlSha256', 'articleTextSha256') if method == 'html_article_text_read' else ()
        if any(not re.fullmatch('[0-9a-f]{64}', source.get(field, '')) for field in hash_fields):
            raise ValueError('Incomplete commentary source fingerprints')
        if sid.endswith('-12') and source.get('pdfPage') != 12 or sid.endswith('-22') and source.get('pdfPage') != 22:
            raise ValueError('Wrong commentary PDF page')
        sources[sid] = source
    return sources


def punctuate(original, positions):
    if not isinstance(positions, list) or any(type(pos) is not int or not 0 < pos < len(original) or not original[pos].isspace() or original[pos - 1].isspace() for pos in positions) or positions != sorted(set(positions)):
        raise ValueError('Comma positions must be unique, ordered word boundaries')
    for pos in reversed(positions):
        original = original[:pos] + ',' + original[pos:]
    return original


def validate(card, review, paragraphs, external):
    if card['number'] != review['id'] or mapping(card)['task'] != 16 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Punctuation review does not match immutable source card')
    provenance = review['rewriteReview']
    if provenance['scope'] != 'all_five_original_sentences' or any(provenance.get(k) is not False for k in ('oldExplanationsUsedAsEvidence', 'independentTeacherAcceptance', 'answerUniquenessEstablished')):
        raise ValueError('Punctuation review scope or provenance changed')
    if len(card['variants']) != 5 or len(review['rows']) != 5 or not review['hint'].strip():
        raise ValueError('Expected all five sentences and an individual hint')
    key = card['answer']
    if not re.fullmatch(r'[1-5]+', key) or key != ''.join(sorted(set(key))):
        raise ValueError('Expected a unique, ordered selection key')
    verified = card['answer_verify']
    verified_key = ''.join(str(i) for i, bit in enumerate(verified, 1) if bit == '1') if re.fullmatch('[01]{5}', verified) else verified
    if verified_key != key:
        raise ValueError('Bitmask verification and saved answer disagree')
    evidence = review['paragraphEvidence']
    required = {sid for row in review['rows'] for sid in row['sourceIds']}
    if len({e['sourceId'] for e in evidence}) != len(evidence) or {e['sourceId'] for e in evidence} != required:
        raise ValueError('Missing or duplicate punctuation rule evidence')
    for entry in evidence:
        paragraph = paragraphs.get(entry['sourceId'])
        if paragraph is None or paragraph['part'] != 'punctuation' or paragraph['textSha256'] != entry['textSha256'] or entry['method'] != 'paragraph_text_read':
            raise ValueError('Stale or unrelated punctuation paragraph')
    selected, pending, corrected = [], [], []
    for i, (original, row) in enumerate(zip(card['variants'], review['rows']), 1):
        if row['number'] != i or digest(original) != row['sourceVariantSha256'] or not row['structure'].strip() or not row['reason'].strip() or not row['sourceIds'] or len(set(row['sourceIds'])) != len(row['sourceIds']):
            raise ValueError('Sentence index, text, explanation or source changed')
        text = punctuate(original, row['commaPositions'])
        corrected.append(text)
        if text.count(',') == 1:
            selected.append(str(i))
        if row['status'] == 'interpretation_pending':
            pending.append(i)
            alternative = punctuate(original, row['alternativeCommaPositions'])
            if alternative == text or not row['alternativeReason'].strip():
                raise ValueError('Unresolved interpretation needs a concrete alternative')
        elif row['status'] != 'source_supported' or 'alternativeCommaPositions' in row:
            raise ValueError('Unknown punctuation review status')
        if len(set(row.get('externalSourceIds', []))) != len(row.get('externalSourceIds', [])) or any(sid not in external for sid in row.get('externalSourceIds', [])):
            raise ValueError('Unknown or duplicate external commentary')
        ext_evidence = row.get('externalSourceEvidence', [])
        expected_ext = set(row.get('externalSourceIds', []))
        if len({e['sourceId'] for e in ext_evidence}) != len(ext_evidence) or {e['sourceId'] for e in ext_evidence} != expected_ext:
            raise ValueError('Missing external commentary evidence')
        for entry in ext_evidence:
            source = external[entry['sourceId']]
            if entry['excerptSha256'] != source['excerptSha256'] or entry['method'] != source['readMethod']:
                raise ValueError('Stale external commentary evidence')
    if ''.join(selected) != key:
        raise ValueError('Reviewed comma counts do not match the preserved key')
    if bool(pending) != review['sourceReviewPending'] or review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Unresolved punctuation status lost')
    return corrected


def clean(text):
    return html.escape(re.sub(r'\s+', ' ', text).strip())


def render(card, review, paragraphs, external):
    corrected = validate(card, review, paragraphs, external)
    blocks = []
    for row, text in zip(review['rows'], corrected):
        count = text.count(',')
        count_label = {0:'запятых нет', 1:'одна запятая', 2:'две запятые', 3:'три запятые'}.get(count, f'запятых: {count}')
        verdict = 'подходит' if count == 1 else 'не подходит'
        note = ' — прочтение требует уточнения' if row['status'] == 'interpretation_pending' else ''
        block = f'<b>Предложение {row["number"]} — {count_label}; {verdict}{note}.</b><br>{clean(row["structure"])}<br>{clean(row["reason"])}<br>Правильно: {clean(text)}'
        if row['status'] == 'interpretation_pending':
            alternative = punctuate(card['variants'][row['number'] - 1], row['alternativeCommaPositions'])
            block += '<br>Альтернативное прочтение: ' + clean(row['alternativeReason']) + '<br>Возможное исправление: ' + clean(alternative)
        blocks.append(block)
    return 'Для выбора нужно ровно по одной запятой в каждом подходящем предложении.<br><br>' + '<br><br>'.join(blocks)


def public_external_refs(review, external):
    return [{'part':row['number'], 'sourceId':sid, 'label':external[sid].get('citationLabel', 'Башкирова · ГГТУ, 2023 · PDF-с. 22'), 'url':external[sid]['url']} for row in review['rows'] for sid in row.get('externalSourceIds', [])]


def coverage_report(registry, paragraphs, external):
    baseline = registry['baselineCommit']
    archive = subprocess.check_output(['git', 'archive', baseline, 'data'], cwd=ROOT)
    expected = {r['id'] for r in registry['cards']}
    catalog = {c['id']:c for c in json.loads((ROOT / 'html/assets/data/catalog.json').read_text())['cards']}
    changed, total, stable = set(), 0, 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as files:
        for member in files:
            if not member.name.startswith('data/card_') or not member.name.endswith('.json'):
                continue
            before = json.load(files.extractfile(member))
            after = json.loads((ROOT / member.name).read_text())
            if frozen(before) != frozen(after):
                raise ValueError('FIPI input or key changed: '+after['number'])
            total += 1
            if before['explanation'] != after['explanation']:
                changed.add(after['number'])
            if mapping(before)['task'] in range(1, 16):
                basis = {'card':before, 'position':mapping(before), 'assessmentPolicy':'responses-v1'}
                version = max(2, int(digest(json.dumps(basis, sort_keys=True, ensure_ascii=False))[:8], 16))
                if before != after or catalog[before['number']]['materialVersion'] != version:
                    raise ValueError('Previously prepared card or progress version changed')
                stable += 1
    other_ids = set()
    for filename in ('isolation_card_reviews.json', 'introductory_card_reviews.json', 'subordination_card_reviews.json'):
        path = ROOT / 'dev/data/knowledge' / filename
        if path.is_file():
            other_ids.update(r['id'] for r in json.loads(path.read_text())['cards'])
    if total != 2140 or stable != 1145 or changed != expected | other_ids:
        raise ValueError('Punctuation batch differs from its declared scope')
    task_cards = []
    for path in (ROOT / 'data').glob('card_*.json'):
        card = json.loads(path.read_text())
        if mapping(card)['task'] == 16:
            task_cards.append(card['number'])
    rows = []
    for review in registry['cards']:
        card = json.loads((ROOT / f'data/card_{review["id"]}.json').read_text())
        rendered = render(card, review, paragraphs, external)
        if rendered != card['explanation']:
            raise ValueError('Punctuation explanation is stale')
        corrected = validate(card, review, paragraphs, external)
        rows.append({'id':review['id'], 'sourceContentSha256':review['sourceContentSha256'], 'explanationSha256':digest(rendered), 'answer':card['answer'], 'answerVerifyBitmask':card['answer_verify'], 'commaCounts':[text.count(',') for text in corrected], 'sourceReviewPending':review['sourceReviewPending']})
    return {'reviewDate':registry['reviewDate'], 'baselineCommit':baseline, 'task':16, 'taskCards':len(task_cards), 'freshlyReviewedCards':len(rows), 'sentencesReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(set(task_cards)-expected), 'preservedConditionsAndKeys':total, 'unchangedTask1To15CardsAndProgressVersions':stable, 'independentTeacherAcceptance':False, 'pendingCards':[r['id'] for r in rows if r['sourceReviewPending']], 'sources':['Лопатин (ред.), Эксмо, 2007: пунктуация §§25–29, 37, 38, 40, 112, 127', 'И. А. Башкирова, ГГТУ, 2023: PDF-с. 22, прочитан индексированный текст; изображение страницы и локальная копия PDF недоступны', 'ФИПИ, рекомендации по самоподготовке к ЕГЭ-2023: текст и изображение с. 12', 'Грамота, ответ №332573 от 18.05.2026: прочитаны вопрос и ответ', 'Грамота, ответ №285111: прочитан ответ об инфинитиве при другом субъекте'], 'cards':rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    registry = read_registry()
    external = external_sources(registry)
    _, paragraphs = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
    paragraphs = {p['id']:p for p in paragraphs}
    log_path = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(log_path.read_text())
    writes = []
    for review in registry['cards']:
        path = ROOT / f'data/card_{review["id"]}.json'
        card = json.loads(path.read_text())
        explanation = render(card, review, paragraphs, external)
        if card.get('explanation', '') == explanation:
            continue
        if not args.write:
            raise ValueError('Punctuation explanation differs from manual review: ' + review['id'])
        before = digest(card.get('explanation', ''))
        if before != review['previousExplanationSha256']:
            raise ValueError('Previous punctuation explanation changed outside the review')
        card['explanation'] = explanation
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2)+'\n'))
        log['reviews'].append({'changeId':'PUNCTUATION16-'+review['id'], 'id':review['id'], 'reviewer':'assistant', 'reviewDate':review['reviewDate'], 'status':review['status'], 'reason':'Заново разобраны все пять исходных предложений: структура, точные места и количество запятых, правила и подсказка. Условие и оба исходных ключа, включая битовую маску answer_verify, сохранены.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(explanation)})
    if args.write and writes:
        writes.append((log_path, json.dumps(log, ensure_ascii=False, indent=2)+'\n'))
        snapshots = {p:p.read_bytes() for p, _ in writes}
        try:
            for path, text in writes:
                path.write_text(text)
        except OSError:
            for path, data in snapshots.items():
                path.write_bytes(data)
            raise
    if args.report:
        report = coverage_report(registry, paragraphs, external)
        (ROOT / 'dev/docs/content-audit/task-16-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(f'Punctuation task 16: {len(registry["cards"])} cards / {sum(len(r["rows"]) for r in registry["cards"])} sentences checked; updated {len(writes)-1 if writes else 0}')


if __name__ == '__main__':
    main()
