import {
  loadHandbook,
  loadHandbookSources,
  loadSourceParagraph,
} from "./data.js";
import { esc, rich } from "./ui.js";
const partName = (part) =>
  part === "orthography" ? "Орфография" : "Пунктуация";
const context = (meta) => (meta ? `&card=${meta.id}` : "");
function back(meta) {
  return meta
    ? `<p><a class="text-link" href="#card/${meta.id}">Вернуться к карточке ${meta.id}</a></p>`
    : "";
}
export async function knowledgePage({ params, catalog, heading, empty }) {
  const safeHeading = (kicker, title, subtitle) =>
    heading(kicker, esc(title), esc(subtitle));
  const meta = catalog.cards.find((c) => c.id === params.get("card"));
  const ruleId = params.get("rule"),
    sourceId = params.get("source"),
    editionId = params.get("edition");
  if (sourceId) {
    const paragraph = await loadSourceParagraph(sourceId);
    if (!paragraph)
      return empty(
        "knowledge",
        "Параграф источника не найден",
        "Проверьте ссылку или откройте оглавление.",
        '<a class="text-link" href="#knowledge">Справочник</a>',
      );
    return (
      safeHeading(
        "ПЕРВОИСТОЧНИК",
        `${partName(paragraph.part)} · §${paragraph.number}`,
        `${paragraph.edition.title} / под ред. ${paragraph.edition.editor}. ${paragraph.edition.publisher}, ${paragraph.edition.year}. ISBN ${paragraph.edition.isbn}`,
      ) +
      back(meta) +
      `<nav class="rule-links"><a class="text-link" href="#knowledge?edition=${paragraph.editionId}${context(meta)}">Оглавление книги</a>${ruleId ? `<a class="text-link" href="#knowledge?rule=${esc(ruleId)}${context(meta)}">Вернуться к нашему объяснению</a>` : '<a class="text-link" href="#knowledge">Короткие правила</a>'}</nav>
      ${paragraph.editorialNotes?.length ? `<aside class="source-warning"><div><strong>Опечатки в источнике</strong>${paragraph.editorialNotes.map((note) => `<p>${esc(note.original)}${note.replacement ? " → " + esc(note.replacement) : " — опечатка в примере"}</p>`).join("")}</div></aside>` : ""}<article class="panel knowledge-rule source-paragraph" data-source-id="${esc(paragraph.id)}"><div class="explanation-text">${rich(paragraph.body, { markdown: false })}</div>${paragraph.notes.length ? `<details class="source-notes"><summary>Примечания к этому параграфу</summary>${paragraph.notes.map((note) => `<p>${rich(note.body, { markdown: false })}</p>`).join("")}</details>` : ""}</article>`
    );
  }
  const sources = await loadHandbookSources();
  if (editionId) {
    const edition = sources.editions.find((e) => e.id === editionId);
    if (!edition)
      return empty(
        "knowledge",
        "Издание не найдено",
        "Выберите источник из справочника.",
        '<a class="text-link" href="#knowledge">Справочник</a>',
      );
    return (
      safeHeading(
        "ОГЛАВЛЕНИЕ ИСТОЧНИКА",
        `Академический справочник · ${edition.year}`,
        `${edition.publisher}. Под ред. ${edition.editor}. ISBN ${edition.isbn}`,
      ) +
      back(meta) +
      '<p><a class="text-link" href="#knowledge">К коротким правилам</a></p>' +
      ["orthography", "punctuation"]
        .map(
          (part) =>
            `<details class="panel source-index"><summary>${partName(part)} — ${edition.paragraphs.filter((p) => p.part === part).length} параграфов</summary><div class="source-index-links">${edition.paragraphs
              .filter((p) => p.part === part)
              .map(
                (p) =>
                  `<a class="text-link" href="#knowledge?source=${p.id}${context(meta)}">${esc(p.heading)}</a>`,
              )
              .join("")}</div></details>`,
        )
        .join("")
    );
  }
  const book = await loadHandbook();
  const selected = book.paragraphs.find((rule) => rule.id === ruleId);
  const related = params.get("card")
    ? meta
      ? book.paragraphs.filter(
          (rule) =>
            (meta.ruleIds || []).includes(rule.id) ||
            rule.tasks.includes(meta.task),
        )
      : []
    : book.paragraphs;
  const rules = ruleId ? (selected ? [selected] : []) : related;
  return (
    safeHeading(
      "ПОНЯТЬ, ЧТОБЫ ПРИМЕНИТЬ",
      "Справочник правил",
      "Короткие объяснения и точные ссылки на разделы исходной книги.",
    ) +
    back(meta) +
    (ruleId
      ? '<p><a class="text-link" href="#knowledge">Все параграфы →</a></p>'
      : "") +
    (rules.length
      ? `<nav class="rule-links" aria-label="Параграфы справочника">${rules.map((rule) => `<a class="text-link" href="#knowledge?rule=${esc(rule.id)}${context(meta)}">§${rule.number}. ${esc(rule.title)}</a>`).join("")}</nav>${rules.map((rule) => `<article class="panel knowledge-rule" id="rule-${esc(rule.id)}"><span class="eyebrow">НАШЕ ПОЯСНЕНИЕ §${rule.number}</span><h2>${esc(rule.title)}</h2><div class="explanation-text">${rich(rule.body)}</div><h3>Параграфы источника</h3><nav class="rule-links">${(rule.sourceRefs || []).map((ref) => `<a class="text-link" href="#knowledge?source=${esc(ref.sourceId)}&rule=${esc(rule.id)}${context(meta)}">${partName(ref.part)}, §${ref.paragraph} · Эксмо, 2007</a>`).join("")}</nav><a class="text-link" href="#bank?task=${rule.tasks[0]}&status=verified">Практика по теме →</a></article>`).join("")}`
      : empty(
          "knowledge",
          ruleId ? "Параграф не найден" : "Связанные правила ещё готовятся",
          "Выберите правило в справочнике.",
          '<a class="text-link" href="#knowledge">Открыть справочник</a>',
        )) +
    `<section class="panel method-panel"><h2>Библиотека источников</h2>${sources.editions.map((e) => `<p><a class="text-link" href="#knowledge?edition=${e.id}${context(meta)}">${esc(e.title)} · ${esc(e.publisher)}, ${esc(e.year)}</a></p>`).join("")}</section>`
  );
}
