/** Variant selection and scoring, independent of the interface. */
import { checkResponse } from './assessment.js';

export const modes = { learning: 'С теорией', exam: 'Пробный экзамен', scored: 'С оценкой' };
export const maxPoints = task => [8, 22].includes(task) ? 2 : 1;
export const examMinutes = 210;
export const isFullExam = s => s.mode === 'exam' && s.examYear === 2027;
export function eligible(card) {
  return card.task >= 1 && card.task <= 26 && card.eligibleForProgress &&
    card.hasVerifiedAnswer && card.hasAnswer && !card.reviewNote &&
    !card.explanationNeedsSourceReview && !card.hasContentIssue;
}
function random(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6D2B79F5;
    let t = Math.imul(value ^ value >>> 15, 1 | value);
    t ^= t + Math.imul(t ^ t >>> 7, 61 | t);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
export function generateVariant(catalog, sessions = [], { seed, mode = 'learning', now = Date.now() } = {}) {
  if (!Object.hasOwn(modes, mode)) throw new Error('Неизвестный режим варианта.');
  const rng = random(seed);
  const used = new Map(), topics = new Map();
  for (const session of sessions.filter(s => s.finishedAt)) {
    for (const item of session.items) {
      used.set(item.id, (used.get(item.id) || 0) + 1);
      const topic = item.topic || `task-${item.task}`;
      topics.set(topic, (topics.get(topic) || 0) + 1);
    }
  }
  const pool = catalog.cards.filter(c => eligible(c) && c.examFormatEligible).sort((a, b) => a.id.localeCompare(b.id));
  const essays = new Map(catalog.cards.filter(c => c.task === 27 && c.examFormatEligible &&
    c.passageGroupId && !c.hasContentIssue && !c.reviewNote).map(c => [c.passageGroupId, c]));
  const cost = cards => cards.reduce((sum, c) => sum +
    (used.get(c.id) || 0) * 100 + (topics.get(c.examTopic) || 0), 0);
  function choose(choices) {
    if (!choices.length) throw new Error('Недостаточно проверенных карточек для совместимого варианта.');
    const ranked = choices.map(cards => ({ cards, cost: cost(cards), tie: rng() }));
    ranked.sort((a, b) => a.cost - b.cost || a.tie - b.tie);
    return ranked[0].cards;
  }
  const selected = [];
  for (const tasks of [[1, 2, 3], [23, 24, 25, 26]]) {
    const groups = new Map();
    for (const c of pool.filter(c => tasks.includes(c.task) && c.passageGroupId)) {
      if (tasks[0] === 23 && !essays.has(c.passageGroupId)) continue;
      if (!groups.has(c.passageGroupId)) groups.set(c.passageGroupId, new Map());
      const group = groups.get(c.passageGroupId);
      if (!group.has(c.task)) group.set(c.task, []);
      group.get(c.task).push(c);
    }
    const choices = [...groups.values()].filter(g => tasks.every(t => g.has(t)))
      .map(g => tasks.map(t => choose(g.get(t).map(c => [c]))[0]));
    selected.push(...choose(choices));
  }
  for (let task = 4; task <= 22; task++) selected.push(...choose(pool.filter(c => c.task === task).map(c => [c])));
  selected.sort((a, b) => a.task - b.task);
  const lastGroup = selected.find(c => c.task === 23).passageGroupId;
  const essay = essays.get(lastGroup);
  return { schemaVersion: 1, examYear: 2027, id: `${now}-${seed >>> 0}`, seed: seed >>> 0, mode, startedAt: now,
    finishedAt: null, cursor: 0, answers: {}, theoryUsed: [], essayId: essay?.id || null, essay: '',
    items: selected.map(c => ({ id: c.id, task: c.task, version: c.materialVersion, topic: c.examTopic })) };
}
export function gradeVariant(session, cards) {
  return session.items.map(item => {
    const card = cards.find(c => c.id === item.id);
    if (!card || !card.answer || !card.acceptedAnswers?.length) throw new Error('Не удалось загрузить эталон ответа. Вариант сохранён, попробуйте завершить его ещё раз.');
    const answer = session.answers[item.id] || '';
    const input = answer.trim();
    const correct = Boolean(input) && checkResponse(card.responseType, input, card.acceptedAnswers, card.sentenceNumbers);
    let points = correct ? maxPoints(item.task) : 0;
    if (!correct && isFullExam(session) && maxPoints(item.task) === 2 && /^\d+$/.test(input)) {
      const partial = card.acceptedAnswers.some(key => key.length === input.length &&
        [...key].filter((digit, i) => digit !== input[i]).length <= 2);
      if (partial) points = 1;
    }
    return { id: item.id, task: item.task, answer, expected: card.acceptedAnswers,
      correct, points, max: maxPoints(item.task),
      assisted: session.theoryUsed.includes(item.id) };
  });
}
export function validateSession(session, catalog) {
  return session?.items?.length === 26 && session.items.every((item, i) =>
    item.task === i + 1 && catalog.cards.some(c => c.id === item.id && c.task === item.task && c.materialVersion === item.version && eligible(c)));
}
