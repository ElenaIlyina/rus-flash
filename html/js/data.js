import { plain } from "./ui.js";

const URL_ROOT = new URL("../assets/data/", import.meta.url);
export async function loadCatalog() {
  const response = await fetch(new URL("catalog.json", URL_ROOT));
  if (!response.ok)
    throw new Error(
      "Не удалось загрузить каталог. Выполните python3 scripts/build_app_data.py и запустите HTTP-сервер.",
    );
  return response.json();
}
export async function loadCard(id) {
  if (!/^[0-9A-F]{6}$/.test(id))
    throw new Error("Некорректный номер карточки.");
  const response = await fetch(new URL(`cards/${id}.json`, URL_ROOT));
  if (!response.ok)
    throw new Error(
      "Карточка недоступна. Проверьте подключение или пересоберите данные.",
    );
  return adaptCard(await response.json());
}
function responseType(raw, question, options) {
  if (raw.sentence_numbers?.length) return "sentence_numbers";
  if (raw.answer_type === "position_set") return "position_set";
  // An ordered matching task may also say «запишите цифры».
  if ((raw.errors?.length && raw.sentences?.length) ||
      /^\s*установите\s+соответствие(?:\s|[.:])/iu.test(question)) {
    return "matching";
  }
  if (options.length && (raw.answer_type === "bitmask" ||
      /(?:укажите|запишите)\s+(?:все\s+)?(?:варианты|номера)|словарной статьи/i.test(question))) {
    return "multiple_choice";
  }
  return /(?:укажите|запишите)[^.!?]*цифр/i.test(question) ? "position_set" : "short_text";
}

function rhetoricColumns(question) {
  const headings = "\n<b><u>ПРЕДЛОЖЕНИЯ</u></b>\n<b><u>ИЗОБРАЗИТЕЛЬНО-ВЫРАЗИТЕЛЬНЫЕ СРЕДСТВА ЯЗЫКА</u></b>\n";
  const [intro, table] = question.split(headings);
  if (!table) return null;
  const footer = table.lastIndexOf("\nЗапишите в таблицу");
  if (footer < 0) return null;
  const cells = table.slice(0, footer).split(/(?:^|\n)([АБВГД1-9])\)[ \t]*\n/u);
  const labels = cells.filter((_, index) => index % 2 === 1).join("");
  const values = cells.filter((_, index) => index > 0 && index % 2 === 0).map(value => value.trim());
  if (labels !== "АБВГД123456789" || cells[0].trim() || values.some(value => !value)) return null;
  return {
    instruction: intro.trim() + "\n" + table.slice(footer).trim(),
    sentences: values.slice(0, 5),
    terms: values.slice(5).map(value => value.replace(/\s+/gu, " ")),
  };
}

function rhetoricTermList(question) {
  const heading = /(?:^|\s)(?:<b><u>)?Список терминов:(?:<\/u><\/b>)?(?=\s)/iu.exec(question);
  if (!heading) return null;
  const list = question.slice(heading.index + heading[0].length);
  const cells = list.split(/(?:^|\s)(?:<b>)?([1-9])\)(?:<\/b>)?(?=\s)/u);
  const labels = cells.filter((_, index) => index % 2 === 1).join("");
  const terms = cells.filter((_, index) => index > 0 && index % 2 === 0).map(value => value.trim());
  if (labels !== "123456789" || cells[0].trim() || terms.some(term => !term)) return null;
  return { instruction: question.slice(0, heading.index).trim(), terms };
}

function punctuationExamples(question) {
  const match = /^([\s\S]*?одним\s+и\s+тем\s+же\s+правилом\s+пунктуации\.\s+Запишите\s+номера\s+этих\s+предложений\.)\s*(\(1\)[\s\S]*)$/iu.exec(question);
  if (!match) return null;
  const cells = match[2].split(/(?:^|\s+)\((\d+)\)/u).slice(1);
  const numbers = cells.filter((_, index) => index % 2 === 0);
  const options = cells.filter((_, index) => index % 2 === 1).map(text => text.trim());
  if (options.length < 2 || options.some((text, index) => !text || Number(numbers[index]) !== index + 1)) return null;
  return { instruction: match[1], options };
}

export function adaptCard(raw) {
  let options = raw.variants || [];
  if (options.length === 1 && /^\s*\d\)/.test(options[0])) {
    options = options[0]
      .split(/(?=\d\))/)
      .map((s) => s.replace(/^\s*\d\)\s*/, "").trim())
      .filter(Boolean);
  } else {
    options = options.map((s) => String(s).replace(/^\s*\d\)\s*/, ""));
  }
  const rhetoric = raw.text ? rhetoricTermList(raw.question) : rhetoricColumns(raw.question);
  const examples = !raw.text && !options.length ? punctuationExamples(raw.question) : null;
  let instruction = rhetoric?.instruction || examples?.instruction || raw.question;
  if (rhetoric && !rhetoric.sentences) {
    // FIPI puts this direction in the header outside the review and term list.
    instruction = "<b>Установите соответствие и впишите ответ.</b><br>" +
      "Запишите четыре цифры в порядке А, Б, В, Г.\n\n" + instruction;
  }
  const questionText = plain(raw.question);
  if (
    raw.errors?.length &&
    raw.sentences?.length &&
    instruction.includes("ГРАММАТИЧЕСКИЕ ОШИБКИ")
  ) {
    instruction = instruction
      .slice(0, instruction.indexOf("ГРАММАТИЧЕСКИЕ ОШИБКИ"))
      .trim();
  }
  return {
    id: raw.number,
    instruction,
    passage: raw.text || "",
    passageNote: raw.passage_note,
    questionNote: raw.question_note,
    options: examples?.options || options,
    errors: raw.errors || [],
    sentences: raw.sentences || [],
    rhetoric,
    responseType: responseType(raw, questionText, options),
    sentenceNumbers: raw.sentence_numbers || [],
    answer: (raw.answer || "").trim(),
    acceptedAnswers: Array.isArray(raw.accepted_answers) ? raw.accepted_answers : [(raw.answer || "").trim()],
    explanation: raw.explanation || "",
    contentIssue: typeof raw.content_issue === "string" ? raw.content_issue.trim() : "",
    ruleIds: raw.rule_ids || [],
  };
}

// Readers share in-flight requests. A failed request can be retried.
const referenceFiles = new Map();

function loadReference(file, message) {
  if (!referenceFiles.has(file)) {
    const request = fetch(new URL(file, URL_ROOT))
      .then((response) => {
        if (!response.ok) throw new Error(message);
        return response.json();
      })
      .catch((error) => {
        referenceFiles.delete(file);
        throw error;
      });
    referenceFiles.set(file, request);
  }
  return referenceFiles.get(file);
}

export const loadParonymIndex = () =>
  loadReference("paronym-index.json", "Список паронимов недоступен.");
export const paronymListSourceUrl = new URL("paronym-index-source.pdf", URL_ROOT).href;

export async function loadDictionaryArticle(dictionaryId, entryId) {
  if (!/^[a-z0-9-]+$/.test(dictionaryId || "")) return null;
  const dictionary = await loadReference(
    `dictionaries/${dictionaryId}.json`, "Словарная статья недоступна.",
  );
  const article = dictionary.entries.find((entry) => entry.id === entryId);
  return article ? { ...article, title: dictionary.title } : null;
}

export const loadStressList = () =>
  loadReference("stress-list.json", "Список ударений недоступен.");
export const stressSourceUrl = new URL("stress-list-source.pdf", URL_ROOT).href;

export const loadHandbook = () =>
  loadReference("handbook.json", "Справочник недоступен. Пересоберите данные сайта.");
export const loadHandbookSources = () =>
  loadReference("handbook-sources.json", "Оглавление источников недоступно. Пересоберите данные сайта.");

export async function loadSourceParagraph(id) {
  if (!/^lopatin-2007-(orthography|punctuation)-[1-9][0-9]{0,2}$/.test(id))
    return null;
  const response = await fetch(
    new URL(`handbook-sources/${id}.json`, URL_ROOT),
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Параграф источника недоступен.");
  return response.json();
}

export const loadStressGlossary = () =>
  loadReference("stress-glossary.json", "Словарик ударений недоступен.");

export const stressGlossaryTextUrl = new URL("stress-glossary.txt", URL_ROOT).href;
