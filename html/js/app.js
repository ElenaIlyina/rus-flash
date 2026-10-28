import {
  loadSettings,
  saveSettings,
  renderSettings,
  defaults,
  coefficientForRetention,
  adjustSetting,
} from "./settings.js";
import { knowledgePage } from "./knowledge.js";
import { recommendPractice } from "./adaptive.js";
import { checkResponse } from "./assessment.js";
import { orderCards } from "./bank-order.js";
import { projectProgress, labels } from "./learning.js";
import { renderGlobalProgress, renderLearningProgress } from "./progress.js";
import { strategyHint } from "./hints.js";
import { icon, esc, rich, plain, num } from "./ui.js";
import { parseProgress, mergeProgress } from "./progress-transfer.js";
import { loadCatalog, loadCard } from "./data.js";
import { store } from "./store.js";

const main = document.querySelector("#main");
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
  reveal = false;
let pendingImport = null;
const shuffleSeed = Math.floor(Math.random() * 0xffffffff);
let filter = {
  query: "",
  task: "",
  status: "all",
  page: 1,
  sort: "practice",
  availability: "verified",
};
function topicCards(topic) {
  return catalog.cards.filter((c) => topic.tasks.includes(c.task));
}
// Hash navigation and learner-facing screens.
function route() {
  const [path, query] = location.hash.slice(1).split("?");
  return { path: path || "study", params: new URLSearchParams(query) };
}
function heading(kicker, title, subtitle, action = "") {
  return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;
}
function learning() {
  return projectProgress(catalog, store.history, Date.now(), loadSettings());
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
  const progress = learning();
  const recommendation = recommendPractice({
    catalog,
    progress,
    tags: (id) => store.tags(id),
    seed: shuffleSeed,
  });
  const candidate =
    catalog.cards.find(
      (c) => c.id === store.lastCard && c.eligibleForProgress,
    ) ||
    catalog.cards.find((c) => c.id === recommendation.cardId) ||
    catalog.cards[0];
  main.innerHTML = `
    <div class="study-intro">
      <section class="hero study-hero" aria-labelledby="hero-title">
        <div class="hero-copy"><span class="eyebrow">РУССКИЙ ЯЗЫК · В СВОЁМ ТЕМПЕ</span><h1 id="hero-title">Не всё сразу.<br>Начнём с одной карточки.</h1><p>Разобраться в правиле. Попробовать.<br> И однажды заметить: получается.</p><section class="stat-strip" aria-label="Ваши результаты"><div>${icon("bank")}<span><strong>${num(catalog.cards.length)}</strong><small>карточек в банке</small></span></div><div>${icon("check")}<span><strong>${s.practiced.size}</strong><small>карточек попробовано</small></span></div><div>${icon("bookmark")}<span><strong>${catalog.cards.filter((c) => store.tags(c.id).fav).length}</strong><small>в избранном</small></span></div></section>${renderGlobalProgress(learning())}</div>
      </section>
      <a class="study-poster" href="#card/${candidate.id}" aria-label="Начать заниматься"><div class="poster-face"><span class="poster-art" aria-hidden="true"><svg class="poster-glyph" viewBox="0 0 300 260" fill="none"><g fill="currentColor" transform="rotate(-9 130 130)"><path d="M62 18h27v27H62zM122 18h27v27h-27zM62 72h113v27H90v37h76v27H90v39h85v27H62z"/></g><g fill="#ff7952" transform="rotate(10 220 165)"><path d="M209 99h26l-3 103h-20zM209 216h26v26h-26z"/></g></svg></span><span class="poster-cta">Начать заниматься</span><span class="poster-arrow">${icon("arrow")}</span></div></a>

    </div>
    <section class="study-topics" aria-labelledby="topics-title"><div class="section-heading"><div><span class="eyebrow">ОТ ПРОСТОГО К ПОНЯТНОМУ</span><h2 id="topics-title">Что разберём сегодня?</h2></div><a class="text-link" href="#bank">Весь банк ${icon("arrow")}</a></div><div class="topic-grid topic-notes">${topics.map((t, i) => `<a class="topic-card topic-note ${t.color}" href="#bank?topic=${i}"><span class="note-tape" aria-hidden="true"></span><span class="eyebrow">${String(i + 1).padStart(2, "0")} / ВЫБЕРИ НАПРАВЛЕНИЕ</span><span class="topic-icon">${icon(t.icon)}</span><h3>${t.name}</h3><p>${t.detail}</p><span class="note-number" aria-hidden="true">${String(i + 1).padStart(2, "0")}</span><span class="note-bottom"><span class="topic-count">${num(topicCards(t).length)} карточек</span><span class="note-open">Открыть ${icon("arrow")}</span></span></a>`).join("")}</div></section>`;
}
function bankResults() {
  const topic = route().params.get("topic");
  const progress = learning();
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
    if (filter.availability === "verified" && !c.hasVerifiedAnswer)
      return false;
    if (filter.availability === "missing" && c.hasAnswer) return false;
    if (
      filter.availability === "unverified" &&
      (!c.hasAnswer || c.hasVerifiedAnswer)
    )
      return false;
    const tried = progress.cardStates.get(c.id) !== "not_started";
    const tags = store.tags(c.id);
    return (
      filter.status === "all" ||
      (filter.status === "new" && !tried) ||
      (filter.status === "practiced" && tried) ||
      (filter.status === "due" && progress.cardStates.get(c.id) === "due") ||
      (filter.status === "fav" && tags.fav) ||
      (filter.status === "hard" && tags.hard)
    );
  });
  const ordered = orderCards(
    list,
    filter.sort,
    progress,
    store.history,
    (id) => store.tags(id),
    shuffleSeed,
  );
  const area = main.querySelector("#bank-results");
  if (!area) return;
  const filterHelp = main.querySelector("#bank-filter-help");
  if (filterHelp)
    filterHelp.textContent =
      {
        fav: "Избранное — ваши закладки. Звезда помогает вернуться к карточке и не влияет на оценку знаний.",
        hard: "Вы сами отметили эти карточки кнопкой «Повторить позже». Это отдельная отметка, а не автоматический статус.",
        due: "Пришло время повторить эти карточки.",
        new: "В этом браузере пока нет сохранённых попыток по этим карточкам.",
        practiced:
          "Есть хотя бы одна отправленная попытка. Это ещё не означает «получается».",
      }[filter.status] ||
      "Фильтры выше — ваша практика. «Эталон» ниже — готовность ответа для проверки.";
  area.innerHTML =
    `<div class="results-meta">Найдено ${num(list.length)} ${topic !== null ? '<a href="#bank" class="text-link">Сбросить тему ×</a>' : ""}</div>` +
    (list.length
      ? `<div class="card-list">${ordered
          .slice(0, filter.page * 24)
          .map(
            (c) =>
              `<a class="bank-row" href="#card/${c.id}"><span class="row-icon group-number" aria-label="Группа ${c.task || "не определена"}">${esc(c.task || "—")}</span><div><div class="row-top"><span>${c.id}</span>${store.tags(c.id).fav ? '<span class="bank-favorite" aria-label="В избранном">⭐</span>' : ""}</div><h3>${esc(plain(c.title))}</h3><span class="row-status ${c.hasAnswer ? "" : "muted"}">${c.hasVerifiedAnswer ? "Ответ ранее проверялся ФИПИ" : c.hasAnswer ? "Эталон ещё не проверен" : "Эталон ещё не подготовлен"}${c.formatStatus === "historical_format" ? " · прежний формат" : ""}</span></div>${icon("arrow")}</a>`,
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
  if (params.has("task")) filter.task = params.get("task");
  if (params.get("status") === "verified") {
    filter.availability = "verified";
    filter.status = "all";
  } else if (params.get("status") === "due") filter.status = "due";
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
    <div class="filter-tabs" aria-label="Ваша практика">${[
      ["all", `${icon("bank")} Все карточки`],
      ["new", `${icon("leaf")} Не пробовал`],
      ["practiced", `${icon("check")} Уже пробовал`],
      ["due", `${icon("clock")} Пора повторить`],
      ["fav", '<span aria-hidden="true">⭐</span> Избранное'],
      ["hard", '<span aria-hidden="true">⏳</span> Повторить позже'],
    ]
      .map(
        ([id, label]) =>
          `<button class="filter-tab ${filter.status === id ? "active" : ""}" data-filter="${id}" aria-pressed="${filter.status === id}">${label}</button>`,
      )
      .join(
        "",
      )}</div><p id="bank-filter-help" class="bank-filter-help"></p><div class="bank-secondary-tools"><label class="select-field bank-sort"><span>Эталон:</span><select id="answer-availability" aria-label="Наличие и проверка эталона">${[
      ["verified", "Ответ проверялся ФИПИ"],
      ["all", "Все материалы"],
      ["unverified", "Ответ ещё не проверен"],
      ["missing", "Ответ ещё не подготовлен"],
    ]
      .map(
        ([value, label]) =>
          `<option value="${value}" ${filter.availability === value ? "selected" : ""}>${label}</option>`,
      )
      .join(
        "",
      )}</select></label><label class="select-field bank-sort"><span>Порядок:</span><select id="bank-sort" aria-label="Порядок карточек">${[
      ["practice", "Для практики"],
      ["exam", "По позициям ЕГЭ"],
      ["shuffle", "Перемешать"],
    ]
      .map(
        ([value, label]) =>
          `<option value="${value}" ${filter.sort === value ? "selected" : ""}>${label}</option>`,
      )
      .join("")}</select></label></div><div id="bank-results"></div>`;
  bankResults();
}
async function renderCard(id, version) {
  currentCard = null;
  main.innerHTML =
    '<div class="loading-state" role="status">Открываем карточку…</div>';
  const c = await loadCard(id);
  if (version !== renderVersion) return;
  currentCard = c;
  const assignment = store.assignment(c.id);
  reveal = assignment.assisted;
  store.remember(c.id);
  const meta = catalog.cards.find((v) => v.id === id);
  Object.assign(c, meta || {});
  const tags = store.tags(id);
  const status = learning().cardStates.get(id);
  const canCheck = Boolean(c.answer && !c.reviewNote);
  main.innerHTML = `<div class="card-breadcrumb"><a class="text-link" href="#bank">${icon("back")} К банку заданий</a><span>Группа ${meta?.task || "—"} · ${esc(id)}</span></div>
    <div class="practice-layout"><article class="exercise"><div class="exercise-header"><span class="eyebrow">КАРТОЧКА ${id}</span><button class="icon-button ${tags.fav ? "selected" : ""}" data-action="favorite" aria-label="В избранное" aria-pressed="${!!tags.fav}">${icon("bookmark")}</button></div>
      <h1 class="exercise-title">${esc(catalog.taskNames[meta?.task] || "Практика русского языка")}</h1><div class="exercise-status"><span class="pill ${c.answer ? "sage-pill" : "neutral-pill"}">${c.hasVerifiedAnswer ? "Ответ ранее проверялся ФИПИ" : c.answer ? "Ответ из текущей базы" : "Самостоятельная проверка"}</span>${c.formatStatus === "historical_format" ? "<span>Прежний формат задания</span>" : ""}<span class="pill neutral-pill" data-learning-status>${labels[status]}</span><span data-learning-score>Оценка карточки: ${learning().cardScores.get(id) === null ? "ещё нет" : learning().cardScores.get(id).toFixed(3)}</span></div>
      ${c.passage ? `<details class="passage" open><summary>${icon("knowledge")} Текст к заданию<span>Свернуть / раскрыть</span></summary><div class="passage-content">${rich(c.passage)}</div></details>` : ""}
      ${c.reviewNote ? `<p class="feedback warning">${esc(c.reviewNote)}</p>` : ""}<section class="question-section" aria-labelledby="question-label"><h2 id="question-label">Задание</h2><div class="question-text">${rich(c.instruction)}</div></section>
      ${c.errors.length && c.sentences.length ? `<div class="matching"><section><h3>Грамматические ошибки</h3>${c.errors.map((x, i) => `<p><b>${"АБВГДЕ"[i] || i + 1}.</b> ${rich(x)}</p>`).join("")}</section><section><h3>Предложения</h3>${c.sentences.map((x, i) => `<p><b>${i + 1}.</b> ${rich(x)}</p>`).join("")}</section></div>` : ""}
      ${c.options.length ? `<fieldset class="options"><legend>${c.responseType === "multiple_choice" ? "Выберите верные варианты" : "Варианты к заданию"}</legend>${c.options.map((x, i) => (c.responseType === "multiple_choice" ? `<label class="option"><input type="checkbox" name="answer-option" value="${i + 1}"><span>${rich(x)}</span></label>` : `<div class="option static-option"><span class="option-number">${i + 1}</span><span>${rich(x)}</span></div>`)).join("")}</fieldset>` : ""}
      <form id="answer-form" class="answer-form">${c.responseType !== "multiple_choice" ? `<label for="answer-input">${c.answer ? "Ваш ответ" : "Ваш ответ для самопроверки"}</label><input id="answer-input" autocomplete="off" placeholder="Введите ответ" ${c.answer ? "required" : ""}>` : ""}<div class="answer-actions">${canCheck ? `<button type="submit" class="button primary">Проверить ${icon("check")}</button>` : '<p class="muted">Автоматическая проверка недоступна: нет эталона или материал требует сверки.</p>'}<button type="button" class="button quiet" data-action="hint">Подсказка</button><button type="button" class="button quiet" data-action="reveal">${c.answer ? "Ответ и разбор" : "Открыть разбор"}</button></div></form>
      <section id="hint" class="aside-card" hidden aria-live="polite"></section><div id="answer-feedback" aria-live="polite"></div><button class="text-link" data-action="new-attempt">Начать новую попытку</button><section id="explanation" class="explanation" hidden></section>
      <div class="exercise-bottom"><button class="button quiet ${tags.hard ? "selected" : ""}" data-action="repeat" aria-pressed="${!!tags.hard}">${icon("repeat")} Повторить позже</button><button class="button secondary ${tags.studied ? "selected" : ""}" data-action="studied" aria-pressed="${!!tags.studied}">${icon("check")} ${tags.studied ? "Отмечено изученным" : "Отметить изученным"}</button><button class="button primary" data-action="next">Дальше ${icon("arrow")}</button></div>
    </article><aside class="practice-aside"><div class="aside-card"><span class="eyebrow">СНАЧАЛА ПОНИМАНИЕ</span><h2>Правило рядом</h2><p>${c.ruleRefs?.length ? "Вспомните правило и посмотрите примеры по этой теме." : "Найдите нужную тему в справочнике."}</p><div class="rule-links">${(c.ruleRefs || []).map((ref) => `<a class="text-link" href="#knowledge?rule=${esc(ref.id)}&card=${c.id}">${esc(ref.label)}</a>`).join("")}</div><button class="text-link" data-action="card-rules">Открыть справочник ${icon("arrow")}</button></div><div class="aside-tip">${icon("leaf")}<p>Не торопитесь. Можно вернуться к тексту, попробовать ещё раз или отложить карточку.</p></div><button class="text-link" data-action="report">Нашли неточность?</button></aside></div>`;
}
function renderExplanation() {
  const c = currentCard;
  const area = document.querySelector("#explanation");
  area.hidden = false;
  area.innerHTML = `<span class="eyebrow">РАЗБЕРЁМСЯ ВМЕСТЕ</span><h2>${c.answer ? "Ответ: " + esc(c.answer) : "Эталонный ответ ещё не добавлен"}</h2>${c.reviewNote ? `<p class="feedback warning">${esc(c.reviewNote)}</p>` : ""}${c.explanation ? `<div class="explanation-text">${rich(c.explanation)}</div>` : "<p>Объяснение пока недоступно. Можно обратиться к справочнику.</p>"}${c.explanationSourceRefs?.length ? `<details class="explanation-sources"><summary>Источники по рядам задания</summary><nav class="rule-links">${c.explanationSourceRefs.map((ref) => `<a class="text-link" href="#knowledge?source=${esc(ref.sourceId)}&card=${c.id}">Ряд ${ref.part}: ${esc(ref.label)}</a>`).join("")}</nav></details>` : ""}<div class="rule-links">${(c.ruleRefs || []).map((ref) => `<a class="text-link" href="#knowledge?rule=${esc(ref.id)}&card=${c.id}">${esc(ref.label)}</a>`).join("")}</div><button class="text-link" data-action="card-rules">${icon("knowledge")} Связанные правила</button>`;
}
function checkAnswer(event) {
  event.preventDefault();
  const c = currentCard;
  if (!c?.answer || c.reviewNote) return;
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
  const correct = checkResponse(c.responseType, actual, c.answer);
  // One completion result per assignment; intermediate errors remain in history.
  const assignment = store.assignment(c.id);
  if (assignment.completed) {
    area.innerHTML =
      '<p class="feedback success">Результат уже сохранён. Для нового решения нажмите «Начать новую попытку».</p>';
    return;
  }
  const assisted = reveal;
  const submitted = store.attempt(
    c.id,
    correct,
    assisted,
    c.materialVersion || 1,
  );
  const statusLabel = main.querySelector("[data-learning-status]");
  if (statusLabel)
    statusLabel.textContent = labels[learning().cardStates.get(c.id)];
  const scoreLabel = main.querySelector("[data-learning-score]");
  if (scoreLabel) {
    const value = learning().cardScores.get(c.id);
    scoreLabel.textContent =
      "Оценка карточки: " + (value === null ? "ещё нет" : value.toFixed(3));
  }
  const resultLabel = submitted.assisted
    ? "Верно, с подсказкой"
    : submitted.attemptNumber === 1
      ? "Верно с первой попытки"
      : "Верно не с первой попытки";
  const result = submitted.assisted ? 0 : 1 / submitted.attemptNumber;
  area.innerHTML = `<div class="feedback ${correct ? "success" : "warning"}">${icon(correct ? "check" : "repeat")}<div><strong>${correct ? resultLabel : "Пока не совпало. Попробуем ещё?"}</strong><p>${correct ? `Результат: ${result.toLocaleString("ru-RU", { maximumFractionDigits: 3 })} из 1. Можно открыть разбор или перейти дальше.` : "Вернитесь к условию или посмотрите объяснение. Оценка обновится после завершения решения."}</p></div></div>`;
  if (!store.available)
    toast("Не удалось сохранить попытку: проверьте доступ к хранилищу.");
}
function renderProgress(params) {
  if (params.get("view") !== "history") {
    main.innerHTML = renderLearningProgress(learning(), catalog, topics);
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
      '<div class="progress-actions"><a class="button primary" href="#progress">Обзор прогресса</a><button class="button secondary" data-action="export">Скачать прогресс</button><button class="button secondary" data-action="import">Загрузить прогресс</button></div>',
    ) +
    `
    <div class="progress-grid"><div class="metric"><span>Карточек попробовано</span><strong>${s.practiced.size}<small> / ${num(catalog.cards.length)}</small></strong><p>По истории нового интерфейса</p></div><div class="metric"><span>Проверки без подсказок</span><strong>${rate === null ? "—" : rate + "%"}</strong><p>${independent.length ? `${s.correct.length} совпадений из ${independent.length} попыток` : "Появятся после первой проверки"}</p></div><div class="metric"><span>Отмечено изученным</span><strong>${catalog.cards.filter((c) => store.tags(c.id).studied).length}</strong><p>Ручная отметка, не результат проверки</p></div></div>
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
                `<a class="attempt-row" href="#card/${e.cardId}"><span class="attempt-dot ${e.correct ? "correct" : ""}">${icon(e.correct ? "check" : "repeat")}</span><span><strong>Карточка ${e.cardId}</strong><small>${e.correct ? "Ответ совпал" : "Нужно повторить"}${e.assisted ? (e.scoringVersion === 1 ? " · с подсказкой" : " · помощь или повторная отправка") : e.scoringVersion === 1 && e.attemptNumber > 1 ? " · не с первой попытки" : " · с первой попытки"}</small></span><time>${new Date(e.time).toLocaleDateString("ru-RU")}</time></a>`,
            )
            .join("")
        : empty(
            "leaf",
            "Здесь начнётся ваша история",
            "Откройте карточку с ответом и попробуйте её решить.",
            '<a href="#bank" class="button primary">Выбрать карточку</a>',
          )
    }</section>
    <div class="sync-card">${icon("repeat")}<div><h3>На телефоне и компьютере</h3><p>Скачайте файл прогресса и загрузите его на другом устройстве, чтобы продолжить занятия.</p></div><button class="button secondary" data-action="transfer-info">Как перенести прогресс</button></div>`;
}
async function renderKnowledge(params, version) {
  const html = await knowledgePage({ params, catalog, heading, empty });
  if (version === renderVersion) main.innerHTML = html;
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
    : (path === "settings"
        ? "Настройки обучения"
        : navs.find((n) => n[0] === path)?.[1]) || "Заниматься";
  for (const target of ["#desktop-nav", "#mobile-nav"]) {
    const itemsHtml = navs
      .map(
        ([id, label]) =>
          `<a href="#${id}" aria-label="${label}" title="${label}" class="nav-item ${active === id ? "active" : ""}" ${active === id ? 'aria-current="page"' : ""}>${icon(id)}<span>${target === "#mobile-nav" && id === "progress" ? "Прогресс" : label}</span></a>`,
      )
      .join("");
    document.querySelector(target).innerHTML =
      target === "#desktop-nav"
        ? `<div style="padding: 0 0 8px 0;"><img src="https://media.tenor.com/Jojpr9QgMLoAAAAM/maxwell-maxwell-spin.gif" alt="Maxwell spin" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; display: block; margin: 0 auto;" /></div>` +
          itemsHtml
        : itemsHtml;
  }
  try {
    if (path.startsWith("card/")) await renderCard(path.slice(5), version);
    else if (path === "bank") renderBank(params);
    else if (path === "progress") renderProgress(params);
    else if (path === "knowledge") await renderKnowledge(params, version);
    else if (path === "settings")
      main.innerHTML = renderSettings(loadSettings());
    else renderStudy();
  } catch (error) {
    if (version === renderVersion)
      main.innerHTML = empty(
        "repeat",
        "Не получилось открыть",
        esc(error.message),
        '<a href="#bank" class="button secondary">Вернуться в банк</a>',
      );
  }
  if (version === renderVersion) {
    window.scrollTo({ top: 0 });
    document.title = `${path.startsWith("card/") ? "Карточка " + path.slice(5) : (path === "settings" ? "Настройки обучения" : navs.find((n) => n[0] === path)?.[1]) || "Заниматься"} — Слово за слово`;
  }
}

// Delegated interactions shared across screens.
document.addEventListener("click", async (event) => {
  if (event.target.closest('#info-dialog a[href^="#"]'))
    document.querySelector("#info-dialog").close();
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
    case "adjust-setting":
      adjustSetting(
        main.querySelector(`[name="${button.dataset.target}"]`),
        Number(button.dataset.direction),
      );
      break;
    case "retention": {
      const a = coefficientForRetention(Number(button.dataset.retention));
      main.querySelector(`[name="${button.dataset.target}"]`).value = a;
      break;
    }
    case "reset-settings":
      main.innerHTML = renderSettings(defaults);
      break;
    case "about":
      modal(
        "Учиться в своём темпе",
        "<p>Практикуйтесь, разбирайте правила и возвращайтесь к темам, которые хочется закрепить.</p><p><a href='#settings'>Настройки обучения</a></p><p>Прогресс хранится в этом браузере. Чтобы перенести его на другое устройство, скачайте файл прогресса и загрузите его там.</p>",
      );
      break;
    case "transfer-info":
      modal(
        "Продолжить на другом устройстве",
        "<p>Скачайте прогресс здесь и загрузите файл в приложении на другом устройстве. Перед загрузкой вы увидите состав изменений; история объединится с текущими записями.</p><p>Автоматического переноса между устройствами нет.</p>",
      );
      break;
    case "more":
      filter.page++;
      bankResults();
      break;
    case "hint": {
      if (!currentCard) break;
      reveal = true;
      store.markAssignment(currentCard.id, "assisted");
      const area = main.querySelector("#hint");
      area.hidden = false;
      area.innerHTML = `<h3>Подсказка к способу решения</h3><p>${esc(strategyHint(currentCard.task))}</p><p class="muted">Подсказка использована: ответ в этой попытке не считается самостоятельным.</p>`;
      break;
    }
    case "new-attempt":
      if (currentCard) {
        store.assignment(currentCard.id, true);
        await renderCard(currentCard.id, renderVersion);
      }
      break;
    case "reveal":
      if (currentCard) store.markAssignment(currentCard.id, "assisted");
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
      if (!currentCard) break;
      if (filter.sort === "practice") {
        const suggestion = recommendPractice({
          catalog,
          progress: learning(),
          task: currentCard.task,
          excludeIds: [currentCard.id],
          tags: (id) => store.tags(id),
          seed: shuffleSeed,
        });
        if (suggestion.cardId) {
          store.assignment(suggestion.cardId, true);
          location.hash = `card/${suggestion.cardId}`;
        }
        toast(suggestion.reasonText);
      } else {
        const pool = catalog.cards.filter(
          (c) => c.task === currentCard.task && c.id !== currentCard.id,
        );
        const next = orderCards(
          pool,
          filter.sort,
          learning(),
          store.history,
          (id) => store.tags(id),
          shuffleSeed,
        )[0];
        if (next) {
          store.assignment(next.id, true);
          location.hash = `card/${next.id}`;
        } else toast("Других карточек в этой группе пока нет.");
      }
      break;
    }
    case "card-rules":
      if (currentCard) {
        location.hash = `knowledge?card=${currentCard.id}`;
      }
      break;
    case "report":
      modal(
        "Спасибо за внимательность",
        `<p>Карточка <strong>${esc(currentCard?.id)}</strong>. Скопируйте этот номер и описание неточности для автора приложения.</p><p>Сообщить об ошибке можно вне приложения.</p>`,
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
        `<p>Файл: <strong>${esc(file.name)}</strong></p><p>Новых попыток: ${result.added}. Новых отметок: ${result.marksAdded}. Уже есть: ${result.duplicates}.</p>${result.conflicts ? `<p>Конфликтов ID: ${result.conflicts}. Для них сохранятся записи этого устройства.</p>` : ""}${unknown ? `<p>Неизвестных текущему банку карточек: ${unknown}. История сохранится, но не будет учитываться в текущих показателях.</p>` : ""}<p>История объединится без удаления текущих попыток. Отметки из файла добавятся к существующим; снятые отметки не удаляют выбранные на этом устройстве.</p><div class="progress-actions"><button class="button secondary" data-action="export">Скачать текущую копию</button><button class="button primary" data-action="apply-import">Объединить прогресс</button></div>`,
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
  if (event.target.id === "answer-availability") {
    filter.availability = ["all", "verified", "unverified", "missing"].includes(
      event.target.value,
    )
      ? event.target.value
      : "verified";
    filter.page = 1;
    bankResults();
  }
  if (event.target.id === "bank-sort") {
    filter.sort = ["practice", "exam", "shuffle"].includes(event.target.value)
      ? event.target.value
      : "practice";
    filter.page = 1;
    bankResults();
  }
  if (event.target.id === "task-filter") {
    filter.task = event.target.value;
    filter.page = 1;
    bankResults();
  }
});
document.addEventListener("submit", (event) => {
  if (event.target.id === "answer-form") checkAnswer(event);
  if (event.target.id === "learning-settings") {
    event.preventDefault();
    try {
      const value = Object.fromEntries(
        [...new FormData(event.target)].map(([key, value]) => [
          key,
          Number(value),
        ]),
      );
      saveSettings(value);
      main.querySelector("#settings-feedback").textContent =
        "Настройки сохранены. Оценки пересчитаны.";
    } catch (error) {
      main.querySelector("#settings-feedback").textContent = error.message;
    }
  }
});
document.addEventListener("keydown", (event) => {
  if (
    event.target.matches('.settings-form input[type="number"]') &&
    ["ArrowUp", "ArrowDown"].includes(event.key)
  ) {
    event.preventDefault();
    adjustSetting(event.target, event.key === "ArrowUp" ? 1 : -1);
  }
});
window.addEventListener("hashchange", () => {
  filter.page = 1;
  render();
});
try {
  catalog = await loadCatalog();
  const legacy = new URLSearchParams(location.search);
  if (!location.hash && legacy.get("id"))
    location.hash = `card/${legacy.get("id").toUpperCase()}`;
  else if (!location.hash && legacy.get("task")) {
    filter.task = legacy.get("task");
    location.hash = "bank";
  } else await render();
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
