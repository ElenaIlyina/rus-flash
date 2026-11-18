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
  let instruction = raw.question;
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
    options,
    errors: raw.errors || [],
    sentences: raw.sentences || [],
    responseType: responseType(raw, questionText, options),
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
