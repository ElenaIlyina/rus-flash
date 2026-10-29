# Разработка и подготовка материалов

Весь вспомогательный раздел находится здесь и хранится в Git вместе
с приложением. Пользовательская часть собирается и работает без `dev/`.

```text
dev/
  docs/                   Планы, спецификации, согласования, баги, библиография,
                          журналы правок, ревью и саморевью, справочные оригиналы
  data/                   Редакторские реестры и материалы аудита
  scripts/                Получение и проверка ФИПИ, подготовка источников,
                          публикация готовых данных, сборка страницы ревью
  tests/                  Все модульные и браузерные проверки
  review/                 Отдельный локальный инструмент ревью карточек
  requirements.txt        Зависимости только для разработки
```

[Документация](docs/README.md), [планы](docs/development-plan.md),
[замечания](docs/content-audit/open-issues.md), [литература](<docs/Список литературы.md>),
[журнал](docs/correction-log.md), [разделение production/dev](docs/production-separation.md).

## Поток публикации материалов

1. Подготовить карточки и словарные доказательства, обновить реестры (в том числе `task_7_card_reviews.json`) в
   `dev/data/knowledge/` и журнал объяснений в `dev/docs/content-audit/`.
   Условия и ключи ФИПИ изменяются только по согласованию автора.
2. Выполнить `python3 dev/scripts/publish_content.py`. Инструмент проверит
   исходники, хеши и ссылки и обновит только подготовленные данные приложения:
   `card_support.json`, `paronyms.json`, `dictionary_sources.json`, профиль
   экзамена, реестр справочника и правила доступности проверки.
3. Выполнить `bash scripts/install.sh`. Эта сборка читает только production.

Проверка синхронности без записи: `python3 dev/scripts/publish_content.py --check`.
Редакторские статусы, цитаты-основания и журналы не переносятся в production.
Готовые подсказки, значения и учебные ссылки являются частью приложения.

## Отдельная страница ревью

```bash
python3 dev/scripts/build_review_data.py
python3 -m http.server 8000 --bind 127.0.0.1
```

Из корня проекта откройте `http://127.0.0.1:8000/dev/review/`.
В очереди есть фильтры и локальное принятие версии разбора; рядом открывается
настоящее приложение в iframe. История учебных ответов от нажатия «Разбор принят»
не меняется. Отметки принятия хранятся под прежним ключом localStorage.
В ученических настройках и навигации инструментов ревью больше нет.

## Проверки

Стандартная библиотека:

```bash
bash scripts/install.sh
python3 -m unittest discover -s dev/tests -p '*_test.py'
python3 scripts/check_pages_artifact.py html
```

Для браузерных тестов:

```bash
sudo apt install -y python3-venv chromium
python3 -m venv dev/.venv
dev/.venv/bin/pip install -r dev/requirements.txt
python3 dev/scripts/build_review_data.py
dev/.venv/bin/python dev/tests/ui_smoke.py
dev/.venv/bin/python dev/tests/priority_1_6_smoke.py
dev/.venv/bin/python dev/tests/review_debug_smoke.py
```

Остальные сценарии — в `dev/tests/`. Скриншоты сохраняются только в `/tmp/`.
В `requirements.txt` также указаны инструменты извлечения PDF/MOBI; они
нужны при подготовке новых источников, но не при сборке и пользовании сайтом.

Текущие материалы №1–4: [отчёт](docs/task-1-4-self-review.md),
[обновление по новой выгрузке](docs/fipi-refresh-workflow.md),
[очередь вторых ответов](docs/author-answer-checks.md).
Проверки этой партии: `python3 dev/tests/text_skills_smoke.py`,
`python3 dev/tests/priority_1_6_smoke.py`, стандартные модульные тесты.

Проверка сервером ФИПИ на компьютере автора:
`python3 dev/scripts/check_fipi_answers.py --cards src/cards`.
[Настройки пауз, журнал и продолжение](docs/fipi-answer-checks.md).
