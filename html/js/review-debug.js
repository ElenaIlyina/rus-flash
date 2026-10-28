/** Local debugging only; acceptance is not teacher signoff or a learning event. */
import { esc } from "./ui.js";
const KEY = "slovo_review_debug_v1";
const ACCEPTED = "slovo_review_acceptances_v1";
export function debugEnabled() {
  try {
    return localStorage.getItem(KEY) === "true";
  } catch {
    return false;
  }
}
export function setDebugEnabled(value) {
  localStorage.setItem(KEY, String(value));
}
function approvals() {
  try {
    const value = JSON.parse(localStorage.getItem(ACCEPTED) || "{}");
    return value && typeof value === "object" && !Array.isArray(value)
      ? value
      : {};
  } catch {
    return {};
  }
}
export function accepted(entry) {
  return approvals()[entry.id] === entry.version;
}
export function toggleAccepted(entry) {
  const values = approvals();
  if (accepted(entry)) delete values[entry.id];
  else values[entry.id] = entry.version;
  localStorage.setItem(ACCEPTED, JSON.stringify(values));
}
let data;
export async function loadReviewDebug() {
  if (!data) {
    const response = await fetch(
      new URL("../assets/data/review-debug.json", import.meta.url),
    );
    if (!response.ok) throw new Error("Не удалось загрузить данные ревью");
    data = await response.json();
  }
  return data;
}
export function debugSettings() {
  return `<details class="debug-settings"><summary>Отладка</summary><p>Локальные инструменты проверки материалов. Отметки не влияют на обучение и не означают предметную приёмку.</p><button type="button" class="button secondary" data-action="debug-toggle">${debugEnabled() ? "Выключить ревью карточек" : "Включить ревью карточек"}</button>${debugEnabled() ? '<p><a class="text-link" href="#debug">Открыть очередь ревью →</a></p>' : ""}</details>`;
}
export function debugBadge(entry) {
  return entry
    ? `<span class="debug-badge">DEBUG · ${entry.issues.length ? "Есть замечания · " : ""}${accepted(entry) ? "Принято локально" : "На ревью"}</span>`
    : "";
}
export function debugPanel(entry) {
  return entry
    ? `<aside class="debug-panel"><strong>Отладка · ${esc(entry.id)}</strong>${debugBadge(entry)}<p>Проверить: ${entry.parts.map(esc).join(", ")}.</p>${entry.issues.map((issue) => `<p>Замечание: ${esc(issue)}</p>`).join("")}<p>Принятие относится к текущей версии и хранится только в этом браузере. Открытые замечания сохраняются.</p><div class="progress-actions"><button class="button secondary" data-action="debug-accept" data-card="${entry.id}">${accepted(entry) ? "Вернуть на ревью" : "Разбор принят"}</button><a class="text-link" href="#debug">Очередь ревью</a></div></aside>`
    : "";
}
export function debugPage(entries, filter) {
  const pending = entries.filter((e) => !accepted(e));
  const list = entries.filter((e) =>
    filter === "issues"
      ? e.issues.length
      : filter === "accepted"
        ? accepted(e)
        : filter === "all"
          ? true
          : !accepted(e),
  );
  return `<div class="page-heading"><div><span class="eyebrow">DEBUG</span><h1>Ревью карточек</h1><p>На ревью: ${pending.length}. Локальное принятие не меняет данные проекта или учебный прогресс.</p></div><a class="text-link" href="#settings">Настройки</a></div><nav class="progress-actions" aria-label="Фильтр ревью">${[
    ["pending", "На ревью"],
    ["issues", "Есть замечания"],
    ["accepted", "Приняты"],
    ["all", "Все"],
  ]
    .map(
      ([id, label]) =>
        `<a class="button quiet" href="#debug?filter=${id}" ${filter === id ? 'aria-current="page"' : ""}>${label}</a>`,
    )
    .join(
      "",
    )}</nav><div class="card-list">${list.map((entry) => `<a class="bank-row" href="#card/${entry.id}"><div><strong>${entry.id}</strong>${debugBadge(entry)}<p>${entry.parts.map(esc).join(", ")}</p></div></a>`).join("") || "<p>Карточек в этой очереди нет.</p>"}</div>`;
}
