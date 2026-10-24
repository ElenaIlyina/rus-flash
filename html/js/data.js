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
  if (
    raw.answer_type === "bitmask" &&
    options.length === 1 &&
    /^\s*\d\)/.test(options[0])
  ) {
    options = options[0]
      .split(/(?=\d\))/)
      .map((s) => s.replace(/^\s*\d\)\s*/, "").trim())
      .filter(Boolean);
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
      raw.answer_type === "bitmask" ? "multiple_choice" : "short_text",
    answer: (raw.answer || "").trim(),
    explanation: raw.explanation || "",
    // Imported legacy values have not acquired editorial verification.
    reviewStatus: "unverified",
    ruleIds: raw.rule_ids || [],
  };
}
