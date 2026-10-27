import { orderCards } from "./bank-order.js";
import { policy } from "./learning.js";

/** First adaptive slice: explainable selection within a chosen group, not a skill graph. */
export function recommendPractice({
  catalog,
  progress,
  tags = () => ({}),
  seed = 0,
  task,
  excludeIds = [],
}) {
  const history = progress.events;
  const excluded = new Set(excludeIds);
  const pool = catalog.cards.filter(
    (card) =>
      card.eligibleForProgress &&
      !excluded.has(card.id) &&
      (task === undefined || card.task === task),
  );
  const recent = new Set(
    history
      .filter(
        (event) =>
          progress.now - Date.parse(event.time) <
          policy.sessionGapMinutes * 60000,
      )
      .slice(-3)
      .map((event) => event.cardId),
  );
  const cooled = pool.filter((card) => !recent.has(card.id));
  const candidates = orderCards(
    cooled.length ? cooled : pool,
    "practice",
    progress,
    history,
    tags,
    seed,
  );
  const card = candidates[0];
  if (!card)
    return {
      kind: "unavailable",
      cardId: null,
      reasonCode: "no_eligible_material",
      reasonText:
        "В выбранной группе нет другой доступной карточки с проверенным ответом.",
      policyVersion: "practice-recommendation-v0",
      alternatives: [],
    };
  const last = history.filter((event) => event.cardId === card.id).at(-1);
  const status = progress.cardStates.get(card.id);
  const [reasonCode, reasonText] =
    status === "due"
      ? ["review_due", "Пришло время повторить эту тему."]
      : tags(card.id).hard
        ? ["marked_for_review", "Вы отметили эту карточку для повторения."]
        : last?.correct === false
          ? [
              "previous_error",
              "В прошлой попытке ответ не совпал с эталоном. Это повод для практики, а не диагноз конкретного правила.",
            ]
          : !last
            ? ["not_tried", "Эту карточку вы ещё не пробовали."]
            : [
                "continue_practice",
                "Продолжим практику в выбранной группе заданий.",
              ];
  return {
    kind: status === "due" ? "review" : "practice",
    cardId: card.id,
    skillId: card.skillId,
    reasonCode,
    reasonText,
    policyVersion: "practice-recommendation-v0",
    alternatives: candidates.slice(1, 3).map((c) => c.id),
  };
}
