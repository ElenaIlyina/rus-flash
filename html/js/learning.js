/** Deterministic projection of completion results; no model calls or hidden clock. */
import { defaults, validateSettings } from "./settings.js";
export const policy = Object.freeze({
  id: "learning-score-v1",
  sessionGapMinutes: 30,
});
export const labels = Object.freeze({
  not_started: "Не пробовал",
  practicing: "Практикую",
  demonstrated: "Получается",
  due: "Пора повторить",
});
export function completionScore(event) {
  if (!event.correct) return null;
  if (event.scoringVersion === 1)
    return event.completed
      ? event.assisted
        ? 0
        : 1 / event.attemptNumber
      : null;
  // Legacy data cannot distinguish hints from retries: never invent a retry count.
  return event.assisted ? null : 1;
}
export function projectProgress(catalog, history, now, settings = defaults) {
  const config = validateSettings(settings);
  const cards = new Map(catalog.cards.map((c) => [c.id, c]));
  const seen = new Set();
  const unique = history
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
    )
    .filter((e) => !seen.has(e.id) && seen.add(e.id));
  const byCard = new Map(),
    scores = new Map(),
    completions = new Set();
  const groupData = new Map(
    Object.keys(catalog.taskNames).map((id) => [
      Number(id),
      { score: 0, lastSuccess: null, results: 0 },
    ]),
  );
  const update = (old, value, a) => (old + a * value) / (1 + a);
  for (const e of unique) {
    if (!byCard.has(e.cardId)) byCard.set(e.cardId, []);
    byCard.get(e.cardId).push(e);
    const card = cards.get(e.cardId),
      result = completionScore(e);
    if (
      result === null ||
      !card.eligibleForProgress ||
      e.materialVersion !== card.materialVersion
    )
      continue;
    const key = e.scoringVersion === 1 ? `${e.cardId}:${e.assignmentId}` : e.id;
    if (completions.has(key)) continue;
    completions.add(key);
    const old = scores.get(e.cardId);
    const score = old ? update(old.score, result, config.cardA) : result;
    scores.set(e.cardId, {
      score,
      lastSuccess: score > config.masteryThreshold ? Date.parse(e.time) : null,
    });
    const group = groupData.get(card.task);
    if (group) {
      const weight = card.exerciseKind === "simple" ? config.simpleWeight : 1;
      if (weight > 0) {
        group.score = update(group.score, result, config.topicA * weight);
        group.results++;
        group.lastSuccess =
          group.score > config.masteryThreshold ? Date.parse(e.time) : null;
      }
    }
  }
  const status = (score, lastSuccess, attempted) =>
    score !== null && score > config.masteryThreshold
      ? now >= lastSuccess + config.reviewDays * 86400000
        ? "due"
        : "demonstrated"
      : attempted
        ? "practicing"
        : "not_started";
  const groups = Object.entries(catalog.taskNames).map(([id, name]) => {
    const members = catalog.cards.filter((c) => c.task === Number(id));
    const group = groupData.get(Number(id));
    const attempted = members.filter((c) => byCard.has(c.id)).length;
    const s = status(group.score, group.lastSuccess, attempted);
    return {
      id: Number(id),
      name,
      ...group,
      total: members.length,
      eligible: members.filter((c) => c.eligibleForProgress).length,
      attempted,
      status: s,
      dueAt:
        group.lastSuccess === null
          ? null
          : group.lastSuccess + config.reviewDays * 86400000,
      reason: `Оценка темы: ${group.score.toFixed(3)}. «Получается» — выше ${config.masteryThreshold}. Завершённых решений в расчёте: ${group.results}.`,
    };
  });
  const cardStates = new Map(
    catalog.cards.map((c) => {
      const value = scores.get(c.id);
      return [
        c.id,
        status(
          value?.score ?? null,
          value?.lastSuccess ?? null,
          byCard.has(c.id),
        ),
      ];
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
    settings: config,
    groups,
    cardStates,
    cardScores: new Map(
      catalog.cards.map((c) => [c.id, scores.get(c.id)?.score ?? null]),
    ),
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
