"""Content-first mapping to the official FIPI 2027 DRAFT, appendix pp. 17–19.

A subject match does not certify the answer, explanation, or current exam format.
"""
import html
import re
from generate_manifest import extract_codes


def text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value))).strip().lower()


def mapping(card):
    q = text(card['question'])
    v = ' '.join(text(str(x)) for x in card.get('variants', []))
    codes = set(extract_codes(card))
    task, basis = None, 'manual_review'
    legacy = False
    if 'главная информация' in q:
        return {'task': None, 'basis': 'historical_main_information', 'mappingStatus': 'historical_without_exact_current_position', 'formatStatus': 'historical_format'}
    if 'напишите сочинение' in q or 'сочинение-рассуждение' in q:
        task, basis = 27, 'essay_instruction'
    elif 'соответствие' in q and 'грамматическ' in q:
        task, basis = 8, 'grammar_matching'
    elif 'список терминов' in q or ('троп' in q and re.search(r'\(?а\)?\s*_', q)):
        task, basis, legacy = 22, 'rhetorical_review_old_format', True
    elif 'соответствие' in q and any(x in q for x in ['выразительн', 'средств', 'термин']):
        task, basis = 22, 'expressive_means_matching'
    elif 'одним и тем же правилом' in q:
        task, basis = 21, 'same_punctuation_rule'
    elif 'пароним' in q:
        task, basis = 5, 'paronym_instruction'
    elif 'отредактируйте' in q and 'лексическ' in q:
        task, basis = 6, 'lexical_editing'
    elif 'ударени' in q or 'ударный гласный' in q:
        task, basis = 4, 'stress_instruction'
        legacy = 'выпишите это слово' in q
    elif 'образовании формы слова' in q or ('выделенных ниже слов' in q and 'грамматическая ошибка' in q):
        task, basis = 7, 'word_form_instruction'
    elif 'характеристик' in q and ('текста' in q or 'фрагмента' in q):
        task, basis = 3, 'stylistic_characteristics'
    elif 'словарной статьи' in q or ('пять слов' in q and 'лексическ' in q):
        task, basis = 2, 'contextual_meaning'
        legacy = 'словарной статьи' in q
    elif 'на месте пропуска' in q and ('самостоятельно подберите' in q or 'должно стоять' in q):
        task, basis = 1, 'missing_link_word'
        legacy = 'самостоятельно' not in q
    elif 'среди предложений' in q and 'с предыдущим' in q:
        task, basis = 26, 'sentence_links'
    elif re.search(r'из предложени[йя].*выпишите', q):
        task, basis = 25, 'lexical_extraction'
    elif 'утвержден' in q and any(x in v for x in ['повествован', 'рассужден', 'описан']):
        task, basis = 24, 'speech_types_in_options'
    elif ('соответств' in q and 'содержан' in q) or ('утвержден' in q and '1.4' in codes):
        task, basis = 23, 'text_content'
    elif '3.7.5' in codes and '3.7.8' in codes:
        task, basis = 12, 'verb_suffixes_and_endings'
    else:
        candidates = set()
        code_tasks = {'3.2.3':4, '3.7.2':9, '3.7.3':10, '3.7.4':10,
                      '3.7.5':11, '3.7.6':15, '3.7.7':13, '3.7.8':12,
                      '3.7.9':14, '3.8.1':21, '3.8.4':16, '3.8.5':17,
                      '3.8.6':18, '3.8.7':19, '3.8.8':20, '1.3':24, '1.4':23}
        for code in codes:
            if code in code_tasks: candidates.add(code_tasks[code])
        if 'одну запятую' in q:
            task, basis = 16, 'one_comma_instruction'
        elif len(candidates) == 1:
            task, basis = candidates.pop(), 'kes_supported'
    if task in {9, 11, 12} and ('выпишите слово' in q or 'определите слово' in q):
        legacy = True
    if task is None:
        status = 'needs_manual_review'
    else:
        status = 'content_mapped_to_official_draft'
    return {'task': task, 'basis': basis, 'mappingStatus': status,
            'formatStatus': 'historical_format' if legacy else 'format_requires_review'}
