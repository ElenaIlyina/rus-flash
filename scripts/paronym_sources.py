"""Validate explicit, page-based evidence before publishing paronym explanations."""
import hashlib
import re


def validate_sources(book, root):
    sources = {}
    for source in book.get('sources', []):
        sid = source['id']
        if not re.fullmatch(r'[a-z0-9-]+', sid) or sid in sources:
            raise ValueError('Invalid or duplicate dictionary source: ' + sid)
        path = (root / source['sourceFile']).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Dictionary source must be inside the project')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('Dictionary source checksum changed: ' + sid)
        sources[sid] = source
    for pair in book['pairs']:
        if pair.get('reviewStatus') == 'verified':
            if len(pair['words']) < 2:
                raise ValueError('Paronym comparison needs at least two words')
            for word in pair['words']:
                validate_references(word.get('dictionaryRefs'), sources)
    return sources


def validate_references(refs, sources):
    if not refs:
        raise ValueError('Verified paronym explanation needs dictionary articles')
    for ref in refs:
        source = sources.get(ref.get('dictionaryId'))
        page = ref.get('pdfPage')
        if not source or type(page) is not int or not 1 <= page <= source['pdfPages']:
            raise ValueError('Missing dictionary or invalid PDF page')
        if not ref.get('headword') or not ref.get('definitionQuote'):
            raise ValueError('Dictionary reference needs a headword and evidence quote')
        if ref.get('verificationMethod') != 'visual_page_read':
            raise ValueError('Paronym article needs visual verification of this PDF copy')


def publication_ready(review, sources):
    entry = review.get('dictionaryReview', {})
    if entry.get('status') != 'verified':
        return False
    validate_references(entry.get('sourceRefs'), sources)
    return True
