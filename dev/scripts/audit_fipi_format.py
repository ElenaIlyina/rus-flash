#!/usr/bin/env python3
"""Audit/restore question presentation from the pinned FIPI qblock archive.

No network, answer changes or reconstruction of absent shared passages.
Raw HTML is parsed as data; only a small presentation allowlist is emitted.
"""
import argparse
import copy
import hashlib
import html as entities
import json
from pathlib import Path
import re
import zipfile

from lxml import html

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT/'dev/docs/references/fipi-bank-2026-10-29/source.zip'
ARCHIVE_SHA256 = '4db6fcbc9c6bf55afcd649a15a54a03405373d47f58f94d295c641fe90d23bb2'
REPORT = ROOT/'dev/docs/content-audit/raw-format-audit.json'
LOG = ROOT/'dev/docs/content-audit/raw-format-changes.jsonl'
KEEP = {'b','strong','i','em','u','sub','sup'}
BLOCK = {'p','div','table','tr','td','li'}
DROP = {'script','style','input','textarea','select','iframe','object'}
FIELDS = ('question','variants','errors','sentences')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def plain(value):
    return html.fragment_fromstring(value or '',create_parent='div').text_content()


def visible(value):
    return re.sub(r'\s+','',plain(value))


def escape_text(value):
    return entities.escape(re.sub(r'\s+',' ',value or ''),quote=False)


def markup(node):
    if not isinstance(node.tag,str) or node.tag in DROP:
        return ''
    body = escape_text(node.text) + ''.join(
        markup(child)+escape_text(child.tail) for child in node)
    if node.tag == 'br':
        return '\n'
    if node.tag in KEEP:
        return f'<{node.tag}>{body}</{node.tag}>'
    if node.tag in BLOCK:
        return '\n'+body+'\n'
    return body


def clean(node):
    # Word's indentation is not a paragraph. Preserve p/br/table-row boundaries,
    # while keeping safe inline formatting and literal angle brackets escaped.
    value = markup(node).replace('\xa0',' ')
    value = re.sub(r'[ \t\r\f\v]+',' ',value)
    value = re.sub(r' *\n *','\n',value)
    value = re.sub(r'\n{2,}','\n',value).strip()
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r'<(b|strong|i|em|u|sub|sup)>\s*</\1>','',value)
    return value.strip()


def remove(node):
    parent = node.getparent()
    if node.tail:
        previous = node.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + node.tail
        else:
            parent.text = (parent.text or '') + node.tail
    parent.remove(node)


def snapshots():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Raw archive checksum mismatch')
    with zipfile.ZipFile(ARCHIVE) as archive:
        cards = [json.loads(archive.read(name)) for name in sorted(archive.namelist())
                 if re.fullmatch(r'src/cards/card_[0-9A-Fa-f]{6}\.json',name)]
    if len(cards)!=2140 or len({c['number'] for c in cards})!=2140 or len({c['guid'].lower() for c in cards})!=2140:
        raise ValueError('Unexpected source inventory')
    return {c['number']:c for c in cards}


def extract(raw):
    tree = html.fragment_fromstring(raw['html'],create_parent='div')
    cells = tree.xpath('.//td[@class="cell_0"]')
    if len(cells)!=1:
        raise ValueError('Expected one question cell: '+raw['number'])
    guids = tree.xpath('.//input[@name="guid"]/@value')
    if not guids or any(g.lower()!=raw['guid'].lower() for g in guids):
        raise ValueError('Embedded GUID mismatch: '+raw['number'])
    cell = copy.deepcopy(cells[0])
    result = {'question':'','variants':[]}
    choice_tables = tree.xpath('.//table[@class="distractors-table"]')
    if len(choice_tables)>1:
        raise ValueError('Ambiguous answer list')
    if choice_tables:
        rows = choice_tables[0].xpath('./tr[contains(concat(" ",normalize-space(@class)," ")," active-distractor ")]')
        for index,row in enumerate(rows,1):
            parts = row.findall('td')
            inputs = row.xpath('.//input[@type="checkbox"]/@value')
            if len(parts) not in {2,3} or inputs!=[str(index)]:
                raise ValueError('Option order mismatch: '+raw['number'])
            result['variants'].append(clean(parts[-1]))
        if not result['variants'] or not all(visible(v) for v in result['variants']):
            raise ValueError('Empty source option: '+raw['number'])
    elif 'ГРАММАТИЧЕСКИЕ ОШИБКИ' in cell.text_content():
        groups = {}
        for table in cell.xpath('.//table'):
            rows = table.findall('tr')
            parts = [r.findall('td') for r in rows]
            if not rows or not all(len(p)==2 for p in parts):
                continue
            labels = [re.sub(r'\s+','',p[0].text_content()) for p in parts]
            if labels == ['А)','Б)','В)','Г)','Д)']:
                groups['errors'] = (table,[clean(p[1]) for p in parts])
            if labels == [str(i)+')' for i in range(1,10)]:
                groups['sentences'] = (table,[clean(p[1]) for p in parts])
        if set(groups)!={'errors','sentences'}:
            raise ValueError('Incomplete grammar matching columns: '+raw['number'])
        for key,(table,values) in groups.items():
            result[key] = values
            remove(table)
        for heading in cell.xpath('.//td'):
            if heading.text_content().strip() in {'ГРАММАТИЧЕСКИЕ ОШИБКИ','ПРЕДЛОЖЕНИЯ'}:
                heading.clear()
    else:
        # FIPI's short-answer lists (paronyms, stress, forms, older spelling)
        # are source tables, not checkboxes. Keep each source row separately.
        lists = []
        for table in cell.xpath('.//table'):
            rows = table.findall('tr')
            parts = [row.findall('td') for row in rows]
            if len(rows)>=2 and all(len(p) in {2,3} and not p[0].text_content().strip() for p in parts):
                if any(len(p)==3 and re.sub(r'\s+','',p[1].text_content())!=str(i)+')' for i,p in enumerate(parts,1)):
                    raise ValueError('Static list order mismatch: '+raw['number'])
                lists.append((table,[clean(p[-1]) for p in parts]))
        if len(lists)>1:
            raise ValueError('Ambiguous static lists: '+raw['number'])
        if lists:
            table,result['variants'] = lists[0]
            if not all(visible(v) for v in result['variants']):
                raise ValueError('Empty static option: '+raw['number'])
            remove(table)
    result['question'] = clean(cell)
    if not visible(result['question']):
        raise ValueError('Empty question: '+raw['number'])
    return result


def inspect(card, raw):
    if card['number']!=raw['number'] or card['guid'].lower()!=raw['guid'].lower():
        raise ValueError('Card identity mismatch')
    proposed = extract(raw)
    changes,issues = {},[]
    for key,new in proposed.items():
        old = card.get(key,[] if key!='question' else '')
        if '\ufffd' in json.dumps(new,ensure_ascii=False):
            source_text = ' | '.join(plain(v) for v in new) if isinstance(new,list) else plain(new)
            index = source_text.index('\ufffd')
            issues.append({'field':key,'kind':'source_replacement_character',
                           'sourceFragment':source_text[max(0,index-60):index+61],
                           'sourceFieldSha256':digest(new),'retainedFieldSha256':digest(old),
                           'action':'retained_current_field','reason':'Raw source contains U+FFFD; do not replace readable text with a damaged character or guess its value.'})
            continue
        if old!=new:
            changes[key] = {'before':old,'after':new}
    return proposed,changes,issues


def rebind_support(changed, log_entries):
    # Preserve explanations/reviews; explicitly record which source hash was
    # rebound after a source-backed presentation repair, never a new subject review.
    for name in ('prefix_card_reviews','root_card_reviews','ege_1_6_card_reviews','task_7_card_reviews'):
        path = ROOT/f'dev/data/knowledge/{name}.json'
        book = json.loads(path.read_text())
        touched = False
        for entry in book['cards']:
            cid = entry['id']
            if cid not in changed:
                continue
            card = json.loads((ROOT/f'data/card_{cid}.json').read_text())
            frozen = digest({k:v for k,v in card.items() if k!='explanation'})
            prior = entry.get('sourceContentSha256')
            if prior == frozen:
                continue
            entry['sourceContentSha256'] = frozen
            entry.setdefault('sourceFormatSync',[]).append({'sourceArchiveSha256':ARCHIVE_SHA256,
                'previousSourceContentSha256':prior,'sourceContentSha256':frozen,
                'correctionLog':'dev/docs/content-audit/raw-format-changes.jsonl',
                'subjectReviewRepeated':False})
            log_entries.append({'event':'support_hash_rebound','cardId':cid,'file':str(path.relative_to(ROOT)),
                               'before':prior,'after':frozen,'reason':'Source-backed presentation repair; explanation unchanged; not a new subject review.'})
            touched = True
        if touched:
            path.write_text(json.dumps(book,ensure_ascii=False,indent=2)+'\n')



def rebind_coverage(changed, log_entries):
    for path in sorted((ROOT/'dev/docs/content-audit').glob('task-*.json')):
        book = json.loads(path.read_text())
        touched = []
        def update(value):
            if isinstance(value,dict):
                cid = value.get('id') or value.get('cardId')
                if cid in changed and 'sourceContentSha256' in value:
                    card = json.loads((ROOT/f'data/card_{cid}.json').read_text())
                    fresh = digest({k:v for k,v in card.items() if k!='explanation'})
                    if fresh != value['sourceContentSha256']:
                        prior = value['sourceContentSha256']
                        value['sourceContentSha256'] = fresh
                        value['formatSyncPreviousSourceContentSha256'] = prior
                        touched.append(cid)
                        log_entries.append({'event':'coverage_hash_rebound','cardId':cid,
                            'file':str(path.relative_to(ROOT)),'before':prior,'after':fresh,
                            'reason':'Source-backed presentation repair, not a new subject review.'})
                for child in list(value.values()):
                    update(child)
            elif isinstance(value,list):
                for child in value:
                    update(child)
        update(book)
        if touched:
            book['formatSyncEvidence'] = str(REPORT.relative_to(ROOT))
            path.write_text(json.dumps(book,ensure_ascii=False,indent=2)+'\n')


def run(apply=False, check=False):
    sources = snapshots()
    cards = {p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
    if set(cards)!=set(sources):
        raise ValueError('Project/source ID inventories differ')
    rows,entries,changed = [],[],set()
    for cid in sorted(cards):
        card,raw = cards[cid],sources[cid]
        proposed,changes,issues = inspect(card,raw)
        row = {'cardId':cid,'guid':card['guid'],'rawSourceContentSha256':digest(raw),
               'sourceFields':list(proposed),'differentFields':list(changes),'issues':issues,
               'sharedPassage':('not_in_qblock_not_compared' if card.get('text') else 'not_present_in_project'),
               'status':'source_damaged_field_retained' if issues else 'differs' if changes else 'matches'}
        if changes and apply:
            before = digest(card)
            before_protected = digest({k:v for k,v in card.items() if k not in FIELDS})
            for key,change in changes.items():
                card[key] = change['after']
            (ROOT/f'data/card_{cid}.json').write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
            changed.add(cid)
            entries.append({'event':'raw_format_restored','date':'2026-10-29','cardId':cid,
                'sourceArchiveSha256':ARCHIVE_SHA256,'rawSourceContentSha256':digest(raw),
                'beforeCardSha256':before,'afterCardSha256':digest(card),
                'beforeNonPresentationSha256':before_protected,
                'afterNonPresentationSha256':digest({k:v for k,v in card.items() if k not in FIELDS}),
                'fields':changes,
                'reason':'Restore FIPI question/list structure and meaningful formatting from pinned raw qblock. No answer, explanation, KES, GUID or shared-passage changes.',
                'answersUnchanged':True,'sharedPassageUnchanged':True})
            row['restoredFields'] = row.pop('differentFields')
            row['status'] = 'source_damaged_field_retained' if issues else 'restored'
        rows.append(row)
    report = {'schemaVersion':1,'sourceArchive':str(ARCHIVE.relative_to(ROOT)),
              'sourceArchiveSha256':ARCHIVE_SHA256,'sharedPassagesCompared':False,
              'summary':{'cards':len(rows),'differingCards':sum(bool(r.get('differentFields')) for r in rows),
                         'restoredCards':len(changed),'sourceDamagedCards':sum(bool(r['issues']) for r in rows),
                         'sharedPassagesNotCompared':sum(r['sharedPassage']=='not_in_qblock_not_compared' for r in rows)},'cards':rows}
    if check:
        if report['summary']['differingCards']:
            raise ValueError('Source presentation differs: '+str(report['summary']))
    else:
        if apply:
            rebind_support(changed,entries)
            rebind_coverage(changed,entries)
            if entries:
                with LOG.open('a') as output:
                    for entry in entries:
                        output.write(json.dumps(entry,ensure_ascii=False)+'\n')
        if not apply or changed or not REPORT.exists():
            REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False))
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--check',action='store_true')
    args = parser.parse_args()
    run(args.apply,args.check)
