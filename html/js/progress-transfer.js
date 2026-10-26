/** Portable progress format v1. Never imports computed/demo mastery values. */
const cardId = (value) =>
  typeof value === "string" && /^[0-9A-F]{6}$/.test(value);
const object = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const fields = (value, allowed) =>
  Object.keys(value).every((key) => allowed.includes(key));
const fail = () => {
  throw new Error(
    "Некорректная структура файла прогресса. Выберите JSON, скачанный из приложения.",
  );
};
export function parseProgress(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(
      "Не удалось прочитать JSON. Файл повреждён или имеет другой формат.",
    );
  }
  if (!object(data) || data.schemaVersion !== 1)
    throw new Error(
      "Версия файла не поддерживается. Нужен экспорт прогресса версии 1.",
    );
  if (
    !fields(data, [
      "schemaVersion",
      "exportedAt",
      "events",
      "lastCard",
      "tags",
    ]) ||
    !Array.isArray(data.events) ||
    data.events.length > 50000 ||
    !object(data.tags) ||
    Object.keys(data.tags).length > 10000 ||
    !(data.lastCard === null || cardId(data.lastCard)) ||
    typeof data.exportedAt !== "string" ||
    !Number.isFinite(Date.parse(data.exportedAt))
  )
    fail();
  const ids = new Set();
  for (const event of data.events) {
    if (
      !object(event) ||
      !fields(event, [
        "id",
        "cardId",
        "time",
        "correct",
        "assisted",
        "materialVersion",
      ]) ||
      typeof event.id !== "string" ||
      !event.id.length ||
      event.id.length > 128 ||
      ids.has(event.id) ||
      !cardId(event.cardId) ||
      typeof event.time !== "string" ||
      !Number.isFinite(Date.parse(event.time)) ||
      typeof event.correct !== "boolean" ||
      typeof event.assisted !== "boolean" ||
      !Number.isInteger(event.materialVersion) ||
      event.materialVersion < 1
    )
      fail();
    ids.add(event.id);
  }
  for (const [id, tags] of Object.entries(data.tags)) {
    if (
      !cardId(id) ||
      !object(tags) ||
      !fields(tags, ["fav", "hard", "studied", "solved"]) ||
      !Object.values(tags).every((value) => typeof value === "boolean")
    )
      fail();
  }
  return data;
}
export function mergeProgress(current, incoming) {
  const events = new Map(current.events.map((event) => [event.id, event]));
  let added = 0,
    duplicates = 0,
    conflicts = 0,
    marksAdded = 0;
  for (const event of incoming.events) {
    if (events.has(event.id)) {
      const local = events.get(event.id);
      if (
        ["cardId", "time", "correct", "assisted", "materialVersion"].some(
          (key) => local[key] !== event[key],
        )
      )
        conflicts++;
      else duplicates++;
    } else {
      events.set(event.id, event);
      added++;
    }
  }
  const tags = Object.fromEntries(
    Object.entries(current.tags).map(([id, value]) => [id, { ...value }]),
  );
  for (const [id, value] of Object.entries(incoming.tags)) {
    tags[id] = { ...(tags[id] || {}) };
    for (const [key, selected] of Object.entries(value)) {
      if (selected && !tags[id][key]) marksAdded++;
      tags[id][key] = Boolean(tags[id][key] || selected);
    }
  }
  return {
    events: [...events.values()].sort(
      (a, b) =>
        Date.parse(a.time) - Date.parse(b.time) || a.id.localeCompare(b.id),
    ),
    lastCard: current.lastCard || incoming.lastCard,
    tags,
    summary: { added, duplicates, conflicts, marksAdded },
  };
}
