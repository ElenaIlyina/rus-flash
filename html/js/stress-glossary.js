import { loadStressGlossary, stressGlossaryTextUrl } from "./data.js";
import { esc } from "./ui.js";

const normalize = (value) =>
  value.toLowerCase().replaceAll("ё", "е").normalize("NFD").replace(/\p{M}/gu, "").trim();
const accented = (value) => esc(value).replace(/[АЕЁИОУЫЭЮЯ]/g, "<b>$&</b>");

export async function stressGlossaryPage({ heading, backLink, cardId }) {
  const data = await loadStressGlossary();
  const words = new Map(data.words.map((word) => [word.id, word]));
  const context = cardId ? `&card=${esc(cardId)}` : "";
  return (
    heading("СРАВНИВАЙ И ЗАПОМИНАЙ", esc(data.title),
      `${data.wordCount} словоформы из всех ${data.cardCount} заданий на ударение.`) +
    backLink +
    `<p class="stress-intro">Ударная гласная — заглавная. Внутри частей речи слова собраны по похожему звучанию, строению и грамматической форме. В одной группе ударение может различаться: сравнивайте каждое слово.</p>
    <div class="stress-glossary"><div class="glossary-search"><label for="stress-word-search">Найти слово или группу</label><input id="stress-word-search" type="search" data-stress-search placeholder="Например, ногт или звон" autocomplete="off"><p class="muted" data-stress-count aria-live="polite">Словоформ: ${data.wordCount}</p></div>
    ${data.parts.map((part, index) => `<details class="panel source-index glossary-part" data-glossary-part="${esc(part.id)}" ${index === 0 ? "open" : ""}><summary>${esc(part.title)}</summary>
      ${part.groups.map((group) => `<section class="stress-comparison" data-stress-comparison="${esc(group.id)}"><h3>${esc(group.title)}</h3>${group.note ? `<p>${esc(group.note)}</p>` : ""}<ul class="stress-chips">${group.wordIds.map((id) => {
        const word = words.get(id);
        return `<li data-stress-word="${esc(id)}" data-search="${esc(normalize(`${word.form} ${part.title} ${group.title} ${word.context || ""}`))}"><span>${accented(word.form)}</span>${word.context ? `<small>${esc(word.context)}</small>` : ""}</li>`;
      }).join("")}</ul></section>`).join("")}</details>`).join("")}
      <p hidden data-stress-empty>Такого слова нет в словарике. Попробуйте часть слова.</p>
    </div><nav class="rule-links"><a class="text-link" href="${esc(stressGlossaryTextUrl)}" download="slovo-stress-glossary.txt">Скачать словарик</a><a class="text-link" href="#knowledge?list=stress${context}">Исходный список ФИПИ по частям речи</a><a class="text-link" href="#bank?task=4">Тренироваться на ударениях</a></nav>${backLink}`
  );
}

export function filterStressGlossary(root, query) {
  const needle = normalize(query);
  const items = [...root.querySelectorAll("[data-stress-word]")];
  for (const item of items) item.hidden = !item.dataset.search.includes(needle);
  for (const group of root.querySelectorAll("[data-stress-comparison]"))
    group.hidden = !group.querySelector("[data-stress-word]:not([hidden])");
  for (const part of root.querySelectorAll("[data-glossary-part]")) {
    part.hidden = !part.querySelector("[data-stress-comparison]:not([hidden])");
    if (needle && !part.hidden) part.open = true;
  }
  const count = items.filter((item) => !item.hidden).length;
  root.querySelector("[data-stress-count]").textContent = needle
    ? `Найдено: ${count} из ${items.length}` : `Словоформ: ${items.length}`;
  root.querySelector("[data-stress-empty]").hidden = count > 0;
}
