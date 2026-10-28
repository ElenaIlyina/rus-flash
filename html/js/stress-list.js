import { loadStressList, stressSourceUrl } from "./data.js";
import { esc } from "./ui.js";

export async function stressListPage({ heading, backLink }) {
  const list = await loadStressList();
  const accented = (value) => esc(value).replace(/[АЕЁИОУЫЭЮЯ]/g, "<b>$&</b>");
  return (
    heading(
      "УДАРЕНИЯ ПО ЧАСТЯМ РЕЧИ",
      esc(list.title),
      `Список ФИПИ · ${list.listYear}. Заглавная гласная обозначает ударение.`,
    ) +
    backLink +
    `<p class="stress-intro">Откройте нужный раздел. Формы слов и грамматические пометы сохранены из списка.</p>
    ${list.groups.map((group) => `<details class="panel source-index stress-group" data-stress-group="${esc(group.id)}"><summary>${esc(group.title)} <span class="muted">· ${group.entries.length}</span></summary><ul class="stress-words">${group.entries.map((entry) => `<li>${accented(entry.text)}${(entry.noteIds || []).map((id) => `<sup title="${esc(list.notes.find((note) => note.id === id)?.text || "")}">${id}</sup>`).join("")}</li>`).join("")}</ul></details>`).join("")}
    <section class="panel method-panel"><h2>Как пользоваться списком</h2>${list.guidance.map((text) => `<p>${esc(text)}</p>`).join("")}<ol class="stress-notes">${list.notes.map((note) => `<li>${esc(note.text)}</li>`).join("")}</ol><details class="source-index"><summary>Слова, исключённые из этой версии списка</summary><p>${list.excludedWords.map(accented).join(", ")}.</p></details><p>Источник: ${esc(list.sourceTitle)}. Орфоэпический список ${list.listYear}, с. 1–6.</p><p><a class="text-link" href="${esc(stressSourceUrl)}" target="_blank" rel="noopener">Открыть исходный PDF</a></p></section>
    ${backLink}<p><a class="text-link" href="#knowledge">К справочнику</a></p>`
  );
}
