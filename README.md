# RusFlash — флешкарты ЕГЭ (русский язык) из банка ФИПИ

2140 карт, задания 1–27. Полностью автономный проект: данные, скрипты сборки и статический UI в одной папке. Открой `html/index.html` — и пользуйся.

## Быстрый старт

```bash
# Собрать всё (порядок важен: манифест → карты → сайдбар)
python3 scripts/generate_manifest.py     # -> html/cards_manifest.js
python3 scripts/regen_cards_html.py      # -> html/card_*.html (из data/)
python3 scripts/build_index_sidebar.py   # -> сайдбар внутри html/index.html
```

`html/card_*.html` и `html/cards_manifest.js` — **генерируются из `data/` и в проекте не хранятся** (добавлены в `.gitignore`). Без шага 2 карты в браузере открываться не будут.

Затем открой `html/index.html` в браузере. Прогресс хранится в `localStorage`, ничего на сервер не уходит.

## Структура

```
data/card_XXXXXX.json    2140 карт — единственный источник правды
data/ege_specification_mapping.json   названия и КЭС заданий 1–27
data/fipi_numbers.txt    все ID банка ФИПИ (вход скрейпера)
html/index.html          UI: сайдбар + iframe карты (только сайдбар генерируется)
html/dashboard.html      статистика/прогресс
html/stats.html          сводка
html/cards_manifest.js   window.CARDS_MANIFEST (генерируется, не хранится)
html/card_*.html         2140 карт (генерируются из data/, не хранятся)
scripts/generate_manifest.py    классификатор + манифест
scripts/regen_cards_html.py     HTML карт (--check для проверки)
scripts/build_index_sidebar.py  сайдбар index.html
scripts/parse_fipi_missing.py   скрейпер FIPI (докачка новых карт)
scripts/verify_answers_fipi.py  проверка ответов через API FIPI
fipi_notes.md            заметки по API FIPI (пагинация, solve.php)
```

## Карта (`data/card_XXXXXX.json`)

```jsonc
{
  "number": "012CAB",          // UPPER CASE ID
  "guid": "9246...",           // ID вопроса на FIPI
  "kes": ["3.3.3 ..."],        // коды элементов содержания
  "question": "В одном из приведённых...",
  "text": "...",               // текст для чтения (если есть)
  "variants": ["1) ...", "2) ..."],   // варианты (у части карт пусто/слипшиеся)
  "answer": "ЛАКИРОВОЧНЫМ",    // правильный ответ
  "answer_verify": "ЛАКИРОВОЧНЫМ",   // ответ в формате для проверки
  "explanation": "..."         // разбор
}
```

## Проверка целостности

```bash
python3 scripts/regen_cards_html.py        # сгенерировать html/card_*.html
python3 scripts/regen_cards_html.py --check   # проверить, что существующие = ожидаемым
```
`--check` сравнивает уже сгенерированные файлы с эталоном; если их нет (после `git clean`/клона) — сначала `regen_cards_html.py` без `--check`.

Если изменил `data/card_*.json` — перегенерируй HTML (одну карту: `python3 scripts/regen_cards_html.py 012CAB`).

Правила классификации: `generate_manifest.py` сопоставляет карты заданиям по КЭС и текстовым сигнатурам вопроса (первое совпадение выигрывает; текстовые сигнатуры важнее КЭС, т.к. FIPI вешает «чужие» КЭС). После правки правил сумма распределения, печатаемая в консоль, обязана равняться числу JSON-карт (2140).

## Примечания

- **Не правь руками `html/card_*.html` и `html/cards_manifest.js`** — они всегда перегенерируются из `data/`. А вот **`index.html`, `dashboard.html`, `stats.html` — это исходники**: их разметка/CSS/JS пишутся вручную и хранятся в проекте; скрипт `build_index_sidebar.py` перезаписывает в `index.html` только блок `<div class="list" id="sidebarList">…</div>`, остальное не трогая.
- **Все ID — UPPER CASE** (имена `card_XXXXXX.json`, `html/card_XXXXXX.html`, поле `number`, пути в манифесте/сайдбаре). FIPI отдаёт смешанный регистр — при обработке нормализуй через `.strip().upper()`.
- **Формат ответа у задания 4 (ударения):** битмаск (`11101`) для вопросов «верно выделена буква», обычное слово для «выпишите слово».
- **`variants` неоднороден:** у части карт 5 отдельных элементов, у части (~137) один слипшийся элемент со всеми пунктами в одной строке. Оба варианта валидны, не «чини» без необходимости.
- Скрейпер `parse_fipi_missing.py` читает `fipi_numbers.txt` и пропускает уже существующие карты (идемпотентен).
