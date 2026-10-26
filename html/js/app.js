import { parseProgress, mergeProgress } from "./progress-transfer.js";
import {
  renderProgressPreview,
  renderGlobalCardProgressPreview,
} from "./progress-preview.js";
import { loadCatalog, loadCard } from "./data.js";
import { store } from "./store.js";
import { services } from "./services.js";

const main = document.querySelector("#main");
const icons = {
  study: '<path d="m9 5 11 7-11 7z"/>',
  bank: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  progress: '<path d="M5 20V10m7 10V4m7 16v-7"/>',
  knowledge:
    '<path d="M12 6c-3-2-6-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v14"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
  repeat: '<path d="M20 7h-9a6 6 0 1 0 5 9M16 3l4 4-4 4"/>',
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  leaf: '<path d="M5 19C1 7 9 3 21 3c0 12-4 20-16 16Zm0 0L16 8"/>',
};
const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.spark}</svg>`;
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
// Retain meaningful source formatting, drop executable/unknown markup and attributes.
function rich(value) {
  const doc = new DOMParser().parseFromString(String(value || ""), "text/html");
  const allowed = new Set([
    "B",
    "STRONG",
    "I",
    "EM",
    "U",
    "SUB",
    "SUP",
    "BR",
    "P",
  ]);
  function clean(node) {
    if (node.nodeType === Node.TEXT_NODE) return esc(node.textContent);
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    if (["SCRIPT", "STYLE", "IFRAME", "OBJECT", "SVG"].includes(node.tagName))
      return "";
    const inside = [...node.childNodes].map(clean).join("");
    if (!allowed.has(node.tagName)) return inside;
    const name = node.tagName.toLowerCase();
    return name === "br" ? "<br>" : `<${name}>${inside}</${name}>`;
  }
  return [...doc.body.childNodes].map(clean).join("").replace(/\n/g, "<br>");
}
const plain = (s) =>
  new DOMParser().parseFromString(s || "", "text/html").body.textContent;
const num = (n) => n.toLocaleString("ru-RU");
const navs = [
  ["study", "Заниматься"],
  ["bank", "Банк заданий"],
  ["progress", "Мой прогресс"],
  ["knowledge", "Справочник"],
];
const topics = [
  {
    name: "Орфография",
    tasks: [9, 10, 11, 12, 13, 14, 15],
    color: "peach",
    icon: "knowledge",
    detail: "От корней до окончаний",
  },
  {
    name: "Пунктуация",
    tasks: [16, 17, 18, 19, 20, 21],
    color: "lilac",
    icon: "bank",
    detail: "Каждый знак на своём месте",
  },
  {
    name: "Нормы языка",
    tasks: [4, 5, 6, 7, 8],
    color: "sage",
    icon: "leaf",
    detail: "Говорить и писать точно",
  },
  {
    name: "Работа с текстом",
    tasks: [1, 2, 3, 22, 23, 24, 25, 26, 27],
    color: "blue",
    icon: "study",
    detail: "Читать, понимать, рассуждать",
  },
];
let catalog,
  currentCard,
  renderVersion = 0,
  reveal = false,
  attempted = false;
let pendingImport = null;
let filter = { query: "", task: "", status: "all", page: 1 };
function topicCards(topic) {
  return catalog.cards.filter((c) => topic.tasks.includes(c.task));
}
function route() {
  const page = document.body.dataset.page || "study";
  const params = new URLSearchParams(location.search);
  return {
    path: page === "card" ? `card/${params.get("id") || ""}` : page,
    params,
  };
}
const initialParams = route().params;
filter = {
  query: initialParams.get("q") || "",
  task: initialParams.get("task") || "",
  status: ["all", "answer", "self", "fav", "hard"].includes(
    initialParams.get("status"),
  )
    ? initialParams.get("status")
    : "all",
  page: Math.min(1000, Math.max(1, Number(initialParams.get("page")) || 1)),
};
function saveBankFilters() {
  if (document.body.dataset.page !== "bank") return;
  const params = new URLSearchParams(location.search);
  for (const [key, value] of Object.entries({
    q: filter.query,
    task: filter.task,
    status: filter.status === "all" ? "" : filter.status,
    page: filter.page > 1 ? filter.page : "",
  })) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  history.replaceState(null, "", `bank.html${params.size ? "?" + params : ""}`);
  try {
    sessionStorage.setItem(
      "slovo_bank_return",
      location.pathname + location.search,
    );
  } catch {}
}
function bankReturnUrl() {
  try {
    const saved = new URL(
      sessionStorage.getItem("slovo_bank_return") || "bank.html",
      location.href,
    );
    const expected = new URL("bank.html", location.href);
    if (
      saved.origin === expected.origin &&
      saved.pathname === expected.pathname
    )
      return saved.pathname + saved.search;
  } catch {}
  return "bank.html";
}
function heading(kicker, title, subtitle, action = "") {
  return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;
}
function stats() {
  const ids = new Set(catalog.cards.map((c) => c.id));
  const history = store.history.filter((e) => ids.has(e.cardId));
  return {
    history,
    correct: history.filter((e) => e.correct && !e.assisted),
    practiced: new Set(history.map((e) => e.cardId)),
  };
}
function empty(iconName, title, description, button = "") {
  return `<div class="empty-state"><span class="empty-icon">${icon(iconName)}</span><h2>${title}</h2><p>${description}</p>${button}</div>`;
}
function renderStudy() {
  const s = stats();
  const candidate =
    catalog.cards.find((c) => c.id === store.lastCard) ||
    catalog.cards.find((c) => c.hasAnswer && c.task === 4) ||
    catalog.cards[0];
  main.innerHTML = `
    <div class="study-intro">
      <section class="hero study-hero" aria-labelledby="hero-title">
        <div class="hero-copy"><span class="eyebrow">РУССКИЙ ЯЗЫК · В СВОЁМ ТЕМПЕ</span><h1 id="hero-title">Не всё сразу.<br>Начнём с одной карточки.</h1><p>Разобраться в правиле. Попробовать.<br> И однажды заметить: получается.</p><section class="stat-strip" aria-label="Ваши результаты"><div>${icon("bank")}<span><strong>${num(catalog.cards.length)}</strong><small>карточек в банке</small></span></div><div>${icon("check")}<span><strong>${s.practiced.size}</strong><small>карточек попробовано</small></span></div><div>${icon("bookmark")}<span><strong>${catalog.cards.filter((c) => store.tags(c.id).fav).length}</strong><small>в избранном</small></span></div></section>${renderGlobalCardProgressPreview(catalog.cards.length)}</div>
      </section>
      <a class="study-poster" href="card.html?id=${candidate.id}" aria-label="Начать заниматься"><div class="poster-face"><span class="poster-art" aria-hidden="true"><svg class="poster-glyph" viewBox="0 0 300 260" fill="none"><g fill="currentColor" transform="rotate(-9 130 130)"><path d="M62 18h27v27H62zM122 18h27v27h-27zM62 72h113v27H90v37h76v27H90v39h85v27H62z"/></g><g fill="#ff7952" transform="rotate(10 220 165)"><path d="M209 99h26l-3 103h-20zM209 216h26v26h-26z"/></g></svg></span><span class="poster-cta">Начать заниматься</span><span class="poster-arrow">${icon("arrow")}</span></div></a>

    </div>
    <section class="study-topics" aria-labelledby="topics-title"><div class="section-heading"><div><span class="eyebrow">ОТ ПРОСТОГО К ПОНЯТНОМУ</span><h2 id="topics-title">Что разберём сегодня?</h2></div><a class="text-link" href="bank.html">Весь банк ${icon("arrow")}</a></div><div class="topic-grid topic-notes">${topics.map((t, i) => `<a class="topic-card topic-note ${t.color}" href="bank.html?topic=${i}"><span class="note-tape" aria-hidden="true"></span><span class="eyebrow">${String(i + 1).padStart(2, "0")} / ВЫБЕРИ НАПРАВЛЕНИЕ</span><span class="topic-icon">${icon(t.icon)}</span><h3>${t.name}</h3><p>${t.detail}</p><span class="note-number" aria-hidden="true">${String(i + 1).padStart(2, "0")}</span><span class="note-bottom"><span class="topic-count">${num(topicCards(t).length)} карточек</span><span class="note-open">Открыть ${icon("arrow")}</span></span></a>`).join("")}</div></section>
    <div class="editorial-note">${icon("knowledge")}<p>Банк ещё проходит проверку. Номера групп предварительные, а ответы и разборы есть не у всех карточек. Это версия интерфейса для обсуждения.</p></div>`;
}
function bankResults() {
  saveBankFilters();
  const topic = route().params.get("topic");
  const list = catalog.cards.filter((c) => {
    if (
      topic !== null &&
      topics[Number(topic)] &&
      !topics[Number(topic)].tasks.includes(c.task)
    )
      return false;
    if (filter.task && String(c.task) !== filter.task) return false;
    if (
      filter.query &&
      !(c.id + " " + plain(c.title))
        .toLowerCase()
        .includes(filter.query.toLowerCase())
    )
      return false;
    const tags = store.tags(c.id);
    return (
      filter.status === "all" ||
      (filter.status === "answer" && c.hasAnswer) ||
      (filter.status === "self" && !c.hasAnswer) ||
      (filter.status === "fav" && tags.fav) ||
      (filter.status === "hard" && tags.hard)
    );
  });
  const area = main.querySelector("#bank-results");
  if (!area) return;
  area.innerHTML =
    `<div class="results-meta">Найдено ${num(list.length)} ${topic !== null ? '<a href="bank.html" class="text-link">Сбросить тему ×</a>' : ""}</div>` +
    (list.length
      ? `<div class="card-list">${list
          .slice(0, filter.page * 24)
          .map(
            (c) =>
              `<a class="bank-row" href="card.html?id=${c.id}"><span class="row-icon group-number" aria-label="Группа ${c.task || "не определена"}">${esc(c.task || "—")}</span><div><div class="row-top"><span>${c.id}</span>${store.tags(c.id).fav ? '<span class="bank-favorite" aria-label="В избранном">⭐</span>' : ""}</div><h3>${esc(plain(c.title))}</h3><span class="row-status ${c.hasAnswer ? "" : "muted"}">${c.hasAnswer ? "Ответ в базе" : "Самостоятельная проверка"}</span></div>${icon("arrow")}</a>`,
          )
          .join(
            "",
          )}</div>${list.length > filter.page * 24 ? '<button class="button secondary load-more" data-action="more">Показать ещё 24</button>' : ""}`
      : empty(
          "search",
          "Пока ничего не нашлось",
          "Попробуйте другую тему, фильтр или запрос.",
        ));
}
function renderBank(params) {
  const topic = topics[Number(params.get("topic"))];
  main.innerHTML =
    heading(
      "ПРАКТИКА БЕЗ СПЕШКИ",
      params.has("topic") && topic ? topic.name : "Банк заданий",
      "Выберите карточку, тему или вернитесь к тому, что хочется повторить.",
    ) +
    `
    <div class="bank-tools"><label class="search-field">${icon("search")}<input id="bank-search" type="search" placeholder="Найти по тексту или ID" value="${esc(filter.query)}" aria-label="Поиск по тексту или ID"></label><label class="select-field"><span class="sr-only">Группа задания</span><select id="task-filter"><option value="">Все группы</option>${Object.entries(
      catalog.taskNames,
    )
      .map(
        ([id, name]) =>
          `<option value="${id}" ${filter.task === id ? "selected" : ""}>${id}. ${esc(name)}</option>`,
      )
      .join("")}</select></label></div>
    <div class="filter-tabs" aria-label="Фильтры банка">${[
      ["all", "Все карточки"],
      ["answer", "С ответом"],
      ["self", "Без ответа"],
      ["fav", '<span aria-hidden="true">⭐</span> Избранное'],
      ["hard", '<span aria-hidden="true">⏳</span> Повторить'],
    ]
      .map(
        ([id, label]) =>
          `<button class="filter-tab ${filter.status === id ? "active" : ""}" data-filter="${id}" aria-pressed="${filter.status === id}">${label}</button>`,
      )
      .join("")}</div><div id="bank-results"></div>`;
  bankResults();
}
async function renderCard(id, version) {
  currentCard = null;
  main.innerHTML =
    '<div class="loading-state" role="status">Открываем карточку…</div>';
  const c = await loadCard(id);
  if (version !== renderVersion) return;
  currentCard = c;
  reveal = false;
  attempted = false;
  store.remember(c.id);
  const meta = catalog.cards.find((v) => v.id === id);
  const tags = store.tags(id);
  main.innerHTML = `<div class="card-breadcrumb"><a class="text-link" href="${esc(bankReturnUrl())}">${icon("back")} К банку заданий</a><span>Группа ${meta?.task || "—"} · ${esc(id)}</span></div>
    <div class="practice-layout"><article class="exercise"><div class="exercise-header"><span class="eyebrow">КАРТОЧКА ${id}</span><button class="icon-button ${tags.fav ? "selected" : ""}" data-action="favorite" aria-label="В избранное" aria-pressed="${!!tags.fav}">${icon("bookmark")}</button></div>
      <h1 class="exercise-title">${esc(catalog.taskNames[meta?.task] || "Практика русского языка")}</h1><div class="exercise-status"><span class="pill ${c.answer ? "sage-pill" : "neutral-pill"}">${c.answer ? "Ответ из текущей базы" : "Самостоятельная проверка"}</span><span>Материал не прошёл редакторскую проверку</span></div>
      ${c.passage ? `<details class="passage" open><summary>${icon("knowledge")} Текст к заданию<span>Свернуть / раскрыть</span></summary><div class="passage-content">${rich(c.passage)}</div></details>` : ""}
      <section class="question-section" aria-labelledby="question-label"><h2 id="question-label">Задание</h2><div class="question-text">${rich(c.instruction)}</div></section>
      ${c.errors.length && c.sentences.length ? `<div class="matching"><section><h3>Грамматические ошибки</h3>${c.errors.map((x, i) => `<p><b>${"АБВГДЕ"[i] || i + 1}.</b> ${rich(x)}</p>`).join("")}</section><section><h3>Предложения</h3>${c.sentences.map((x, i) => `<p><b>${i + 1}.</b> ${rich(x)}</p>`).join("")}</section></div>` : ""}
      ${c.options.length ? `<fieldset class="options"><legend>${c.responseType === "multiple_choice" ? "Выберите верные варианты" : "Варианты к заданию"}</legend>${c.options.map((x, i) => (c.responseType === "multiple_choice" ? `<label class="option"><input type="checkbox" name="answer-option" value="${i + 1}"><span>${rich(x)}</span></label>` : `<div class="option static-option"><span class="option-number">${i + 1}</span><span>${rich(x)}</span></div>`)).join("")}</fieldset>` : ""}
      <form id="answer-form" class="answer-form">${c.responseType !== "multiple_choice" ? `<label for="answer-input">${c.answer ? "Ваш ответ" : "Ваш ответ для самопроверки"}</label><input id="answer-input" autocomplete="off" placeholder="Введите ответ" ${c.answer ? "required" : ""}>` : ""}<div class="answer-actions">${c.answer ? `<button type="submit" class="button primary">Проверить ${icon("check")}</button>` : '<p class="muted">Эталонный ответ пока не добавлен. Автоматическая проверка недоступна.</p>'}<button type="button" class="button quiet" data-action="reveal">${c.answer ? "Ответ и разбор" : "Открыть разбор"}</button></div></form>
      <div id="answer-feedback" aria-live="polite"></div><section id="explanation" class="explanation" hidden></section>
      <div class="exercise-bottom"><button class="button quiet ${tags.hard ? "selected" : ""}" data-action="repeat" aria-pressed="${!!tags.hard}">${icon("repeat")} Повторить позже</button><button class="button secondary ${tags.studied ? "selected" : ""}" data-action="studied" aria-pressed="${!!tags.studied}">${icon("check")} ${tags.studied ? "Отмечено изученным" : "Отметить изученным"}</button><button class="button primary" data-action="next">Дальше ${icon("arrow")}</button></div>
    </article><aside class="practice-aside"><div class="aside-card"><span class="eyebrow">СНАЧАЛА ПОНИМАНИЕ</span><h2>Правило рядом</h2><p>Здесь появятся проверенные правила, связанные с навыком этой карточки.</p><button class="text-link" data-action="card-rules">Открыть справочник ${icon("arrow")}</button></div><div class="aside-tip">${icon("leaf")}<p>Не торопитесь. Можно вернуться к тексту, попробовать ещё раз или отложить карточку.</p></div><button class="text-link" data-action="report">Нашли неточность?</button></aside></div>`;
}
function renderExplanation() {
  const c = currentCard;
  const area = document.querySelector("#explanation");
  area.hidden = false;
  area.innerHTML = `<span class="eyebrow">РАЗБЕРЁМСЯ ВМЕСТЕ</span><h2>${c.answer ? "Ответ: " + esc(c.answer) : "Эталонный ответ ещё не добавлен"}</h2><span class="review-label">${c.explanation ? "Разбор из текущей базы · не проверен редактором" : "Разбор готовится"}</span>${c.explanation ? `<div class="explanation-text">${rich(c.explanation)}</div>` : "<p>Здесь будет объяснение решения, типичная ошибка и ссылка на правило. Пока нельзя считать эту карточку проверенным учебным материалом.</p>"}<button class="text-link" data-action="card-rules">${icon("knowledge")} Связанные правила</button>`;
}
function checkAnswer(event) {
  event.preventDefault();
  const c = currentCard;
  if (!c?.answer) return;
  const actual =
    c.responseType === "multiple_choice"
      ? [...main.querySelectorAll('[name="answer-option"]:checked')]
          .map((e) => e.value)
          .join("")
      : main.querySelector("#answer-input").value.trim().toLowerCase();
  const area = main.querySelector("#answer-feedback");
  if (!actual) {
    area.innerHTML = '<p class="feedback warning">Сначала укажите ответ.</p>';
    return;
  }
  const correct = actual === c.answer.toLowerCase();
  // A revealed answer, or a retry after feedback, must not become independent success.
  store.attempt(c.id, correct, reveal || attempted);
  attempted = true;
  area.innerHTML = `<div class="feedback ${correct ? "success" : "warning"}">${icon(correct ? "check" : "repeat")}<div><strong>${correct ? "Совпадает с ответом в базе" : "Пока не совпало. Попробуем ещё?"}</strong><p>${correct ? "Можно открыть разбор или перейти дальше." : "Вернитесь к условию или посмотрите объяснение."} ${reveal ? "Ответ уже был открыт: попытка отмечена с подсказкой." : ""}</p></div></div>`;
  if (!store.available)
    toast("Не удалось сохранить попытку: проверьте доступ к хранилищу.");
}
function renderProgress(params) {
  if (params.get("view") !== "history") {
    main.innerHTML = renderProgressPreview(params);
    return;
  }
  const s = stats();
  const independent = s.history.filter((e) => !e.assisted);
  const rate = independent.length
    ? Math.round((s.correct.length / independent.length) * 100)
    : null;
  main.innerHTML =
    heading(
      "ЗАМЕЧАЙТЕ СВОИ ШАГИ",
      "Мой прогресс",
      "Не соревнование с другими. История того, что вы уже попробовали.",
      '<div class="progress-actions"><a class="button primary" href="progress.html?view=preview">Новый дашборд · демо</a><button class="button secondary" data-action="export">Скачать прогресс</button><button class="button secondary" data-action="import">Загрузить прогресс</button></div>',
    ) +
    `
    <div class="progress-grid"><div class="metric"><span>Карточек попробовано</span><strong>${s.practiced.size}<small> / ${num(catalog.cards.length)}</small></strong><p>По истории нового интерфейса</p></div><div class="metric"><span>Самостоятельные ответы</span><strong>${rate === null ? "—" : rate + "%"}</strong><p>${independent.length ? `${s.correct.length} совпадений из ${independent.length} попыток` : "Появятся после первой проверки"}</p></div><div class="metric"><span>Отмечено изученным</span><strong>${catalog.cards.filter((c) => store.tags(c.id).studied).length}</strong><p>Ручная отметка, не результат проверки</p></div></div>
    <section class="panel"><div class="section-heading"><div><h2>Практика по темам</h2><p>Карточки с попытками, а не оценка освоения навыка</p></div></div>${topics
      .map((t) => {
        const cards = topicCards(t);
        const count = cards.filter((c) => s.practiced.has(c.id)).length;
        return `<div class="topic-progress"><span>${t.name}</span><div class="progress-track"><span style="width:${cards.length ? (count / cards.length) * 100 : 0}%"></span></div><small>${count} / ${cards.length}</small></div>`;
      })
      .join("")}</section>
    <section class="panel"><div class="section-heading"><div><h2>Последние попытки</h2><p>Ответы сверяются с текущей, ещё не проверенной базой</p></div></div>${
      s.history.length
        ? s.history
            .slice(-8)
            .reverse()
            .map(
              (e) =>
                `<a class="attempt-row" href="card.html?id=${e.cardId}"><span class="attempt-dot ${e.correct ? "correct" : ""}">${icon(e.correct ? "check" : "repeat")}</span><span><strong>Карточка ${e.cardId}</strong><small>${e.correct ? "Ответ совпал" : "Нужно повторить"}${e.assisted ? " · с подсказкой / повторная попытка" : " · самостоятельно"}</small></span><time>${new Date(e.time).toLocaleDateString("ru-RU")}</time></a>`,
            )
            .join("")
        : empty(
            "leaf",
            "Здесь начнётся ваша история",
            "Откройте карточку с ответом и попробуйте её решить.",
            '<a href="bank.html" class="button primary">Выбрать карточку</a>',
          )
    }</section>
    <div class="sync-card">${icon("repeat")}<div><h3>На телефоне и компьютере</h3><p>Сейчас прогресс хранится только в этом браузере. Перенос через JSON уже доступен. Автоматическая синхронизация — следующий этап.</p></div><button class="button secondary" data-action="sync">О синхронизации</button></div>`;
}
async function renderKnowledge(params, version) {
  const rawCardId = params.get("card");
  const cardId = /^[0-9A-F]{6}$/.test(rawCardId || "") ? rawCardId : null;
  const rules = cardId ? await services.knowledge.findRules({ cardId }) : [];
  if (version !== renderVersion) return;
  main.innerHTML =
    heading(
      "ПОНЯТЬ, ЧТОБЫ ПРИМЕНИТЬ",
      "Справочник правил",
      "Короткое объяснение, пример и связь с практикой — в одном месте.",
    ) +
    `
    <div class="knowledge-intro"><span class="book-art">${icon("knowledge")}</span><div><span class="pill neutral-pill">База знаний ещё не подключена</span><h2>У каждого ответа должно быть основание</h2><p>Здесь будут проверенные правила русского языка с источниками и примерами. Черновики, созданные с помощью RAG, появятся в приложении только после проверки.</p>${cardId ? `<a class="text-link" href="card.html?id=${esc(cardId)}">${icon("back")} Вернуться к карточке ${esc(cardId)}</a>` : ""}</div></div>
    <div class="section-heading"><div><h2>Как будет устроен справочник</h2><p>Это структура будущей базы, а не готовые учебные материалы</p></div></div><div class="knowledge-grid">${topics.map((t) => `<div class="knowledge-category"><span class="topic-icon ${t.color}">${icon(t.icon)}</span><h3>${t.name}</h3><p>${t.detail}</p><span class="coming-label">Материалы готовятся</span></div>`).join("")}</div>
    <section class="panel method-panel"><span class="eyebrow">ОТ ИСТОЧНИКА К ПОНИМАНИЮ</span><h2>Правило → пример → практика</h2><p>Надёжный источник, короткое объяснение и карточки на конкретный навык. Статус проверки будет виден у каждого материала.</p><button class="text-link" data-action="rag">Как будем готовить объяснения ${icon("arrow")}</button></section>`;
}
function modal(title, body) {
  document.querySelector("#info-dialog form button").textContent = "Понятно";
  document.querySelector("#dialog-body").innerHTML =
    `<span class="eyebrow">СЛОВО ЗА СЛОВО</span><h2 id="dialog-title">${title}</h2>${body}`;
  document.querySelector("#info-dialog").showModal();
}
function toast(text) {
  const el = document.querySelector("#toast");
  el.textContent = text;
  el.classList.add("visible");
  clearTimeout(toast.timeout);
  toast.timeout = setTimeout(() => el.classList.remove("visible"), 3500);
}
async function render() {
  if (!catalog) return;
  const version = ++renderVersion;
  const { path, params } = route();
  const active = path.startsWith("card/") ? "bank" : path;
  document.querySelector("#breadcrumb").textContent = path.startsWith("card/")
    ? "Практика / Карточка"
    : navs.find((n) => n[0] === path)?.[1] || "Заниматься";
  for (const target of ["#desktop-nav", "#mobile-nav"])
    document.querySelector(target).innerHTML = navs
      .map(
        ([id, label]) =>
          `<a href="${id === "study" ? "index" : id}.html" aria-label="${label}" title="${label}" class="nav-item ${active === id ? "active" : ""}" ${active === id ? 'aria-current="page"' : ""}>${icon(id)}<span>${target === "#mobile-nav" && id === "progress" ? "Прогресс" : label}</span>${id === "knowledge" && target === "#desktop-nav" ? '<span class="nav-dot"></span>' : ""}</a>`,
      )
      .join("");
  try {
    if (path.startsWith("card/")) await renderCard(path.slice(5), version);
    else if (path === "bank") renderBank(params);
    else if (path === "progress") renderProgress(params);
    else if (path === "knowledge") await renderKnowledge(params, version);
    else renderStudy();
  } catch (error) {
    if (version === renderVersion)
      main.innerHTML = empty(
        "repeat",
        "Не получилось открыть",
        esc(error.message),
        '<a href="bank.html" class="button secondary">Вернуться в банк</a>',
      );
  }
  if (version === renderVersion) {
    window.scrollTo({ top: 0 });
    document.title = `${path.startsWith("card/") ? "Карточка " + path.slice(5) : navs.find((n) => n[0] === path)?.[1] || "Заниматься"} — Слово за слово`;
  }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action], [data-filter]");
  if (!button) return;
  if (button.dataset.filter) {
    filter.status = button.dataset.filter;
    filter.page = 1;
    main.querySelectorAll("[data-filter]").forEach((el) => {
      el.classList.toggle("active", el.dataset.filter === filter.status);
      el.setAttribute("aria-pressed", el.dataset.filter === filter.status);
    });
    bankResults();
    return;
  }
  switch (button.dataset.action) {
    case "about":
      modal(
        "Учиться в своём темпе",
        "<p>Это рабочий интерфейс для ревью. Банк содержит исходные материалы ФИПИ, но ответы, разборы и номера групп ещё требуют проверки.</p><p>Прогресс хранится в этом браузере. Никакие ответы не отправляются на сервер. Офлайн-режим PWA, аккаунты и синхронизация пока не реализованы.</p>",
      );
      break;
    case "adaptive": {
      await services.adaptive.recommend({ history: store.history });
      modal(
        "Подбор по вашим трудностям",
        "<p>Будущий режим будет учитывать конкретные навыки, ошибки, подсказки и интервалы повторения. После затруднения он предложит правило или более простое задание.</p><p>Сейчас алгоритм не подключён: сначала нужно проверить материалы и разметить навыки. Обычная практика уже работает.</p>",
      );
      break;
    }
    case "rag":
      modal(
        "Источники, затем объяснение",
        "<p>RAG поможет находить подходящие правила и готовить черновики разборов со ссылками на источники. Редактор проверит объяснение перед публикацией.</p><p>Генерация выполняется инструментами подготовки данных, а не в браузере ученика. В этой версии база знаний и модель не подключены.</p>",
      );
      break;
    case "sync":
      modal(
        "Продолжить на другом устройстве",
        "<p>Планируем синхронизацию попыток, избранного и повторений. Сервер и аккаунты пока не подключены.</p><p>Сейчас можно скачать прогресс и загрузить его на другом устройстве через JSON-файл. Перед загрузкой показывается состав изменений; история объединяется без удаления текущих записей.</p>",
      );
      break;
    case "more":
      filter.page++;
      bankResults();
      break;
    case "reveal":
      reveal = true;
      renderExplanation();
      break;
    case "favorite":
    case "repeat":
    case "studied": {
      if (!currentCard) return;
      const tag = { favorite: "fav", repeat: "hard", studied: "studied" }[
        button.dataset.action
      ];
      const selected = store.toggle(currentCard.id, tag);
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", !!selected);
      if (tag === "studied")
        button.innerHTML = `${icon("check")} ${selected ? "Отмечено изученным" : "Отметить изученным"}`;
      toast(
        store.available
          ? selected
            ? "Сохранено на этом устройстве"
            : "Отметка снята"
          : "Хранилище недоступно. Изменение сохранится только до закрытия страницы.",
      );
      break;
    }
    case "next": {
      const index = catalog.cards.findIndex((c) => c.id === currentCard?.id);
      const task = catalog.cards[index]?.task;
      const candidates = catalog.cards.filter((c) => c.task === task);
      const position = candidates.findIndex((c) => c.id === currentCard?.id);
      const next = candidates[(position + 1) % candidates.length];
      if (next) location.href = `card.html?id=${next.id}`;
      break;
    }
    case "card-rules":
      if (currentCard) location.href = `knowledge.html?card=${currentCard.id}`;
      break;
    case "report":
      modal(
        "Спасибо за внимательность",
        `<p>Карточка <strong>${esc(currentCard?.id)}</strong>. Запишите её ID и опишите неточность при ревью проекта.</p><p>Отправка сообщений ещё не подключена. Эта кнопка ничего не отправляет.</p>`,
      );
      break;
    case "import":
      document.querySelector("#progress-import").click();
      break;
    case "apply-import": {
      if (!pendingImport) break;
      try {
        const result = store.importData(pendingImport);
        pendingImport = null;
        document.querySelector("#info-dialog").close();
        await render();
        toast(
          `Прогресс объединён: ${result.added} новых попыток, ${result.marksAdded} отметок.`,
        );
      } catch (error) {
        pendingImport = null;
        document.querySelector("#dialog-body").innerHTML =
          `<h2 id="dialog-title">Загрузка отменена</h2><p>${esc(error.message)}</p>`;
      }
      break;
    }
    case "export": {
      const url = URL.createObjectURL(
        new Blob([store.exportData()], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "slovo-za-slovo-progress.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      break;
    }
  }
});
document.querySelector("#info-dialog").addEventListener("close", () => {
  pendingImport = null;
});
document
  .querySelector("#progress-import")
  .addEventListener("change", async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    pendingImport = null;
    try {
      if (file.size > 10 * 1024 * 1024)
        throw new Error(
          "Файл больше 10 МБ. Выберите файл экспорта прогресса меньшего размера.",
        );
      const incoming = parseProgress(await file.text());
      const current = JSON.parse(store.exportData());
      const result = mergeProgress(current, incoming).summary;
      const known = new Set(catalog.cards.map((card) => card.id));
      const unknown = new Set(
        [
          ...incoming.events.map((e) => e.cardId),
          ...Object.keys(incoming.tags),
        ].filter((id) => !known.has(id)),
      ).size;
      pendingImport = incoming;
      modal(
        "Загрузить прогресс?",
        `<p>Файл: <strong>${esc(file.name)}</strong></p><p>Новых попыток: ${result.added}. Новых отметок: ${result.marksAdded}. Уже есть: ${result.duplicates}.</p>${result.conflicts ? `<p>Конфликтов ID: ${result.conflicts}. Для них сохранятся записи этого устройства.</p>` : ""}${unknown ? `<p>Неизвестных текущему банку карточек: ${unknown}. История сохранится, но не будет учитываться в текущих показателях.</p>` : ""}<p>История объединится без удаления текущих попыток. Отметки из файла добавятся к существующим; снятые отметки не удаляют выбранные на этом устройстве. Демо-статусы не загружаются.</p><div class="progress-actions"><button class="button secondary" data-action="export">Скачать текущую копию</button><button class="button primary" data-action="apply-import">Объединить прогресс</button></div>`,
      );
      document.querySelector("#info-dialog form button").textContent = "Отмена";
    } catch (error) {
      modal("Не удалось загрузить прогресс", `<p>${esc(error.message)}</p>`);
    }
  });
document.addEventListener("input", (event) => {
  if (event.target.id === "bank-search") {
    filter.query = event.target.value;
    filter.page = 1;
    bankResults();
  }
});
document.addEventListener("change", (event) => {
  if (event.target.id === "task-filter") {
    filter.task = event.target.value;
    filter.page = 1;
    bankResults();
  }
});
document.addEventListener("submit", (event) => {
  if (event.target.id === "answer-form") checkAnswer(event);
});
try {
  catalog = await loadCatalog();
  await render();
  if (!store.available)
    toast("Хранилище недоступно: прогресс может не сохраниться.");
} catch (error) {
  main.innerHTML = empty(
    "repeat",
    "Нужна подготовка данных",
    esc(error.message),
    '<button class="button primary" onclick="location.reload()">Попробовать снова</button>',
  );
}
