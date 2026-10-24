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
  attempt(id, correct, revealed) {
    const event = {
      id: crypto.randomUUID(),
      cardId: id,
      time: new Date().toISOString(),
      correct,
      assisted: revealed,
      materialVersion: 1,
    };
    state.events.push(event);
    save();
    return event;
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
