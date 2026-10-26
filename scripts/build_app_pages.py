#!/usr/bin/env python3
"""Generate separate app documents from one shared shell (standard library only)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    'index': ('study', 'Заниматься'),
    'bank': ('bank', 'Банк заданий'),
    'card': ('card', 'Карточка'),
    'progress': ('progress', 'Мой прогресс'),
    'knowledge': ('knowledge', 'Справочник'),
}

def main():
    template = (ROOT / 'scripts/templates/app.html').read_text()
    for filename, (page, title) in PAGES.items():
        html = template.replace('{{page}}', page).replace('{{title}}', title)
        (ROOT / 'html' / f'{filename}.html').write_text(html)
    print(f'Built {len(PAGES)} app pages')

if __name__ == '__main__':
    main()
