import { esc } from "./ui.js";
import { labels } from "./learning.js";
const states = ["demonstrated", "due", "practicing", "not_started"];
function bar(counts, total) {
  return `<div class="skill-bar" role="img" aria-label="${states.map((s) => labels[s] + ": " + counts[s]).join(", ")}">${states
    .filter((s) => counts[s])
    .map(
      (s) =>
        `<span class="skill-segment ${s}" style="width:${total ? (100 * counts[s]) / total : 0}%" aria-hidden="true"></span>`,
    )
    .join("")}</div>`;
}
function legend(counts) {
  return `<div class="skill-legend">${states.map((s) => `<span><i class="status-swatch ${s}" aria-hidden="true"></i>${labels[s]}<b>${counts[s]}</b></span>`).join("")}</div>`;
}
export function renderGlobalProgress(p) {
  return `<section class="home-coverage aggregate-progress" aria-label="Суммарный прогресс по карточкам"><div class="home-coverage-title"><h2>Общий прогресс</h2><a href="#progress">Подробнее →</a></div>${bar(p.counts, p.total)}<div class="aggregate-caption"><span>Охват ${p.covered} / ${p.total}</span><span>Пора повторить: ${p.counts.due}</span></div>${legend(p.counts)}<p class="home-coverage-caption">Охват показывает, сколько карточек вы попробовали. Закрепление зависит от оценок завершённых решений.</p></section>`;
}
export function renderLearningProgress(p, catalog, topics) {
  return `<div class="page-heading"><div><span class="eyebrow">ЗАМЕЧАЙТЕ СВОИ ШАГИ</span><h1>Мой прогресс</h1><p>Охват карточек и закрепление по группам заданий — разные показатели.</p></div><div class="progress-actions"><button class="button secondary" data-action="export">Скачать прогресс</button><button class="button secondary" data-action="import">Загрузить прогресс</button><a class="text-link" href="#progress?view=history">История занятий</a><a class="text-link" href="#settings">Настройки обучения</a></div></div>
  <section class="learning-overview"><div class="consolidation"><span class="eyebrow">ЗАКРЕПЛЕНИЕ ГРУПП</span><div class="learning-number">${p.consolidation ?? "—"}<span>%</span></div><h2>Получается по ${p.consolidated} из ${p.skillTotal} групп</h2><p>«Получается» и «пора повторить» входят в закрепление.</p><details class="metric-explainer"><summary>Как это считается?</summary><p>Верно с первой попытки — 1; с n-й попытки — 1/n; с подсказкой — 0. Чтение правила не снижает результат. Оценка темы обновляется один раз после завершения решения. «Получается» — выше ${p.settings.masteryThreshold}; повторение через ${p.settings.reviewDays} дн. Коэффициенты и вес упражнений можно изменить в настройках. Ручная отметка «изучено» не влияет на оценку.</p></details></div><div class="coverage-panel"><span class="eyebrow">ОХВАТ КАРТОЧЕК</span><div class="coverage-number">${p.coverage ?? "—"}<span>%</span></div><h3>Попробовали ${p.covered} из ${p.total}</h3><div class="coverage-track"><span style="width:${p.coverage || 0}%"></span></div><p>Уникальные карточки с попытками, включая ответы с подсказкой. Повтор той же карточки не увеличивает охват.</p><details class="metric-explainer"><summary>Какие ответы учитываются?</summary><p>Для оценок учитываются завершённые решения карточек с проверенным эталоном актуального формата. Результат с подсказкой равен нулю. Если задание изменилось, его нужно решить заново; прежние попытки сохраняются в истории и охвате.</p></details></div></section>
  <section class="topic-coverage"><div class="section-heading"><div><h2>По крупным темам</h2><p>Полосы показывают статусы карточек. Откройте тему, чтобы увидеть группы заданий.</p></div></div>${legend(p.counts)}<div class="coverage-topics">${topics
    .map((t) => {
      const cards = catalog.cards.filter((c) => t.tasks.includes(c.task));
      const counts = Object.fromEntries(
        states.map((s) => [
          s,
          cards.filter((c) => p.cardStates.get(c.id) === s).length,
        ]),
      );
      return `<details class="coverage-topic"><summary><div class="coverage-topic-heading"><h3>${esc(t.name)}</h3><span>Охват ${cards.length - counts.not_started} / ${cards.length}</span></div>${bar(counts, cards.length)}</summary><div class="skill-detail">${p.groups
        .filter((g) => t.tasks.includes(g.id))
        .map(
          (g) =>
            `<details class="skill-row"><summary><span class="skill-dot ${g.status}" aria-hidden="true"></span><span>№${g.id}. ${esc(g.name)}</span><span class="skill-status-text">${labels[g.status]}</span></summary><div class="skill-reason"><p>${esc(g.reason)}</p><p>Пул с проверенными ответами: ${g.eligible} из ${g.total}; карточек попробовано: ${g.attempted}. ${g.dueAt ? "Срок повторения: " + new Date(g.dueAt).toLocaleString("ru-RU") + "." : ""}</p>${g.eligible ? `<a class="text-link" href="#bank?task=${g.id}&status=verified">Перейти к практике →</a>` : "<p>Для закрепления этой группы пока не хватает готовых материалов.</p>"}</div></details>`,
        )
        .join("")}</div></details>`;
    })
    .join(
      "",
    )}</div><p class="coverage-hint">Карточки без точной позиции по проекту-2027 остаются в общем охвате, но не приписываются теме автоматически.</p></section>`;
}
