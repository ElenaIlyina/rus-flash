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
    responseType:
      raw.errors?.length && raw.sentences?.length
        ? "matching"
        : options.length > 0 &&
            (raw.answer_type === "bitmask" ||
              /(?:укажите|запишите)\s+(?:все\s+)?(?:варианты|номера)/i.test(
                questionText,
              ) ||
              /словарной статьи/i.test(questionText))
          ? "multiple_choice"
          : /(?:укажите|запишите)[^.!?]*цифр/i.test(questionText)
            ? "position_set"
            : "short_text",
    answer: (raw.answer || "").trim(),
    acceptedAnswers: Array.isArray(raw.accepted_answers) ? raw.accepted_answers : [(raw.answer || "").trim()],
    explanation: raw.explanation || "",
    contentIssue: typeof raw.content_issue === "string" ? raw.content_issue.trim() : "",
    ruleIds: raw.rule_ids || [],
  };
}

let handbookPromise;
let paronymIndexPromise;
export function loadParonymIndex() {
  if (!paronymIndexPromise)
    paronymIndexPromise = fetch(new URL("paronym-index.json", URL_ROOT))
      .then((response) => {
        if (!response.ok) throw new Error("Список паронимов недоступен.");
        return response.json();
      })
      .catch((error) => {
        paronymIndexPromise = null;
        throw error;
      });
  return paronymIndexPromise;
}
export const paronymListSourceUrl = new URL(
  "paronym-index-source.pdf",
  URL_ROOT,
).href;

const dictionaryPromises = new Map();
export async function loadDictionaryArticle(dictionaryId, entryId) {
  if (!/^[a-z0-9-]+$/.test(dictionaryId || "")) return null;
  if (!dictionaryPromises.has(dictionaryId)) {
    dictionaryPromises.set(
      dictionaryId,
      fetch(new URL(`dictionaries/${dictionaryId}.json`, URL_ROOT))
        .then((response) => {
          if (!response.ok) throw new Error("Словарная статья недоступна.");
          return response.json();
        })
        .catch((error) => {
          dictionaryPromises.delete(dictionaryId);
          throw error;
        }),
    );
  }
  const dictionary = await dictionaryPromises.get(dictionaryId);
  const article = dictionary.entries.find((entry) => entry.id === entryId);
  return article ? { ...article, title: dictionary.title } : null;
}

let stressListPromise;
export function loadStressList() {
  if (!stressListPromise)
    stressListPromise = fetch(new URL("stress-list.json", URL_ROOT))
      .then((response) => {
        if (!response.ok) throw new Error("Список ударений недоступен.");
        return response.json();
      })
      .catch((error) => {
        stressListPromise = null;
        throw error;
      });
  return stressListPromise;
}
export const stressSourceUrl = new URL("stress-list-source.pdf", URL_ROOT).href;

export function loadHandbook() {
  if (!handbookPromise)
    handbookPromise = fetch(new URL("handbook.json", URL_ROOT))
      .then((response) => {
        if (!response.ok)
          throw new Error("Справочник недоступен. Пересоберите данные сайта.");
        return response.json();
      })
      .catch((error) => {
        handbookPromise = null;
        throw error;
      });
  return handbookPromise;
}

let sourceIndexPromise;
export function loadHandbookSources() {
  if (!sourceIndexPromise)
    sourceIndexPromise = fetch(new URL("handbook-sources.json", URL_ROOT))
      .then((response) => {
        if (!response.ok)
          throw new Error(
            "Оглавление источников недоступно. Пересоберите данные сайта.",
          );
        return response.json();
      })
      .catch((error) => {
        sourceIndexPromise = null;
        throw error;
      });
  return sourceIndexPromise;
}
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

let stressGlossaryPromise;
export async function loadStressGlossary() {
  if (!stressGlossaryPromise)
    stressGlossaryPromise = fetch(new URL("stress-glossary.json", URL_ROOT))
      .then((response) => {
        if (!response.ok) throw new Error("Словарик ударений недоступен.");
        return response.json();
      })
      .catch((error) => {
        stressGlossaryPromise = null;
        throw error;
      });
  return stressGlossaryPromise;
}

export const stressGlossaryTextUrl = new URL("stress-glossary.txt", URL_ROOT).href;
