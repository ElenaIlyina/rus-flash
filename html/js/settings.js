/** Author-approved scoring profile; preferences stay on the current device. */
export const coefficientForRetention = (retention, answers = 10) =>
  retention ** (-1 / answers) - 1;
export const defaults = Object.freeze({
  cardA: coefficientForRetention(0.0001),
  topicA: coefficientForRetention(0.01),
  masteryThreshold: 0.75,
  reviewDays: 7,
  simpleWeight: 0.5,
});
const limits = {
  cardA: [0.0001, 1000],
  topicA: [0.0001, 1000],
  masteryThreshold: [0, 1],
  reviewDays: [0.1, 3650],
  simpleWeight: [0, 1],
};
const KEY = "slovo_learning_settings_v1";
const steps = {
  cardA: 0.01,
  topicA: 0.01,
  masteryThreshold: 0.01,
  reviewDays: 1,
  simpleWeight: 0.05,
};
// Keep step="any" for exact presets/manual values; use the same bounded step
// for keyboard arrows and visible controls, without the browser's unit jumps.
export function adjustSetting(input, direction) {
  const key = input.name;
  if (!Object.hasOwn(steps, key) || ![1, -1].includes(direction)) return;
  const current = Number.isFinite(input.valueAsNumber)
    ? input.valueAsNumber
    : defaults[key];
  const [min, max] = limits[key];
  const next = Math.min(max, Math.max(min, current + direction * steps[key]));
  input.value = String(Number(next.toFixed(12)));
  input.dispatchEvent(new Event("input", { bubbles: true }));
}
export function validateSettings(value) {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).length !== Object.keys(defaults).length ||
    Object.keys(value).some((key) => !Object.hasOwn(defaults, key))
  )
    throw new Error("Некорректные настройки обучения.");
  for (const [key, [min, max]] of Object.entries(limits))
    if (!Number.isFinite(value[key]) || value[key] < min || value[key] > max)
      throw new Error("Проверьте диапазоны настроек обучения.");
  return { ...value };
}
export function loadSettings() {
  try {
    return validateSettings(JSON.parse(localStorage.getItem(KEY)));
  } catch {
    return { ...defaults };
  }
}
export function saveSettings(value) {
  const settings = validateSettings(value);
  localStorage.setItem(KEY, JSON.stringify(settings));
  return settings;
}
export function renderSettings(settings) {
  const input = (key, label, help) =>
    `<div class="settings-field"><label for="setting-${key}">${label}</label><div class="settings-number"><input id="setting-${key}" name="${key}" type="number" min="${limits[key][0]}" max="${limits[key][1]}" step="any" value="${settings[key]}" aria-describedby="help-${key}" required><div class="settings-stepper"><button type="button" data-action="adjust-setting" data-target="${key}" data-direction="1" aria-label="Увеличить: ${label}">↑</button><button type="button" data-action="adjust-setting" data-target="${key}" data-direction="-1" aria-label="Уменьшить: ${label}">↓</button></div></div><small id="help-${key}">${help}</small></div>`;
  return `<div class="page-heading"><div><span class="eyebrow">В СВОЁМ ТЕМПЕ</span><h1>Настройки обучения</h1><p>Настройки действуют в этом браузере. После сохранения оценки пересчитываются по истории решений.</p></div><a class="text-link" href="#progress">Мой прогресс →</a></div>
  <form id="learning-settings" class="panel settings-form">
  ${input("masteryThreshold", "Порог «Получается»", "Оценка должна быть строго выше порога. Диапазон: от 0 до 1.")}
  ${input("reviewDays", "Повторение через, дней", "Срок после последнего результата, сохранившего оценку выше порога.")}
  ${input("simpleWeight", "Вес упражнений на правило для оценки темы", "0 — не влияют на тему; 0,5 — меньший вес; 1 — такой же вес, как у ЕГЭ. Оценка самой карточки не уменьшается.")}
  <details><summary>Как быстро меняется оценка</summary><p>Новое значение = (старое + a × результат) / (1 + a). Чем больше a, тем сильнее влияние нового решения. Первое решение задаёт оценку карточки напрямую; оценка темы начинается с нуля.</p>
  ${input("cardA", "Коэффициент a для карточек", "По умолчанию от старого вклада остаётся 0,01% после 10 следующих решений этой карточки.")}
  ${input("topicA", "Коэффициент a для тем", "Для заданий ЕГЭ. При меньшем весе простых упражнений тема меняется медленнее.")}
  <div class="progress-actions">${["cardA", "topicA"].map((key) => `<p>${key === "cardA" ? "Для карточки" : "Для темы"}: ${[0.01, 0.001, 0.0001].map((r) => `<button class="button quiet" type="button" data-action="retention" data-target="${key}" data-retention="${r}">${r * 100}% после 10 решений</button>`).join("")}</p>`).join("")}</div></details>
  <p>Верно с первой попытки — 1; с n-й попытки — 1/n; с подсказкой или просмотром ответа — 0. Чтение правила не снижает результат. Незавершённое решение не меняет оценку.</p>
  <div class="progress-actions"><button class="button primary" type="submit">Сохранить настройки</button><button class="button secondary" type="button" data-action="reset-settings">По умолчанию</button></div><p id="settings-feedback" role="status"></p></form>`;
}
