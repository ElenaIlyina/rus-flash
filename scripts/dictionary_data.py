"""Read pinned, published dictionary content; no editorial records or originals."""
import hashlib
import json
import re


def load_sources(root, registry):
    sources = {}
    for item in registry['sources']:
        sid = item['id']
        if not re.fullmatch(r'[a-z0-9-]+',sid) or sid in sources:
            raise ValueError('Invalid or duplicate source: '+sid)
        source = dict(item)
        path = (root/source['file']).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Source file checksum mismatch: '+sid)
        if source['format']=='articles':
            entries = json.loads(path.read_text())['entries']
            source['_entries'] = entries
            source['_by_id'] = {a['id']:a for a in entries}
            if len(source['_by_id'])!=len(entries):
                raise ValueError('Duplicate source article')
            for article in entries:
                if article['dictionaryId']!=sid or hashlib.sha256(article['text'].encode()).hexdigest()!=article['textSha256']:
                    raise ValueError('Source article checksum mismatch')
        elif source['format']!='pdf':
            raise ValueError('Unsupported source format: '+sid)
        sources[sid] = source
    return sources


def public_ref(ref, sources):
    source = sources.get(ref.get('dictionaryId'))
    if source is None or not ref.get('headword'):
        raise ValueError('Missing dictionary source/headword')
    if source['format']=='articles':
        article = source['_by_id'].get(ref.get('entryId'))
        if not article or article['headword']!=ref['headword']:
            raise ValueError('Missing dictionary article')
    elif type(ref.get('pdfPage')) is not int or not 1<=ref['pdfPage']<=source['pdfPages']:
        raise ValueError('Invalid PDF page')
    return {**{key:ref[key] for key in ('dictionaryId','headword','pdfPage','entryId') if key in ref},
            'label':source['citationLabel']}
