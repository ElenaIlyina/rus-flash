import { loadCatalog } from "../js/data.js";
import { store } from "../js/store.js";
const icons = {
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  up: '<path d="M5 19 19 5M5 5h14v14"/>',
  play: '<path d="m9 5 11 7-11 7z"/>',
  book: '<path d="M12 6C9 4 6 4 3 5v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v14"/>',
  bars: '<path d="M5 20V10m7 10V4m7 16v-7"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  star: '<path d="M12 2v20M2 12h20M5 5l14 14M5 19 19 5"/>',
  sound: '<path d="M4 10v4m5-8v12m5-15v18m5-14v10"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.star}</svg>`;
const variants = ["edition", "focus", "studio"];
const requested = new URLSearchParams(location.search).get("v");
const variant = variants.includes(requested) ? requested : "edition";
document.body.className = variant;
document.querySelector('meta[name="theme-color"]').content =
  variant === "focus"
    ? "#161c1b"
    : variant === "studio"
      ? "#f9f6f1"
      : "#f5f3eb";
document
  .querySelector(`[href="?v=${variant}"]`)
  .setAttribute("aria-current", "page");
const root = document.querySelector("#concept");
const to = (hash) => `../#${hash}`;
const nav = (vertical = false) =>
  `<nav class="app-nav ${vertical ? "vertical" : ""}" aria-label="Разделы приложения"><a class="active" href="${to("study")}">${icon("play")}<span>Заниматься</span></a><a href="${to("bank")}">${icon("grid")}<span>Банк заданий</span></a><a href="${to("progress")}">${icon("bars")}<span>Прогресс</span></a><a href="${to("knowledge")}">${icon("book")}<span>Справочник</span></a></nav>`;
const brand = `<a class="brand" href="?v=${variant}"><span class="brand-symbol">${icon("star")}</span><span class="design-wordmark">Слово<br>за слово</span><span class="brand-caption">РУССКИЙ ЯЗЫК</span></a>`;
const groups = [
  {
    title: "Орфография",
    caption: "Буквы на своих местах",
    tasks: [9, 10, 11, 12, 13, 14, 15],
    glyph: "Аа",
    style: "orange",
  },
  {
    title: "Пунктуация",
    caption: "Поставить всё по местам",
    tasks: [16, 17, 18, 19, 20, 21],
    glyph: "?!",
    style: "purple",
  },
  {
    title: "Нормы языка",
    caption: "Звучать уверенно",
    tasks: [4, 5, 6, 7, 8],
    glyph: "Ёё",
    style: "green",
  },
  {
    title: "Работа с текстом",
    caption: "Понять между строк",
    tasks: [1, 2, 3, 22, 23, 24, 25, 26, 27],
    glyph: "¶",
    style: "pink",
  },
];
const count = (n) => n.toLocaleString("ru-RU");
try {
  const catalog = await loadCatalog();
  const ids = new Set(catalog.cards.map((c) => c.id));
  const history = store.history.filter((e) => ids.has(e.cardId));
  const practiced = new Set(history.map((e) => e.cardId)).size;
  const favorites = catalog.cards.filter((c) => store.tags(c.id).fav).length;
  const candidate =
    catalog.cards.find((c) => c.id === store.lastCard) ||
    catalog.cards.find((c) => c.hasAnswer && c.task === 4) ||
    catalog.cards[0];
  const cardURL = to(`card/${candidate.id}`);
  const topicLinks = groups
    .map(
      (g, i) =>
        `<a class="topic ${g.style}" href="${to(`bank?topic=${i}`)}"><span class="topic-glyph">${g.glyph}</span><span class="topic-info"><h3>${g.title}</h3><p>${g.caption}</p><small>${count(catalog.cards.filter((c) => g.tasks.includes(c.task)).length)} карточек</small></span><span class="topic-arrow">${icon("up")}</span></a>`,
    )
    .join("");
  const progressNote = practiced
    ? `Вы уже попробовали ${practiced} карточек. Продолжим?`
    : "Первая попытка — уже начало. Остальное придёт с практикой.";
  const practiceCTA = store.lastCard ? "Продолжить" : "Попробовать";
  if (variant === "edition") {
    document.title = "01 Редакция — Слово за слово";
    root.innerHTML = `<div class="edition-shell"><aside class="edition-sidebar">${brand}${nav(true)}<div class="sidebar-bottom"><span class="tiny-label">ТВОЙ ТЕМП. ТВОИ ПРАВИЛА.</span><p>Учиться —<br>тоже навык.</p><a href="${to("progress")}">${icon("bars")} ${practiced} карточек попробовано</a></div></aside><div class="edition-content"><div class="edition-top"><span class="tiny-label">ПРАКТИКА РУССКОГО · БЕЗ ЛИШНЕГО ШУМА</span><a href="${to("bank")}">Открыть банк ${icon("up")}</a></div><section class="edition-hero"><div class="edition-hero-copy"><span class="issue-label"><span></span> ВЫПУСК 01 / НАЧАТЬ С СЕБЯ</span><h1>Не зубри.<br><span>Разберись.</span></h1><p>Русский — это не набор ловушек.<br>Разложим по полочкам. По одной карточке.</p><a class="cta" href="${cardURL}">${practiceCTA} карточку ${icon("arrow")}</a></div><a href="${cardURL}" class="editorial-poster" aria-label="Открыть карточку"><span class="poster-label">В ЭТОМ НОМЕРЕ</span><span class="poster-letter">Ё<span>!</span></span><span class="poster-foot">ТОЧКА ОПОРЫ —<br>ПОНИМАНИЕ.</span><span class="poster-corner">${icon("up")}</span></a></section><section class="edition-topics"><div class="section-heading"><h2>Выбери, с чего начать<span> / 04</span></h2><a href="${to("bank")}">Все темы ${icon("arrow")}</a></div><div class="topics">${topicLinks}</div></section><section class="edition-bottom"><div><span class="tiny-label">МАЛЕНЬКИЙ ШАГ СЕГОДНЯ</span><p>${progressNote}</p><a href="${to("progress")}">Моя история ${icon("arrow")}</a></div><a href="${to("bank")}" class="bank-stamp"><strong>${count(catalog.cards.length)}</strong><span>поводов сказать<br>«теперь понятно»</span>${icon("star")}</a></section></div></div>`;
  } else if (variant === "focus") {
    document.title = "02 Фокус — Слово за слово";
    root.innerHTML = `<div class="focus-shell"><header class="focus-header">${brand}${nav()}<a class="profile" href="${to("progress")}" aria-label="Прогресс">СЗС</a></header><div class="focus-content"><section class="focus-intro"><div><span class="tiny-label"><span class="live-dot"></span> ТОЛЬКО ТЫ И СЛЕДУЮЩИЙ ШАГ</span><h1>Меньше шума.<br>Больше <span>понимания.</span></h1><p>Одно задание за раз. Без гонки, рейтингов и «ты должен».</p></div><div class="focus-orbit" aria-hidden="true"><span class="orbit-circle"></span><span class="orbit-circle two"></span><span class="orbit-star">${icon("star")}</span><span class="orbit-tag">в своём темпе</span></div></section><section class="focus-dashboard"><div class="session-panel"><span class="tiny-label">ТВОЯ ПРАКТИКА</span><div class="session-heading"><h2>Переключись<br>на русский.</h2><span class="session-play">${icon("play")}</span></div><p>${progressNote}</p><a class="cta" href="${cardURL}">${practiceCTA} ${icon("arrow")}</a><div class="session-footer"><span>БЕЗ ТАЙМЕРА</span><span>МОЖНО ОСТАНОВИТЬСЯ</span></div></div><div class="focus-side"><a class="focus-note" href="${to("knowledge")}"><span class="tiny-label">НЕ ПОМНИШЬ ПРАВИЛО?</span>${icon("book")}<h3>Сначала понять.<br>Потом применить.</h3><p>Справочник готовится. Здесь будет опора для каждой темы.</p><span class="link-label">Как это устроено ${icon("arrow")}</span></a><a class="focus-history" href="${to("progress")}"><span>${icon("bars")} Твой прогресс</span><strong>${practiced}<small> карточек попробовано</small></strong>${icon("up")}</a></div></section><section class="focus-topics"><div class="section-heading"><h2>Или выбери направление</h2><span>${count(catalog.cards.length)} карточек в банке</span></div><div class="topics">${topicLinks}</div></section></div></div>`;
  } else {
    document.title = "03 Студия — Слово за слово";
    root.innerHTML = `<div class="studio-shell"><header class="studio-header">${brand}<span class="studio-motto">МЕСТО, ГДЕ МОЖНО НЕ ЗНАТЬ. И РАЗОБРАТЬСЯ.</span><a class="profile" href="${to("progress")}" aria-label="Прогресс">СЗС</a></header><div class="studio-workspace"><aside class="studio-sidebar">${nav(true)}<div class="studio-side-note">${icon("star")}<p>Ошибаться —<br>часть маршрута.</p><span>Тут не ставят двойки.</span></div></aside><div class="studio-content"><section class="studio-intro"><span class="tiny-label">ТВОЯ СТУДИЯ РУССКОГО</span><h1>Сложное?<br>Сейчас <span>распутаем.<svg viewBox="0 0 310 15" aria-hidden="true"><path d="M3 11Q145-3 305 7" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/></svg></span></h1><p>Немного практики, понятные объяснения<br>и место для твоих открытий.</p><span class="studio-doodle" aria-hidden="true">${icon("star")}</span></section><section class="studio-board"><a class="studio-main-note" href="${cardURL}"><span class="note-pin" aria-hidden="true"></span><span class="tiny-label">НАЧНИ С МАЛЕНЬКОГО</span><h2>Одна карточка.<br>Одно «ага!».</h2><p>Не нужно знать всё,<br>чтобы начать.</p><span class="note-cta">${practiceCTA} ${icon("arrow")}</span><span class="note-number" aria-hidden="true">01</span></a><a class="studio-stat-note" href="${to("progress")}"><span class="tiny-label">ТВОИ ШАГИ</span><strong>${practiced}</strong><p>карточек попробовано</p><span class="small-link">Каждый шаг считается ${icon("up")}</span></a><a class="studio-saved-note" href="${to("bank")}"><span class="tiny-label">ПОД РУКОЙ</span>${icon("bookmark")}<h3>Есть к чему<br>вернуться.</h3><span>${favorites} в избранном · открыть банк ${icon("arrow")}</span></a></section><section class="studio-topics"><div class="section-heading"><h2>Разложим по темам</h2><a href="${to("bank")}">Весь банк ${icon("arrow")}</a></div><div class="topics">${topicLinks}</div></section><a class="studio-rule-strip" href="${to("knowledge")}">${icon("book")}<span><strong>А почему именно так?</strong><small>Место для будущего справочника с проверенными правилами</small></span>${icon("arrow")}</a></div></div></div>`;
  }
} catch (error) {
  root.innerHTML =
    '<div class="load-error"><h1>Сначала подготовим данные</h1><p>В корне проекта выполните <code>bash scripts/install.sh</code> и запустите HTTP-сервер.</p><a href="../">Вернуться в приложение</a></div>';
}
