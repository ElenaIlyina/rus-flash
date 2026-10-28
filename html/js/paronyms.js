import { esc } from "./ui.js";

function referenceLink(ref) {
  const url = new URL(
    `../assets/data/dictionaries/${ref.dictionaryId}.pdf`,
    import.meta.url,
  );
  url.hash = `page=${ref.pdfPage}`;
  return `<a class="text-link" href="${esc(url.href)}" target="_blank" rel="noopener" title="${esc(ref.label || "Словарь паронимов русского языка")}">${esc(ref.label || "Словарь")}: «${esc(ref.headword)}» · PDF, с. ${ref.pdfPage}</a>`;
}

export function renderDictionaryReferences(refs = []) {
  const unique = [
    ...new Map(
      refs.map((ref) => [
        `${ref.dictionaryId}:${ref.pdfPage}:${ref.headword}`,
        ref,
      ]),
    ).values(),
  ];
  return unique.length
    ? `<nav class="rule-links dictionary-sources" aria-label="Словарные статьи">${unique.map(referenceLink).join("")}</nav>`
    : "";
}

export function renderParonymComparisons(pairs = []) {
  return pairs
    .map(
      (pair) =>
        `<section class="paronym-comparison" aria-label="Сравнение паронимов"><h3>Сравним слова</h3><div class="paronym-words">${pair.words.map((word) => `<section class="paronym-word"><h4>${esc(word.word)}</h4><p>${esc(word.meaning)}</p><ul>${word.examples.map((example) => `<li>${esc(example)}</li>`).join("")}</ul>${renderDictionaryReferences(word.dictionaryRefs)}</section>`).join("")}</div><p class="paronym-difference"><b>Как различить:</b> ${esc(pair.distinction)}</p></section>`,
    )
    .join("");
}
