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
                raw.question,
              ) ||
              /словарной статьи/i.test(raw.question))
          ? "multiple_choice"
          : /(?:укажите|запишите)[^.!?]*цифр/i.test(raw.question)
            ? "position_set"
            : "short_text",
    answer: (raw.answer || "").trim(),
    explanation: raw.explanation || "",
    // Imported legacy values have not acquired editorial verification.
    reviewStatus: "unverified",
    ruleIds: raw.rule_ids || [],
  };
}

let handbookPromise;
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
