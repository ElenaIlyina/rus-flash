import { esc } from "./ui.js";

export function renderParonymComparisons(pairs = []) {
  return pairs
    .map(
      (pair) =>
        `<section class="paronym-comparison" aria-label="Сравнение паронимов"><h3>Сравним слова</h3><div class="paronym-words">${pair.words.map((word) => `<section class="paronym-word"><h4>${esc(word.word)}</h4><p>${esc(word.meaning)}</p><ul>${word.examples.map((example) => `<li>${esc(example)}</li>`).join("")}</ul></section>`).join("")}</div><p class="paronym-difference"><b>Как различить:</b> ${esc(pair.distinction)}</p></section>`,
    )
    .join("");
}
