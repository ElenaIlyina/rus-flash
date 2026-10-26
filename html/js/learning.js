/** Experimental, deterministic policy. No model calls and no hidden clock reads. */
export const policy = Object.freeze({
  id: "learning-reference-v0",
  status: "experimental_not_validated",
  distinctCards: 3,
  sessions: 2,
  spanHours: 24,
  reviewHours: 72,
  demotionErrors: 2,
  sessionGapMinutes: 30,
});
export const labels = Object.freeze({
  not_started: "Не пробовал",
  practicing: "Практикую",
  demonstrated: "Получается",
  due: "Пора повторить",
});
const HOUR = 3600000;
export function projectProgress(catalog, history, now) {
  const cards = new Map(catalog.cards.map((c) => [c.id, c]));
  const events = history
    .filter(
      (e) =>
        cards.has(e.cardId) &&
        Number.isFinite(Date.parse(e.time)) &&
        Date.parse(e.time) <= now &&
        typeof e.correct === "boolean" &&
        typeof e.assisted === "boolean",
    )
    .slice()
    .sort(
      (a, b) =>
        Date.parse(a.time) - Date.parse(b.time) ||
        String(a.id).localeCompare(String(b.id)),
    );
  const seenIds = new Set();
  const unique = events.filter((e) => !seenIds.has(e.id) && seenIds.add(e.id));
  const byCard = new Map();
  for (const e of unique) {
    if (!byCard.has(e.cardId)) byCard.set(e.cardId, []);
    byCard.get(e.cardId).push(e);
  }
  const groups = Object.entries(catalog.taskNames).map(([id, name]) => {
    const members = catalog.cards.filter((c) => String(c.task) === id);
    const eligible = members.filter((c) => c.eligibleForProgress);
    const pool = new Set(eligible.map((c) => c.id));
    const attempts = unique.filter((e) => pool.has(e.cardId));
    const evidence = attempts.filter(
      (e) =>
        e.materialVersion === cards.get(e.cardId).materialVersion &&
        !e.assisted,
    );
    let demonstrated = false,
      lastSuccess = null,
      errors = 0,
      session = 0,
      previous = null;
    let window = [];
    for (const e of evidence) {
      const time = Date.parse(e.time);
      if (
        previous === null ||
        time - previous >= policy.sessionGapMinutes * 60000
      )
        session++;
      previous = time;
      if (!e.correct) {
        errors++;
        window = [];
        if (errors >= policy.demotionErrors) {
          demonstrated = false;
          lastSuccess = null;
          window = [];
        }
        continue;
      }
      errors = 0;
      window = window.filter((v) => v.cardId !== e.cardId);
      window.push({ ...e, session, time });
      window = window.slice(-policy.distinctCards);
      if (
        demonstrated ||
        (window.length >= policy.distinctCards &&
          new Set(window.map((v) => v.session)).size >= policy.sessions &&
          time - window[0].time >= policy.spanHours * HOUR)
      ) {
        demonstrated = true;
        lastSuccess = time;
      }
    }
    const dueAt = demonstrated ? lastSuccess + policy.reviewHours * HOUR : null;
    const status = demonstrated
      ? now >= dueAt
        ? "due"
        : "demonstrated"
      : attempts.length
        ? "practicing"
        : "not_started";
    return {
      id: Number(id),
      name,
      status,
      eligible: eligible.length,
      total: members.length,
      attempted: new Set(attempts.map((e) => e.cardId)).size,
      dueAt,
      lastSuccess,
      evidenceCards: window.length,
      sessions: new Set(window.map((v) => v.session)).size,
      reason: demonstrated
        ? "Есть самостоятельные решения на разных карточках и в разных сессиях."
        : `Нужно ${policy.distinctCards} разных карточки в ${policy.sessions} сессиях, между первой и последней — не менее ${policy.spanHours} ч.`,
      errors,
    };
  });
  const cardStates = new Map(
    catalog.cards.map((c) => {
      const attempts = byCard.get(c.id) || [];
      const qualified = attempts.filter(
        (e) => e.materialVersion === c.materialVersion && !e.assisted,
      );
      const last = qualified.at(-1),
        group = groups.find((g) => g.id === c.task);
      const status = !attempts.length
        ? "not_started"
        : c.eligibleForProgress &&
            last?.correct &&
            ["demonstrated", "due"].includes(group?.status)
          ? group.status
          : "practicing";
      return [c.id, status];
    }),
  );
  const counts = Object.fromEntries(
    Object.keys(labels).map((s) => [
      s,
      [...cardStates.values()].filter((v) => v === s).length,
    ]),
  );
  const total = catalog.cards.length,
    covered = total - counts.not_started;
  const consolidated = groups.filter((g) =>
    ["demonstrated", "due"].includes(g.status),
  ).length;
  return {
    now,
    groups,
    cardStates,
    counts,
    total,
    covered,
    events: unique,
    consolidated,
    skillTotal: groups.length,
    consolidation: groups.length
      ? Math.floor((100 * consolidated) / groups.length)
      : null,
    coverage: total ? Math.floor((100 * covered) / total) : null,
  };
}
