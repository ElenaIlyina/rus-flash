#!/usr/bin/env python3
"""Generate html/card_*.html from data/card_*.json (single source of truth).

Usage:
    python3 scripts/regen_cards_html.py            # regen all cards
    python3 scripts/regen_cards_html.py 015A7C     # regen a single card by id
    python3 scripts/regen_cards_html.py --check    # verify existing cards match generation (no writes)

The template reproduces the currently deployed card layout byte-for-byte
(except the historical unclosed <div class="card"> bug, which is fixed here
 by closing the div before </body>).
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
HTML_DIR = os.path.join(ROOT, 'html', 'cards')

def render_variants(variants: list, variants_type: str):
    """Render variants[] to a "Варианты ответа:" block.

    Both default/"options" and "sentences" render the same list of .variant
    blocks (sentences are just whole-sentence entries). Empty entries are
    preserved, matching legacy behaviour. Returns a tuple (variants_html,
    sentences) where sentences is kept for backward-compat and always empty.
    """
    raw = [str(v).replace('\r\n', '\n') for v in variants]
    if not raw:
        return '', []
    rows = '\n'.join(f'            <div class="variant">{v}</div>' for v in raw)
    html = f'<div class="variants">\n{rows}\n        </div>'
    return html, []


def _flatten_bitmask_variants(variants):
    if len(variants) == 1 and re.search(r'^\s*\d\)', variants[0]):
        parts = re.split(r'(?=\d\))', variants[0].strip())
        out = []
        for p in parts:
            p = re.sub(r'^\s*\d\)\s*\xa0?\s*', '', p).strip()
            if p:
                out.append(p)
        return out
    return variants


def render_interactive(correct_ans_js, answer_type, variants, variants_html):
    if answer_type.strip().lower() == 'bitmask' and variants:
        variants = _flatten_bitmask_variants(variants)
        chk_lines = []
        for i, v in enumerate(variants, start=1):
            chk_lines.append(
                f'        <label class="bitmask-opt"><input type="checkbox" class="bitmask-cb" value="{i}">'
                f' <span>{v}</span></label>')
        bitmask_variants = ("<div class=\"variants bitmask-box\">\n"
                            + "\n".join(chk_lines) + "\n        </div>")
        return bitmask_variants, f"""
    <!-- Interactive Answer Check (bitmask checkboxes) -->
    <div style="margin-top: 20px; padding: 15px; background: #f1f8ff; border: 1px solid #c8e1ff; border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <span style="font-weight: bold; font-size: 14px; color: #0366d6;">Отметьте все верные варианты:</span>
            <button onclick="checkBitmask()" style="padding: 6px 14px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;">Проверить</button>
            <span id="checkFeedback" style="font-size: 14px; font-weight: bold;"></span>
        </div>
    </div>
    <script>
        const correctAns = {correct_ans_js};
        function checkBitmask() {{
            let tBtn = document.getElementById('toggleBtn');
            if (tBtn) {{
                tBtn.removeAttribute('disabled');
                tBtn.style.opacity = '1';
                tBtn.style.cursor = 'pointer';
            }}
            let picked = [];
            document.querySelectorAll('.bitmask-cb:checked').forEach(function(cb) {{
                picked.push(cb.value);
            }});
            picked.sort(function(a,b) {{ return a - b; }});
            let val = picked.join('');
            let fb = document.getElementById('checkFeedback');
            if (!val) {{
                fb.style.color = '#d73a49';
                fb.innerText = '⚠️ Отметьте хотя бы один вариант';
                return;
            }}
            if (!correctAns) {{
                fb.style.color = '#e36209';
                fb.innerText = '⚠️ Ответ для этого задания еще не занесен в базу.';
                if (tBtn) {{
                    tBtn.removeAttribute('disabled');
                    tBtn.style.opacity = '1';
                    tBtn.style.cursor = 'pointer';
                }}
                return;
            }}
            if (val === correctAns) {{
                fb.style.color = '#28a745';
                fb.innerText = '🟢 Верно! Отличная работа.';
                try {{
                    let data = JSON.parse(localStorage.getItem('task_tags_' + taskNum) || '{{}}');
                    if (!data.solved) {{
                        data.solved = true;
                        localStorage.setItem('task_tags_' + taskNum, JSON.stringify(data));
                        if (typeof loadTags === 'function') loadTags();
                        window.dispatchEvent(new StorageEvent('storage', {{key: 'task_tags_' + taskNum, newValue: JSON.stringify(data)}}));
                    }}
                }} catch(e) {{}}
            }} else {{
                fb.style.color = '#d73a49';
                fb.innerText = '🔴 Неверно. Попробуйте еще раз.';
            }}
        }}
    </script>
    <!-- /Interactive Answer Check -->"""
    return variants_html, f"""
    <!-- Interactive Answer Check -->
    <div style="margin-top: 20px; padding: 15px; background: #f1f8ff; border: 1px solid #c8e1ff; border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <label style="font-weight: bold; font-size: 14px; color: #0366d6;">Ваш ответ:</label>
            <input type="text" id="userAnswerInput" placeholder="Например: 123 или корысть" style="padding: 6px 10px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; width: 180px;">
            <button onclick="checkAnswerLocally()" style="padding: 6px 14px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold;">Проверить</button>
            <span id="checkFeedback" style="font-size: 14px; font-weight: bold;"></span>
        </div>
    </div>
    <script>
        const correctAns = {correct_ans_js};
        function checkAnswerLocally() {{
            let tBtn = document.getElementById('toggleBtn');
            if (tBtn) {{
                tBtn.removeAttribute('disabled');
                tBtn.style.opacity = '1';
                tBtn.style.cursor = 'pointer';
            }}
            let val = document.getElementById('userAnswerInput').value.trim().toLowerCase();
            let fb = document.getElementById('checkFeedback');
            if (!val) {{
                fb.style.color = '#d73a49';
                fb.innerText = '⚠️ Введите ответ';
                return;
            }}
            if (!correctAns) {{
                fb.style.color = '#e36209';
                fb.innerText = '⚠️ Ответ для этого задания еще не занесен в базу.';
                if (tBtn) {{
                    tBtn.removeAttribute('disabled');
                    tBtn.style.opacity = '1';
                    tBtn.style.cursor = 'pointer';
                }}
                return;
            }}
            if (val === correctAns) {{
                fb.style.color = '#28a745';
                fb.innerText = '🟢 Верно! Отличная работа.';
                try {{
                    let data = JSON.parse(localStorage.getItem('task_tags_' + taskNum) || '{{}}');
                    if (!data.solved) {{
                        data.solved = true;
                        localStorage.setItem('task_tags_' + taskNum, JSON.stringify(data));
                        if (typeof loadTags === 'function') loadTags();
                        window.dispatchEvent(new StorageEvent('storage', {{key: 'task_tags_' + taskNum, newValue: JSON.stringify(data)}}));
                    }}
                }} catch(e) {{}}
            }} else {{
                fb.style.color = '#d73a49';
                fb.innerText = '🔴 Неверно. Попробуйте еще раз.';
            }}
        }}
    </script>
    <!-- /Interactive Answer Check -->"""


def build_html(card: dict) -> str:
    tid = (card.get('number') or '').strip().upper()
    guid = card.get('guid', '')
    kes_list = card.get('kes') or []
    question = (card.get('question') or '').replace('\r\n', '\n')
    text = (card.get('text') or '').replace('\r\n', '\n').strip()
    variants = [(v or '').replace('\r\n', '\n') for v in (card.get('variants') or [])]
    variants_type = card.get('variants_type') or ''
    answer_type = card.get('answer_type') or ''
    explanation = (card.get('explanation') or '').strip()
    ans = (card.get('answer') or '').strip().lower()
    ans_show = (card.get('answer') or '').strip()

    kes_html = "<br>".join(f"<strong>КЭС:</strong> {k}" for k in kes_list)

    variants_html, _ = render_variants(variants, variants_type)

    text_html = ""
    if text:
        text_paras = "\n".join(f"            <p>{p}</p>" for p in text.split('\n') if p.strip())
        text_html = f"""<div class="text-block">
            <h3>Текст для чтения:</h3>
{text_paras}
        </div>"""

    errors = [(e or '').replace('\r\n', '\n') for e in (card.get('errors') or [])]
    sentences = [(s or '').replace('\r\n', '\n') for s in (card.get('sentences') or [])]
    labels_cyr = 'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'

    instruction = ''
    if errors and sentences:
        if 'ГРАММАТИЧЕСКИЕ ОШИБКИ' in question:
            cut = question.find('ГРАММАТИЧЕСКИЕ ОШИБКИ')
            instruction = (question[:cut]).strip().strip('\xa0')
        elif question.strip().startswith('Установите соответствие'):
            i = question.find('столбца.')
            if i >= 0:
                instruction = (question[:i + len('столбца.')]).strip().strip('\xa0')
        if len(instruction) < 15:
            instruction = ''

    if errors and sentences:
        err_rows = "".join(
            f"            <tr valign=\"top\"><td width=\"0\">{labels_cyr[i]})</td>"
            f"<td width=\"100%\">{e}</td></tr>\n"
            for i, e in enumerate(errors))
        sent_rows = "".join(
            f"            <tr valign=\"top\"><td width=\"0\">{j+1})</td>"
            f"<td width=\"100%\">{sn}</td></tr>\n"
            for j, sn in enumerate(sentences))
        match_html = f"""<div class="match-table">
            <table width="100%" border="0" cellspacing="0" cellpadding="2">
                <tr valign="top">
                    <td width="40%" class="match-head">ГРАММАТИЧЕСКИЕ ОШИБКИ</td>
                    <td width="60%" class="match-head">ПРЕДЛОЖЕНИЯ</td>
                </tr>
                <tr valign="top">
                    <td width="40%" class="match-col"><table cellpadding="3">
{err_rows}        </table></td>
                    <td width="60%" class="match-col"><table cellpadding="3">
{sent_rows}        </table></td>
                </tr>
            </table>
        </div>"""
    else:
        match_html = ""

    if ans:
        btn_attrs = f"  style=\"opacity: 1; cursor: pointer;\""
        ans_h3 = f"Правильный ответ: {ans_show}"
    else:
        btn_attrs = " disabled style=\"opacity: 0.5; cursor: not-allowed;\""
        ans_h3 = "Правильный ответ: Ответ не указан"

    if match_html:
        if instruction:
            question_html = f"""<div class="question">
            {instruction}
        </div>"""
        else:
            question_html = "        <!-- вопрос заменён таблицей соответствия -->"
    else:
        question_html = f"""<div class="question">
            {question}
        </div>"""

    if explanation:
        expl_html = f"            <p>{explanation}</p>"
    else:
        expl_html = "            <p><em>Объяснение к этому заданию готовится.</em></p>"

    correct_ans_js = json.dumps(ans, ensure_ascii=True)

    variants_html, interactive_html = render_interactive(
        correct_ans_js, answer_type, variants, variants_html)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Задание ФИПИ № {tid} (С ответом)</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 10px; background: #f9f9f9; color: #333; }}
        .card {{ background: #fff; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }}
        h1 {{ display: inline-block; background: #e3f2fd; color: #0d47a1; font-size: 17px; padding: 4px 12px; border-radius: 6px; margin: 0; }}
        .badge {{ background: #e0f7fa; color: #006064; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .question {{ font-weight: bold; margin: 15px 0; background: #FAFBCA; padding: 10px; border-left: 4px solid #fbc02d; line-height: 1.6; }}
        .task-instruction {{ margin-bottom: 8px; }}
        .text-block {{ margin: 15px 0; background: #f3f8ff; padding: 12px 14px; border-left: 4px solid #1976d2; line-height: 1.7; border-radius: 4px; }}
        .text-block h3 {{ margin-top: 0; color: #1976d2; font-size: 14px; }}
        .text-block p {{ margin: 8px 0; }}
        .meta {{ font-size: 14px; color: #555; margin-top: 15px; }}
        .variants {{ margin-left: 20px; margin-top: 10px; }}
        .variant {{ margin: 8px 0; line-height: 1.4; }}
        .bitmask-box {{ margin-left: 0; }}
        .bitmask-opt {{ display: flex; align-items: center; gap: 8px; margin: 8px 0; line-height: 1.4; cursor: pointer; }}
        .bitmask-opt input {{ cursor: pointer; }}
        .match-table {{ margin: 15px 0; border: 1px solid #bbb; border-collapse: collapse; }}
        .match-table table {{ border-collapse: collapse; }}
        .match-head {{ background: #FAFBCA; font-weight: bold; text-decoration: underline; padding: 6px; border: 1px solid #ccc; }}
        .match-col {{ padding: 6px; vertical-align: top; border: 1px solid #ccc; }}
        .match-col td {{ padding: 3px 6px; line-height: 1.5; }}
        .match-col td[width="0"] {{ white-space: nowrap; font-weight: bold; }}
        
        .toggle-btn {{ background: #1976d2; color: white; border: none; padding: 10px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; margin-top: 15px; }}
        .toggle-btn:hover {{ background: #115293; }}
        
        .answer-box {{ margin-top: 15px; background: #e8f5e9; padding: 15px; border-left: 4px solid #4caf50; border-radius: 4px; display: none; }}
        .answer-box h3 {{ margin-top: 0; color: #2e7d32; }}
        .meta {{ display: none; }}
    </style>
    <script>
        function toggleAnswer() {{
            var box = document.getElementById('answerBox');
            var btn = document.getElementById('toggleBtn');
            if (box.style.display === 'none' || box.style.display === '') {{
                box.style.display = 'block';
                btn.innerText = 'Скрыть ответ и объяснение';
            }} else {{
                box.style.display = 'none';
                btn.innerText = 'Показать ответ и объяснение';
            }}
        }}
    </script>
</head>
<body>
    <div class="card">
        <h1>{tid}</h1>
        <div class="meta">
            <p><strong>GUID:</strong> {guid}</p>
            <p>{kes_html}</p>
        </div>
        {text_html}
        {question_html}
        {match_html}
        {variants_html}
        {interactive_html}
    
    <button id="toggleBtn" class="toggle-btn" onclick="toggleAnswer()"{btn_attrs}>Показать ответ и объяснение</button>

        <div id="answerBox" class="answer-box">
            <h3>{ans_h3}</h3>
            <p><strong>Подробное объяснение:</strong></p>
{expl_html}
        </div>

    <!-- Local Tags System (parent is source of truth) -->
    <div style="margin-top: 25px; padding-top: 15px; border-top: 1px solid #eee; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <span style="font-size: 13px; font-weight: bold; color: #555;">Метки:</span>
        <button id="tagFav" onclick="toggleTag('fav')" style="padding: 6px 12px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 13px;">⭐ В избранное</button>
        <button id="tagSolved" onclick="toggleTag('solved')" style="padding: 6px 12px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 13px;">✅ Решено</button>
        <button id="tagHard" onclick="toggleTag('hard')" style="padding: 6px 12px; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 13px;">⚠️ Повторить</button>
    </div>
    <script>
        let currentData = {{}};

        function getTaskNum() {{
            let h1 = document.querySelector('h1');
            if (h1) {{
                let m = h1.innerText.match(/№\\s*([A-Za-z0-9]+)/);
                if (m) return m[1];
            }}
            let parts = window.location.pathname.split('/');
            let filename = parts[parts.length - 1];
            return filename.replace('.html', '').replace('card_', '') || 'unknown';
        }}

        const taskNum = getTaskNum();
        const inParent = !!(window.parent && window.parent !== window);

        function setBtnState(id, active, defaultText, activeText, activeBg, activeBorder) {{
            let btn = document.getElementById(id);
            if (!btn) return;
            if (active) {{
                btn.innerText = activeText;
                btn.style.background = activeBg;
                btn.style.borderColor = activeBorder;
                btn.style.fontWeight = 'bold';
            }} else {{
                btn.innerText = defaultText;
                btn.style.background = '#fff';
                btn.style.borderColor = '#ccc';
                btn.style.fontWeight = 'normal';
            }}
        }}

        function applyData(data) {{
            setBtnState('tagFav', data.fav, '⭐ В избранное', '⭐ В избранном', '#fff8e1', '#fbc02d');
            setBtnState('tagSolved', data.solved, '✅ Решено', '✅ Решено', '#e8f5e9', '#4caf50');
            setBtnState('tagHard', data.hard, '⚠️ Повторить', '⚠️ Повторить', '#ffebee', '#ef5350');
        }}

        function readLocal() {{
            try {{
                return JSON.parse(localStorage.getItem('task_tags_' + taskNum) || '{{}}');
            }} catch(e) {{ return {{}}; }}
        }}

        function toggleTag(tag) {{
            if (inParent) {{
                currentData[tag] = !currentData[tag];
                applyData(currentData);
                window.parent.postMessage({{type: 'set_tag', num: taskNum, tag: tag}}, '*');
            }} else {{
                let data = readLocal();
                data[tag] = !data[tag];
                try {{ localStorage.setItem('task_tags_' + taskNum, JSON.stringify(data)); }} catch(e) {{}}
                currentData = data;
                applyData(currentData);
            }}
        }}

        window.addEventListener('message', function(e) {{
            let d = e.data;
            if (d && d.type === 'tags_data' && d.num === taskNum) {{
                currentData = d.data || {{}};
                applyData(currentData);
            }}
        }});

        window.addEventListener('DOMContentLoaded', function() {{
            currentData = readLocal();
            applyData(currentData);
            if (inParent) {{
                window.parent.postMessage({{type: 'request_tags', num: taskNum}}, '*');
            }}
        }});
    </script>
    </div>
</body>
</html>
"""


def iter_json_files(only_id=None):
    for jf in sorted(glob.glob(os.path.join(DATA_DIR, 'card_*.json'))):
        with open(jf, encoding='utf-8') as f:
            card = json.load(f)
        tid = (card.get('number') or '').strip().upper()
        if not tid:
            continue
        if only_id and tid != only_id:
            continue
        yield tid, card


def cmd_all():
    os.makedirs(HTML_DIR, exist_ok=True)
    n = 0
    for tid, card in iter_json_files():
        path = os.path.join(HTML_DIR, f'card_{tid}.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(build_html(card))
        n += 1
    print(f"Regenerated {n} cards -> {HTML_DIR}")


def cmd_check():
    same = diff = 0
    for tid, card in iter_json_files():
        path = os.path.join(HTML_DIR, f'card_{tid}.html')
        want = build_html(card)
        try:
            with open(path, encoding='utf-8') as f:
                have = f.read()
        except FileNotFoundError:
            print(f"MISSING: {path}")
            diff += 1
            continue
        if have == want:
            same += 1
        else:
            diff += 1
            print(f"DIFF: {tid}")
    print(f"check: {same} identical, {diff} differ")


def cmd_one(tid):
    tid = tid.strip().upper()
    jf = os.path.join(DATA_DIR, f'card_{tid}.json')
    with open(jf, encoding='utf-8') as f:
        card = json.load(f)
    os.makedirs(HTML_DIR, exist_ok=True)
    path = os.path.join(HTML_DIR, f'card_{tid}.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(build_html(card))
    print(f"Regenerated {path}")


def main():
    args = sys.argv[1:]
    if not args:
        cmd_all()
    elif args[0] == '--check':
        cmd_check()
    elif args[0].startswith('-'):
        print(__doc__)
        sys.exit(1)
    else:
        for tid in args:
            cmd_one(tid)


if __name__ == '__main__':
    main()
