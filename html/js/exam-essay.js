export const essayCriteria = [
  ['Позиция автора по заданной проблеме', 1],
  ['Комментарий к позиции автора', 3],
  ['Собственное отношение к позиции автора и его обоснование', 2],
  ['Фактическая точность', 1],
  ['Логичность', 2],
  ['Соблюдение этических норм', 1],
  ['Орфография', 3],
  ['Пунктуация', 3],
  ['Грамматические нормы', 3],
  ['Речевые нормы', 3],
];

// A reviewer determines which quoted or copied passages count towards the limit.
export function wordEstimate(value) {
  const withoutInitials = value.replace(/(?:[А-ЯЁA-Z]\.\s*)+(?=[А-ЯЁA-Z][а-яёa-z])/gu, '');
  return (withoutInitials.match(/\p{L}+(?:[-‑]\p{L}+)*/gu) || []).length;
}

export function essayReview(words, points) {
  if (!Number.isInteger(words) || words < 0 || !Number.isInteger(points) || points < 0 || points > 22)
    throw new Error('Введите подтверждённое число слов и целый балл от 0 до 22.');
  if (words < 150 && points !== 0)
    throw new Error('При объёме менее 150 слов за сочинение выставляется 0 баллов.');
  return { words, points };
}
