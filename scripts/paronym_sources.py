"""Validate pinned dictionaries and explicit article evidence before publication."""
import hashlib
import json
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
        validated = dict(source)
        if source.get('articlesFile'):
            article_path = (root / source['articlesFile']).resolve()
            if not article_path.is_relative_to(root.resolve()):
                raise ValueError('Dictionary articles must be inside the project')
            if hashlib.sha256(article_path.read_bytes()).hexdigest() != source['articlesSha256']:
                raise ValueError('Dictionary article extraction changed: ' + sid)
            articles = json.loads(article_path.read_text())['entries']
            validated['_articles'] = {a['id']: a for a in articles}
            if len(validated['_articles']) != len(articles):
                raise ValueError('Duplicate dictionary article ID')
            for article in articles:
                if article['dictionaryId'] != sid or hashlib.sha256(article['text'].encode()).hexdigest() != article['textSha256']:
                    raise ValueError('Invalid extracted dictionary article')
        sources[sid] = validated
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
        if not source:
            raise ValueError('Missing dictionary')
        if not ref.get('headword') or not ref.get('definitionQuote'):
            raise ValueError('Dictionary reference needs a headword and evidence quote')
        if source.get('format') == 'mobi':
            article = source['_articles'].get(ref.get('entryId'))
            if not article or article['headword'] != ref['headword']:
                raise ValueError('Missing electronic dictionary article')
            if ' '.join(ref['definitionQuote'].split()) not in ' '.join(article['text'].split()):
                raise ValueError('Evidence quote does not occur in dictionary article')
            if ref.get('verificationMethod') != 'electronic_article_read':
                raise ValueError('Electronic dictionary article needs reading')
        else:
            page = ref.get('pdfPage')
            if type(page) is not int or not 1 <= page <= source['pdfPages']:
                raise ValueError('Invalid PDF page')
            method = ref.get('verificationMethod')
            if method not in {'visual_page_read', 'embedded_font_text_read', 'electronic_pdf_text_read'}:
                raise ValueError('Paronym article needs reading in this PDF copy')
            if method != 'visual_page_read':
                article = source.get('_articles', {}).get(ref.get('evidenceId'))
                if not article or article['headword'] != ref['headword'] or article['pdfPage'] != page:
                    raise ValueError('Missing PDF article evidence')
                if ' '.join(ref['definitionQuote'].split()) not in ' '.join(article['text'].split()):
                    raise ValueError('Evidence quote does not occur in recovered PDF article')


def publication_ready(review, sources):
    entry = review.get('dictionaryReview', {})
    if entry.get('status') != 'verified':
        return False
    validate_references(entry.get('sourceRefs'), sources)
    return True
