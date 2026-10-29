import { esc } from "./ui.js";
import {
  loadParonymIndex,
  paronymListSourceUrl,
  loadDictionaryArticle,
} from "./data.js";

export async function paronymListPage({ heading, backLink, cardId }) {
  const index = await loadParonymIndex();
  return (
    heading(
      "ПАРОНИМЫ",
      "Алфавитный список паронимов",
      `${index.groups.length} пар и групп из всех ${index.cardCount} упражнений. По алфавиту, без повторов.`,
    ) +
    backLink +
    `<p><a class="text-link" href="#knowledge?list=paronyms&view=theory${cardId ? `&card=${esc(cardId)}` : ""}">Как различать паронимы</a></p><section class="panel"><p>Включены пары и группы для выделенных слов из всех вариантов и для ответов. Слова приведены к начальной форме.</p><ol class="paronym-list">${index.groups.map((group) => `<li data-paronym-group="${esc(group.id)}">${group.words.map(esc).join(" — ")}</li>`).join("")}</ol></section>
    <p><a class="text-link" href="${esc(paronymListSourceUrl)}" target="_blank" rel="noopener">Состав групп: список ФИПИ · ${index.source.listYear}, с. 2–5</a></p>${backLink}`
  );
}

export function paronymTheoryPage({ heading, backLink, cardId }) {
  return (
    heading(
      "ЛЕКСИКА",
      "Как различать паронимы",
      "Смысл слова проверяем в конкретном предложении.",
    ) +
    backLink +
    `<article class="panel knowledge-rule"><h2>Похожее звучание — разные значения</h2><p>Паронимы — близкие по звучанию слова с различающимися значениями: например, «костный» относится к кости и костной ткани, а «костяной» — к материалу изделия.</p><h2>Смотрите на словосочетание целиком</h2><ol><li>Определите, что названо: человек, материал, действие, свойство или результат.</li><li>Объясните смысл выделенного слова простыми словами и подставьте объяснение в предложение.</li><li>Сопоставьте значения паронимов. Проверьте, с какими словами они сочетаются и какую стилистическую помету даёт словарь.</li><li>Запишите замену в нужной грамматической форме: сохраните падеж, число, род, время и согласование.</li></ol><h2>Одного значения бывает недостаточно</h2><p>У слова может быть несколько значений. Некоторые паронимы в отдельных сочетаниях сближаются: например, «дипломатический» может описывать не только отношения государств, но и осторожный подход. Поэтому правило «одно слово можно употреблять только так» часто слишком узко.</p><h2>Проверка в задании</h2><p>В задании №5 найдите одно неверно употреблённое слово и замените его паронимом. Автоматическая проверка принимает ответ по ключу ФИПИ. Если словарь допускает другое прочтение, оно поясняется в разборе отдельно.</p><nav class="rule-links"><a class="text-link" href="#knowledge?list=paronyms${cardId ? `&card=${esc(cardId)}` : ""}">Все пары и группы из упражнений</a><a class="text-link" href="${esc(paronymListSourceUrl)}#page=5" target="_blank" rel="noopener">ФИПИ · значения и сближение паронимов, с. 5</a><a class="text-link" href="#bank?task=5&status=verified">Задания на паронимы</a></nav></article>` +
    backLink
  );
}

export async function dictionaryArticlePage({
  params,
  heading,
  backLink,
  task,
}) {
  const article = await loadDictionaryArticle(
    params.get("dictionary"),
    params.get("entry"),
  );
  if (!article)
    return (
      heading(
        "СЛОВАРЬ",
        "Статья не найдена",
        "Выберите ссылку на словарь в разборе задания.",
      ) + backLink
    );
  const textGuide = {
    1: ["connections", "Средства связи в тексте"],
    2: ["meanings", "Значение слова в контексте"],
    3: ["style", "Как анализировать текст"],
  }[task];
  const relatedUrl = textGuide
    ? `#knowledge?list=${textGuide[0]}&card=${esc(params.get("card"))}`
    : task === 7
      ? `#knowledge?list=word-forms&card=${esc(params.get("card"))}`
      : task === 6
        ? `#knowledge?list=lexical&card=${esc(params.get("card"))}`
        : task === 5
          ? "#knowledge?list=paronyms"
          : "#knowledge";
  const relatedLabel = textGuide
    ? textGuide[1]
    : task === 7
      ? "Формы слов"
      : task === 6
        ? "Лексические нормы"
        : task === 5
          ? "Алфавитный список паронимов"
          : "Справочник";
  return (
    heading("СЛОВАРЬ", esc(article.headword), esc(article.title)) +
    backLink +
    `<article class="panel knowledge-rule source-paragraph" data-dictionary-entry="${esc(article.id)}">${article.text
      .split("\n")
      .map((line) => `<p>${esc(line)}</p>`)
      .join(
        "",
      )}</article><p><a class="text-link" href="${relatedUrl}">${relatedLabel}</a></p>` +
    backLink
  );
}

function referenceLink(ref, cardId) {
  if (ref.entryId) {
    return `<a class="text-link" href="#knowledge?dictionary=${esc(ref.dictionaryId)}&entry=${esc(ref.entryId)}${cardId ? `&card=${esc(cardId)}` : ""}">${esc(ref.label || "Словарь")}: «${esc(ref.headword)}»</a>`;
  }
  const url = new URL(
    `../assets/data/dictionaries/${ref.dictionaryId}.pdf`,
    import.meta.url,
  );
  url.hash = `page=${ref.pdfPage}`;
  return `<a class="text-link" href="${esc(url.href)}" target="_blank" rel="noopener" title="${esc(ref.label || "Словарь паронимов русского языка")}">${esc(ref.label || "Словарь")}: «${esc(ref.headword)}» · PDF, с. ${ref.pdfPage}</a>`;
}

export function renderDictionaryReferences(refs = [], cardId) {
  const unique = [
    ...new Map(
      refs.map((ref) => [
        `${ref.dictionaryId}:${ref.entryId || ref.pdfPage}:${ref.headword}`,
        ref,
      ]),
    ).values(),
  ];
  return unique.length
    ? `<nav class="rule-links dictionary-sources" aria-label="Источники">${unique.map((ref) => referenceLink(ref, cardId)).join("")}</nav>`
    : "";
}

export function renderParonymComparisons(pairs = [], cardId) {
  return pairs
    .map(
      (pair) =>
        `<section class="paronym-comparison" aria-label="Сравнение паронимов"><h3>Сравним слова</h3><div class="paronym-words">${pair.words.map((word) => `<section class="paronym-word"><h4>${esc(word.word)}</h4><p>${esc(word.meaning)}</p><ul>${word.examples.map((example) => `<li>${esc(example)}</li>`).join("")}</ul>${renderDictionaryReferences(word.dictionaryRefs, cardId)}</section>`).join("")}</div><p class="paronym-difference"><b>Как различить:</b> ${esc(pair.distinction)}</p></section>`,
    )
    .join("");
}
