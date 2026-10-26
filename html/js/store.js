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
    const key = "slovo_assignment_" + id;
    let value = { assisted: false, submitted: false };
    try {
      const saved = fresh
        ? null
        : JSON.parse(localStorage.getItem(key) || "null");
      if (
        saved &&
        typeof saved.assisted === "boolean" &&
        typeof saved.submitted === "boolean"
      )
        value = saved;
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      available = false;
    }
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
    const event = {
      id: crypto.randomUUID(),
      cardId: id,
      time: new Date().toISOString(),
      correct,
      assisted: revealed,
      materialVersion,
    };
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
        schemaVersion: 1,
        exportedAt: new Date().toISOString(),
        ...state,
        tags: Object.fromEntries(tags),
      },
      null,
      2,
    );
  },
};
