import { mergeProgress } from "./progress-transfer.js";
const KEY = "rusflash_learning_v1";
let available = true;
let state = { events: [], lastCard: null };
try {
  const saved = JSON.parse(localStorage.getItem(KEY) || "null");
  if (saved && Array.isArray(saved.events)) state = saved;
} catch {
  available = false;
}
const tags = new Map();
const assignments = new Map();
try {
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (/^task_tags_[0-9A-F]{6}$/i.test(key)) {
      try {
        const value = JSON.parse(localStorage.getItem(key));
        if (value && typeof value === "object")
          tags.set(key.slice(10).toUpperCase(), value);
      } catch {
        /* isolate a malformed legacy entry */
      }
    }
  }
} catch {
  available = false;
}
// randomUUID requires a secure context; getRandomValues also works over HTTP.
function eventId() {
  if (typeof globalThis.crypto.randomUUID === "function")
    return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4),
    hex.slice(4, 6),
    hex.slice(6, 8),
    hex.slice(8, 10),
    hex.slice(10),
  ]
    .map((part) => part.join(""))
    .join("-");
}
function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    available = false;
  }
}
export const store = {
  get available() {
    return available;
  },
  get history() {
    return state.events;
  },
  get lastCard() {
    return state.lastCard;
  },
  tags(id) {
    return tags.get(id) || {};
  },
  toggle(id, tag) {
    if (!["fav", "hard", "studied"].includes(tag)) return;
    const value = { ...this.tags(id), [tag]: !this.tags(id)[tag] };
    tags.set(id, value);
    try {
      localStorage.setItem("task_tags_" + id, JSON.stringify(value));
    } catch {
      available = false;
    }
    return value[tag];
  },
  remember(id) {
    state.lastCard = id;
    save();
  },
  assignment(id, fresh = false) {
    if (!fresh && assignments.has(id)) return assignments.get(id);
    const key = "slovo_assignment_" + id;
    let value = {
      id: eventId(),
      assisted: false,
      submitted: false,
      attemptNumber: 0,
      completed: false,
    };
    try {
      const saved = fresh
        ? null
        : JSON.parse(localStorage.getItem(key) || "null");
      if (
        saved &&
        typeof saved.assisted === "boolean" &&
        typeof saved.submitted === "boolean"
      )
        value = {
          ...value,
          ...saved,
          id: typeof saved.id === "string" ? saved.id : value.id,
          attemptNumber: Number.isInteger(saved.attemptNumber)
            ? saved.attemptNumber
            : saved.submitted
              ? 1
              : 0,
          completed: saved.completed === true,
        };
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      available = false;
    }
    assignments.set(id, value);
    return value;
  },
  markAssignment(id, field) {
    const value = this.assignment(id);
    value[field] = true;
    try {
      localStorage.setItem("slovo_assignment_" + id, JSON.stringify(value));
    } catch {
      available = false;
    }
    return value;
  },
  attempt(id, correct, revealed, materialVersion = 1) {
    const assignment = this.assignment(id);
    if (assignment.completed) return null;
    assignment.attemptNumber++;
    assignment.submitted = true;
    assignment.assisted = assignment.assisted || revealed;
    assignment.completed = correct;
    const event = {
      id: eventId(),
      scoringVersion: 1,
      assignmentId: assignment.id,
      attemptNumber: assignment.attemptNumber,
      completed: correct,
      cardId: id,
      time: new Date().toISOString(),
      correct,
      assisted: assignment.assisted,
      materialVersion,
    };
    try {
      localStorage.setItem(
        "slovo_assignment_" + id,
        JSON.stringify(assignment),
      );
    } catch {
      available = false;
    }
    state.events.push(event);
    save();
    return event;
  },
  importData(incoming) {
    const merged = mergeProgress(
      { ...state, tags: Object.fromEntries(tags) },
      incoming,
    );
    const nextState = { events: merged.events, lastCard: merged.lastCard };
    const writes = [
      [KEY, JSON.stringify(nextState)],
      ...Object.entries(merged.tags).map(([id, value]) => [
        "task_tags_" + id,
        JSON.stringify(value),
      ]),
    ];
    const before = new Map(
      writes.map(([key]) => [key, localStorage.getItem(key)]),
    );
    try {
      for (const [key, value] of writes) localStorage.setItem(key, value);
    } catch {
      // Restore old values and remove only keys newly created by this import.
      try {
        for (const [key, value] of before)
          if (value === null) localStorage.removeItem(key);
        for (const [key, value] of before)
          if (value !== null) localStorage.setItem(key, value);
      } catch {
        throw new Error(
          "Не удалось завершить восстановление хранилища. Сохраните резервную копию и не закрывайте вкладку.",
        );
      }
      throw new Error(
        "Не удалось сохранить файл: хранилище недоступно или переполнено. Импорт отменён.",
      );
    }
    state = nextState;
    tags.clear();
    for (const [id, value] of Object.entries(merged.tags)) tags.set(id, value);
    available = true;
    return merged.summary;
  },
  exportData() {
    return JSON.stringify(
      {
        schemaVersion: 2,
        exportedAt: new Date().toISOString(),
        ...state,
        tags: Object.fromEntries(tags),
      },
      null,
      2,
    );
  },
};
