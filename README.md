# Слово за слово

Статический тренажёр русского языка: 2140 карточек, банк заданий, подсказки,
объяснения со ссылками на справочник, оценки карточек и тем, локальный прогресс.

Позиции сопоставлены с официальным проектом ЕГЭ-2027. Проверка объяснений
и старых форматов продолжается; наличие ответа в базе не заменяет приёмку учителем.
Полный адаптивный маршрут, собственные простые упражнения, PWA и автоматическая
синхронизация пока не реализованы.

## Запуск на Ubuntu

Нужны Git, Python 3 и современный браузер. Приложению не нужны npm,
серверный фреймворк, сторонние Python-библиотеки или ключи API.

```bash
sudo apt update
sudo apt install -y git python3
git clone https://github.com/ElenaIlyina/rus-flash.git
cd rus-flash
git switch feat/slovo-za-slovo
bash scripts/install.sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory html
```

Откройте `http://127.0.0.1:8000` на своём компьютере. Остановить сервер — Ctrl+C.
Открытие `index.html` через `file://` не поддерживается: данные загружаются через fetch.
После изменения исходных JSON повторите `bash scripts/install.sh`.

## Разделы приложения

| Адрес | Содержимое |
|---|---|
| `#study` | Главная, темы, суммарный прогресс и начало практики |
| `#bank` | Поиск, фильтры, избранное, повторение и порядок выдачи |
| `#card/EECA69` | Задание, проверка ответа, подсказка, разбор и связанные правила |
| `#progress` | Охват карточек и закрепление групп |
| `#progress?view=history` | История отправок и ручные отметки |
| `#knowledge` | Короткие правила и академический справочник |
| `#settings` | Коэффициенты оценок, порог и срок повторения |

Чтение правила не снижает результат. Верное решение с n-й отправки получает
1/n, с помощью — 0. Оценка обновляется один раз при завершении решения.
Карточка и тема имеют разные коэффициенты; точные формулы и ограничения —
в [политике оценивания](docs/current-learning.md).

Прогресс хранится в браузере. Его можно скачать и загрузить на другом устройстве:
импорт показывает изменения и объединяет историю без удаления текущих записей.
Файл не отправляется на сервер. [Контракт переноса](docs/specification/progress-transfer.md).
Настройки локальны; при смене протокола, хоста или порта браузер использует другое хранилище.

## Структура

```text
data/                     Исходные карточки, классификация, правила и источники
html/index.html           Оболочка приложения
html/js/                  Экраны, загрузка, проверка, оценки, подбор и хранение
html/css/                 Стили по областям интерфейса
html/assets/data/         Результат сборки; не хранится в Git
scripts/                  Сборка, аудит, проверка и получение материалов
tests/                   Проверки данных и браузерных сценариев
docs/                     Спецификация, план, согласования и журнал исправлений
```

Браузер загружает карточки и параграфы по отдельности. Сборка воспроизводит
`html/assets/data/` из `data/`, исходники не переписывает и в сеть не обращается.
Сетевые утилиты ФИПИ нужны только для подготовки материалов, не для работы сайта.
[Карта файлов](docs/project-structure.md), [документация](docs/README.md).

## Проверки

```bash
bash scripts/install.sh
python3 scripts/check_pages_artifact.py html
python3tests/content_audit_test.py
python3tests/handbook_test.py
python3tests/ui_smoke.py
python3tests/composed_home_smoke.py
python3tests/learning_smoke.py
python3tests/bank_knowledge_smoke.py
python3tests/progress_transfer_smoke.py
python3tests/pages_smoke.py
```

Браузерным проверкам нужны Playwright и Chromium; это зависимости разработки:

```bash
sudo apt install -y python3-venv chromium
python3 -m venv .venv
.venv/bin/pip install playwright
.venv/bin/pythontests/ui_smoke.py
```

Тесты используют `/usr/bin/chromium`, временный HTTP-сервер и изолированное
хранилище браузера. Опция `--screenshots` у визуальных проверок сохраняет снимки
в `/tmp/rus-flash-screenshots/`, без файлов в `docs/`.

## Публикация и развитие

Для GitHub Pages запускайте workflow **Deploy Slovo za Slovo to GitHub Pages**
в нужной ветке. Пуш сам по себе сайт не публикует. [Настройка Pages](docs/github-pages.md).

[План развития](docs/development-plan.md), [спецификация](docs/specification/README.md),
[вопросы к автору](docs/author-approval-questions.md), [журнал исправлений](docs/correction-log.md).
Исходные нормативные документы, хеши и соответствие позиций сохранены в
[реестре материалов](docs/ege-2027-card-mapping.md) и [отчёте по справочникам](docs/handbook-import.md).
