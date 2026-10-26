/** Explicitly synthetic data. Never read or write learner history. */
const sample = [
  {
    name: "Орфография",
    skills: [
      ["Проверяемые гласные в корне", "demonstrated"],
      ["Правописание приставок", "demonstrated"],
      ["Личные окончания глаголов", "due"],
      ["Суффиксы причастий", "practicing"],
      ["НЕ с разными частями речи", "practicing"],
      ["Н и НН", "not_started"],
    ],
  },
  {
    name: "Пунктуация",
    skills: [
      ["Грамматическая основа", "demonstrated"],
      ["Однородные члены", "due"],
      ["Обособленные определения", "practicing"],
      ["Вводные конструкции", "practicing"],
      ["Границы придаточного", "not_started"],
      ["Разные виды связи", "not_started"],
    ],
  },
  {
    name: "Нормы языка",
    skills: [
      ["Ударение в словах", "demonstrated"],
      ["Различение паронимов", "demonstrated"],
      ["Лексическая избыточность", "due"],
      ["Формы числительных", "practicing"],
      ["Согласование подлежащего и сказуемого", "practicing"],
      ["Управление", "not_started"],
    ],
  },
  {
    name: "Работа с текстом",
    skills: [
      ["Поиск подтверждения в тексте", "demonstrated"],
      ["Значение слова в контексте", "practicing"],
      ["Связь предложений", "practicing"],
      ["Типы речи", "not_started"],
      ["Средства выразительности", "not_started"],
      ["Объяснение связи примеров", "not_started"],
    ],
  },
];
const states = [
  ["demonstrated", "Получается"],
  ["due", "Пора повторить"],
  ["practicing", "Практикую"],
  ["not_started", "Не пробовал"],
];
export function previewTopics(scenario = "example") {
  let moved = 0;
  return sample.map((t) => ({
    ...t,
    skills: t.skills.map(([name, status]) => {
      if (scenario === "start") status = "not_started";
      if (scenario === "later" && status === "demonstrated" && moved < 2) {
        status = "due";
        moved++;
      }
      return { name, status };
    }),
  }));
}
export function summarize(skills) {
  const counts = Object.fromEntries(
    states.map(([id]) => [id, skills.filter((s) => s.status === id).length]),
  );
  const total = skills.length,
    consolidated = counts.demonstrated + counts.due,
    covered = total - counts.not_started;
  return {
    counts,
    total,
    consolidated,
    covered,
    consolidation: total ? Math.round((consolidated / total) * 100) : null,
    coverage: total ? Math.round((covered / total) * 100) : null,
  };
}
const link = (scenario, extra = "") =>
  `progress.html?view=preview&scenario=${scenario}${extra}`;
function bar(s) {
  const label = states
    .map(([id, name]) => `${name}: ${s.counts[id]}`)
    .join(", ");
  return `<div class="skill-bar" role="img" aria-label="${label}">${states.map(([id]) => (s.counts[id] ? `<span class="skill-segment ${id}" style="width:${(s.counts[id] / s.total) * 100}%" aria-hidden="true"></span>` : "")).join("")}</div>`;
}
function legend(s) {
  return `<div class="skill-legend">${states.map(([id, label]) => `<span><i class="status-swatch ${id}" aria-hidden="true"></i>${label}<b>${s.counts[id]}</b></span>`).join("")}</div>`;
}
function skillRow(skill) {
  const label = states.find(([id]) => id === skill.status)[1];
  const reason = {
    demonstrated:
      "Пример основания: самостоятельные решения на разных карточках и успешная проверка после перерыва.",
    due: "Раньше получалось. В этом примере наступил срок повторения — достижение остаётся засчитанным.",
    practicing:
      "Практика уже есть, но самостоятельных устойчивых результатов пока недостаточно.",
    not_started:
      "В этом примере попыток по навыку ещё не было. Это не оценка способностей.",
  }[skill.status];
  return `<details class="skill-row"><summary><span class="skill-dot ${skill.status}" aria-hidden="true"></span><span>${skill.name}</span><span class="skill-status-text">${label}</span><span class="skill-chevron" aria-hidden="true">+</span></summary><div class="skill-reason"><span class="eyebrow">ДЕМОНСТРАЦИОННОЕ ОСНОВАНИЕ</span><p>${reason}</p><p>Здесь будут связанные правила, упражнения и отдельная самооценка. В прототипе они ещё не подключены к этому навыку.</p></div></details>`;
}
export function renderProgressPreview(params) {
  const scenario = ["example", "later", "start"].includes(
    params.get("scenario"),
  )
    ? params.get("scenario")
    : "example";
  const topics = previewTopics(scenario),
    all = summarize(topics.flatMap((t) => t.skills));
  const requested = params.get("topic");
  const selected =
    requested !== null && /^[0-3]$/.test(requested) ? Number(requested) : null;
  const dueOnly = params.get("due") === "1";
  return `<div class="page-heading"><div><span class="eyebrow">ВИДЕТЬ НЕ ТОЛЬКО ШАГИ, НО И РЕЗУЛЬТАТ</span><h1>Мой прогресс</h1><p>Что уже попробовали. Что получается. К чему стоит вернуться.</p></div><div class="progress-actions"><button class="button secondary" data-action="export">Скачать прогресс</button><button class="button secondary" data-action="import">Загрузить прогресс</button><a class="text-link" href="progress.html?view=history">Моя реальная история</a></div></div>
    <div class="preview-warning"><span class="preview-badge">ДЕМО</span><p><strong>Пример будущего дашборда.</strong> Числа и навыки иллюстративные. Они не рассчитаны из ваших попыток и не сохраняются в прогресс.</p></div>
    <nav class="preview-scenarios" aria-label="Примеры состояния прогресса">${[
      ["example", "Есть первые результаты"],
      ["later", "Наступило повторение"],
      ["start", "В самом начале"],
    ]
      .map(
        ([id, name]) =>
          `<a href="${link(id)}" ${scenario === id ? 'aria-current="true"' : ""}>${name}</a>`,
      )
      .join("")}</nav>
    <section class="learning-overview" aria-label="Пример охвата и закрепления"><div class="consolidation"><span class="eyebrow">ЗАКРЕПЛЕНИЕ</span><div class="learning-number">${all.consolidation}<span>%</span></div><h2>Получается по ${all.consolidated} из ${all.total} навыков</h2><p>Самостоятельно, на разных примерах.<br>Повторение не обнуляет достижение.</p><details class="metric-explainer"><summary>Как это считается?</summary><p>«Получается» и «пора повторить» вместе / все навыки модуля. В примере: ${all.consolidated} / ${all.total}. Это не прогноз балла ЕГЭ.</p></details></div><div class="coverage-panel"><span class="eyebrow">ОХВАТ</span><div class="coverage-number">${all.coverage}<span>%</span></div><h3>Попробовали ${all.covered} из ${all.total}</h3><div class="coverage-track" role="img" aria-label="Охват: ${all.covered} из ${all.total}"><span style="width:${all.coverage}%"></span></div><p>Широта практики, а не число решённых карточек. Попытки с подсказкой тоже помогают познакомиться с темой.</p><details class="metric-explainer"><summary>Чем отличается от закрепления?</summary><p>Охват растёт, когда пробуете новый навык. Закрепление — когда достаточно свидетельств, что он получается. Повторы одного навыка не увеличивают охват.</p></details></div></section>
    <div class="review-invitation"><span class="review-clock" aria-hidden="true">↻</span><div><h3>${all.counts.due ? `${all.counts.due} ${all.counts.due === 3 ? "навыка" : "навыков"} пора освежить` : "Повторение появится, когда придёт время"}</h3><p>${scenario === "later" ? "Срок наступил ещё у двух навыков. Закрепление осталось 38% — знания не исчезли по календарю." : all.counts.due ? "Они уже входят в закрепление. Короткая практика поможет сохранить уверенность." : "Не нужно успеть всё сразу. Начните с интересной темы."}</p></div>${all.counts.due ? `<a class="button secondary" href="${link(scenario, "&due=1")}">Посмотреть навыки</a>` : ""}</div>
    <section class="topic-coverage"><div class="section-heading"><div><span class="eyebrow">ОТ ОБЩЕЙ КАРТИНЫ К КОНКРЕТНОМУ ШАГУ</span><h2>По крупным темам</h2><p>Одна полоса — вся тема. Нажмите, чтобы увидеть навыки.</p></div></div>${legend(all)}<div class="coverage-topics">${topics
      .map((t, i) => {
        const s = summarize(t.skills);
        return `<a class="coverage-topic ${selected === i ? "is-selected" : ""}" href="${link(scenario, `&topic=${i}`)}" ${selected === i ? 'aria-current="true"' : ""}><div class="coverage-topic-heading"><h3>${t.name}</h3><span><b>${s.consolidated}</b> / ${s.total} закреплено <span aria-hidden="true">→</span></span></div>${bar(s)}<div class="coverage-topic-foot"><span>Охват ${s.covered} / ${s.total}</span><span>${s.counts.due ? `Пора повторить: ${s.counts.due}` : "Повторение пока не нужно"}</span></div></a>`;
      })
      .join("")}</div></section>
    ${selected !== null || dueOnly ? `<section class="panel skill-detail" id="skill-detail"><div class="section-heading"><div><span class="eyebrow">ПРИМЕР КАРТЫ НАВЫКОВ</span><h2>${dueOnly ? "Пора повторить" : topics[selected].name}</h2><p>Нажмите на навык — увидите основание статуса.</p></div><a class="text-link" href="${link(scenario)}">Свернуть ×</a></div>${(dueOnly ? topics.flatMap((t) => t.skills).filter((s) => s.status === "due") : topics[selected].skills).map(skillRow).join("")}${!dueOnly ? `<a class="button secondary" href="bank.html?topic=${selected}">Посмотреть текущий банк по теме →</a><p class="skill-bank-note">Переход к существующим карточкам. Точное соответствие этим демонстрационным навыкам ещё не размечено.</p>` : ""}</section>` : '<p class="coverage-hint">Выберите тему выше: внутри — понятные статусы и основания, без сложного графа.</p>'}
    <details class="quality-disclosure"><summary>А насколько готов сам банк?</summary><p>Это отдельный показатель качества материалов, а не ваших знаний. В рабочей версии здесь появятся проверенность ответов, объяснений и покрытие навыков упражнениями. Недоступный материал не должен уменьшать знаменатель и искусственно повышать ваш процент.</p></details>`;
}

/** Layout-only distribution over the entire catalog; not inferred from attempts. */
export function renderGlobalCardProgressPreview(total) {
  const weights = [6, 3, 8, 7];
  const exact = weights.map((weight) => (total * weight) / 24);
  const values = exact.map(Math.floor);
  const remaining = total - values.reduce((sum, value) => sum + value, 0);
  const order = exact
    .map((value, i) => ({ i, fraction: value - values[i] }))
    .sort((a, b) => b.fraction - a.fraction || a.i - b.i);
  for (let i = 0; i < remaining; i++) values[order[i].i]++;
  const counts = Object.fromEntries(states.map(([id], i) => [id, values[i]]));
  const summary = { total, counts };
  return `<section class="home-coverage aggregate-demo" aria-label="Пример суммарного прогресса по всем карточкам"><div class="home-coverage-title"><h2>Общий прогресс <span class="aggregate-demo-badge">ДЕМО</span></h2><a href="progress.html">Подробнее →</a></div>${bar(summary)}<div class="aggregate-caption"><span>Охват ${total - counts.not_started} / ${total}</span><span>Пора повторить: ${counts.due}</span></div>${legend(summary)}<p class="home-coverage-caption">Пример статусов по всему банку, а не по отдельным темам. Числа демонстрационные: оценивание карточек ещё не подключено.</p></section>`;
}
