"""Read the user-provided FB2 safely and index original, section-scoped paragraphs.

Only the .fb2 member is read; .url attachments and all external instructions are ignored.
No files are extracted from ZIP paths. The source archive is retained unchanged.
"""
import hashlib
import html
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

NS = {'f': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
XLINK = '{http://www.w3.org/1999/xlink}href'
PARTS = {'ОРФОГРАФИЯ': 'orthography', 'ПУНКТУАЦИЯ': 'punctuation'}


def content(node):
    return ''.join(node.itertext()).strip() if node is not None else ''


def inline(node):
    inside = html.escape(node.text or '')
    for child in node:
        inside += inline(child) + html.escape(child.tail or '')
    tag = node.tag.rsplit('}', 1)[-1]
    name = {'strong': 'strong', 'emphasis': 'em', 'sub': 'sub', 'sup': 'sup'}.get(tag)
    if tag == 'a' and node.get('type') == 'note':
        name = 'sup'
    return f'<{name}>{inside}</{name}>' if name else inside


def read_handbook(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.infolist() if m.filename.lower().endswith('.fb2')]
        if len(members) != 1 or members[0].file_size > 8 * 1024 * 1024:
            raise ValueError('Expected exactly one FB2 up to 8 MiB')
        raw = archive.read(members[0])
    if re.search(br'<!\s*(DOCTYPE|ENTITY)\b', raw, re.I):
        raise ValueError('DTD/entities are not supported')
    root = ET.fromstring(raw)
    publish = root.find('f:description/f:publish-info', NS)
    title = root.find('f:description/f:title-info', NS)
    metadata = {
        'id': 'lopatin-2007',
        'title': content(title.find('f:book-title', NS)),
        'authors': [content(a.find('f:last-name', NS)) + ' ' + content(a.find('f:first-name', NS)) + ' ' + content(a.find('f:middle-name', NS)) for a in title.findall('f:author', NS)],
        'editor': 'В. В. Лопатин',
        'publisher': content(publish.find('f:publisher', NS)),
        'year': content(publish.find('f:year', NS)),
        'isbn': content(publish.find('f:isbn', NS)),
        'archiveSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'fb2Sha256': hashlib.sha256(raw).hexdigest(),
        'provenance': 'user_provided_electronic_copy',
        'matchesFipi2020Edition': False,
        'printedPageAvailable': False,
    }
    if metadata['year'] != '2007' or metadata['isbn'] != '978-5-699-18553-5':
        raise ValueError('This importer profile expects the inspected 2007 edition')
    bodies = root.findall('f:body', NS)
    main = next(b for b in bodies if b.get('name') != 'notes')
    notes = {}
    for body in bodies:
        if body.get('name') == 'notes':
            for section in body.findall('.//f:section', NS):
                if section.get('id'):
                    notes[section.get('id')] = '<br>'.join(inline(p) for p in section.findall('.//f:p', NS))
    paragraphs = []
    for section in main.findall('f:section', NS):
        part_title = content(section.find('f:title', NS)).upper()
        part = PARTS.get(part_title)
        if not part:  # Preface and word/subject indices are NOT numbered source paragraphs.
            continue
        current = None
        title_nodes = {id(p) for title_node in section.findall('.//f:title', NS) for p in title_node.findall('.//f:p', NS)}
        for p in section.findall('.//f:p', NS):
            if id(p) in title_nodes: continue
            plain = content(p)
            match = re.match(r'^§\s*(\d+)\.', plain)
            if match:
                number = int(match[1])
                current = {'id': f'lopatin-2007-{part}-{number}', 'editionId': metadata['id'],
                           'part': part, 'partTitle': part_title.capitalize(), 'number': number,
                           'heading': plain[:200], 'blocks': [], 'noteIds': []}
                paragraphs.append(current)
            if current is not None:
                current['blocks'].append(inline(p))
                for link in p.findall('.//f:a', NS):
                    if link.get('type') == 'note':
                        note_id = link.get(XLINK, '').lstrip('#')
                        if note_id in notes and note_id not in current['noteIds']:
                            current['noteIds'].append(note_id)
        found = [p['number'] for p in paragraphs if p['part'] == part]
        expected = 219 if part == 'orthography' else 167
        if found != list(range(1, expected + 1)):
            raise ValueError(f'Missing/duplicate/out-of-order source paragraph in {part}')
    if len(paragraphs) != 386:
        raise ValueError('Expected 219 orthography + 167 punctuation paragraphs')
    for p in paragraphs:
        p['body'] = '<br><br>'.join(p.pop('blocks'))
        p['notes'] = [{'id': nid, 'body': notes[nid]} for nid in p.pop('noteIds')]
        p['textSha256'] = hashlib.sha256(p['body'].encode()).hexdigest()
    metadata['paragraphCounts'] = {'orthography': 219, 'punctuation': 167}
    return metadata, paragraphs


def apply_errata(paragraphs, entries):
    by_id = {p['id']: p for p in paragraphs}
    for entry in entries:
        paragraph = by_id[entry['sourceId']]
        if paragraph['body'].count(entry['original']) != 1:
            raise ValueError('Erratum context changed: ' + entry['id'])
        paragraph.setdefault('sourceTextSha256', paragraph['textSha256'])
        if entry['replacement'] is not None:
            paragraph['body'] = paragraph['body'].replace(entry['original'], html.escape(entry['replacement']))
            paragraph['textSha256'] = hashlib.sha256(paragraph['body'].encode()).hexdigest()
        paragraph.setdefault('editorialNotes', []).append(entry)
