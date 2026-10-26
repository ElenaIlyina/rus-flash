/** UI ordering, deliberately separate from the learning-state reducer. */
function rank(id, seed) {
  let value = seed >>> 0;
  for (const ch of id)
    value = Math.imul(value ^ ch.charCodeAt(0), 16777619) >>> 0;
  return value;
}
export function orderCards(cards, mode, progress, history, tags, seed) {
  const last = new Map();
  for (const e of history) {
    if (
      !last.has(e.cardId) ||
      Date.parse(e.time) > Date.parse(last.get(e.cardId).time)
    )
      last.set(e.cardId, e);
  }
  const priority = (c) => {
    if (!c.eligibleForProgress)
      return c.hasVerifiedAnswer && !c.reviewNote ? 6 : 7;
    if (progress.cardStates.get(c.id) === "due") return 0;
    if (tags(c.id).hard) return 1;
    if (last.get(c.id)?.correct === false) return 2;
    if (!last.has(c.id)) return 3;
    if (progress.cardStates.get(c.id) === "practicing") return 4;
    return 5;
  };
  return cards.slice().sort((a, b) => {
    if (mode === "shuffle")
      return rank(a.id, seed) - rank(b.id, seed) || a.id.localeCompare(b.id);
    if (mode === "exam")
      return (
        (a.task ?? 99) - (b.task ?? 99) ||
        priority(a) - priority(b) ||
        rank(a.id, seed) - rank(b.id, seed)
      );
    return (
      priority(a) - priority(b) ||
      (Date.parse(last.get(a.id)?.time || "") || 0) -
        (Date.parse(last.get(b.id)?.time || "") || 0) ||
      (a.task ?? 99) - (b.task ?? 99) ||
      rank(a.id, seed) - rank(b.id, seed)
    );
  });
}
