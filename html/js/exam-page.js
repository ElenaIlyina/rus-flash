import { esc, rich, cardExplanation, matchingColumns } from './ui.js';
import { loadCard } from './data.js';
import { generateVariant, gradeVariant, modes, maxPoints, validateSession } from './exam.js';
import { theoryFor } from './exam-theory.js';

const KEY = 'rusflash_variants_v1';
function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved?.schemaVersion === 1 && Array.isArray(saved.sessions) && saved.sessions.every(s =>
      typeof s.id === 'string' && Object.hasOwn(modes, s.mode) && Array.isArray(s.items) && s.items.length === 26 &&
      s.answers && typeof s.answers === 'object' && Object.values(s.answers).every(v => typeof v === 'string') &&
      Array.isArray(s.theoryUsed) && Number.isInteger(s.cursor) && s.cursor >= 0 && s.cursor <= 26 &&
      (!s.finishedAt || Array.isArray(s.results)))) return saved;
  } catch { /* A malformed variant never affects card progress. */ }
  return { schemaVersion: 1, sessions: [], activeId: null };
}
function button(action, label, style = 'secondary', extra = '') {
  return `<button type="button" class="button ${style}" data-exam="${action}" ${extra}>${label}</button>`;
}
function sourceLinks(task, meta) {
  const lists = { 1: 'connections', 2: 'meanings', 3: 'style', 4: 'stress-words', 5: 'paronyms&view=theory', 6: 'lexical', 7: 'word-forms' };
  if (lists[task]) return `<a href="#knowledge?list=${lists[task]}" class="text-link">Подробнее в справочнике</a>`;
  return (meta.ruleRefs || []).map(r => `<a class="text-link" href="#knowledge?rule=${esc(r.id)}">${esc(r.label)}</a>`).join(' ') || '<a href="#knowledge" class="text-link">Открыть справочник</a>';
}
function theoryComparison(comparison) {
  if (!comparison) return '';
  return `<table class="exam-theory-comparison"><caption>${esc(comparison.title)}</caption><thead><tr>${comparison.headers.map(label => `<th scope="col">${esc(label)}</th>`).join('')}</tr></thead><tbody>${comparison.rows.map(row => `<tr><th scope="row">${esc(row[0])}</th>${row.slice(1).map(value => `<td>${esc(value)}</td>`).join('')}</tr>`).join('')}</tbody></table><p>${esc(comparison.note)}</p><p><a class="text-link" href="${esc(comparison.source.url)}" target="_blank" rel="noopener noreferrer">${esc(comparison.source.label)}</a></p>`;
}
export function createExamController({ main, getCatalog, isCurrent }) {
  const state = loadState();
  let view = state.activeId ? 'session' : 'home', selectedId = state.activeId;
  let busy = false, error = '', confirming = '', serial = 0, storageFailed = false;
  const cache = new Map();
  function getCard(id) {
    if (!cache.has(id)) cache.set(id, loadCard(id).catch(e => { cache.delete(id); throw e; }));
    return cache.get(id);
  }
  const session = () => state.sessions.find(s => s.id === selectedId);
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); storageFailed = false; }
    catch { storageFailed = true; }
    const warning = main.querySelector('[data-exam-storage]');
    if (warning) warning.hidden = !storageFailed;
  }
  function wrap(content) {
    main.innerHTML = `<section class="exam-page"><div class="page-heading"><div><div class="eyebrow">ШАГ ЗА ШАГОМ ПО ВСЕМ ТЕМАМ</div><h1>Варианты</h1><p>Учебные варианты по банку ЕГЭ · 26 заданий с автопроверкой</p></div></div>
      <p class="feedback warning" data-exam-storage ${storageFailed ? '' : 'hidden'}>Не удалось сохранить вариант в браузере. Не закрывайте страницу: ответы сейчас хранятся только в памяти.</p>
      ${error ? `<p class="feedback warning" role="alert">${esc(error)}</p>` : ''}${content}</section>`;
  }
  function home() {
    const active = state.sessions.find(s => s.id === state.activeId && !s.finishedAt && !s.abandonedAt);
    const history = [...state.sessions].filter(s => s.finishedAt).reverse();
    wrap(`<p class="exam-note">Варианты собираются из проверяемых карточек. №1–3 и №23–26 используют общие тексты внутри своих блоков. Это учебная сборка банка, а не официальный экзаменационный вариант. Сочинение доступно отдельно как черновик и не оценивается автоматически.</p>
      ${active ? `<section class="panel"><h2>Незаконченный вариант</h2><p>${esc(modes[active.mode])} · заполнено ${Object.values(active.answers).filter(v => v.trim()).length} из 26</p>${button('resume', 'Продолжить', 'primary')}${button('discard-ask', 'Удалить незаконченный вариант', 'quiet')}${confirming === 'discard' ? `<p>Ответы этого незаконченного варианта будут удалены.</p>${button('discard', 'Удалить вариант', 'secondary')}${button('cancel', 'Сохранить и вернуться', 'quiet')}` : ''}</section>` : ''}
      <div class="exam-modes">${Object.entries(modes).map(([key, label]) => `<section class="panel"><h2>${label}</h2><p>${key === 'learning' ? 'Короткая теория перед каждым заданием — открывайте по необходимости. Ответы и разборы после завершения.' : key === 'exam' ? 'Без теории и подсказок. Итог — число верных заданий и разбор после завершения.' : 'Без помощи. №8 и №22: 2 или 0 баллов; остальные: 1 или 0. Максимум 28 баллов.'}</p>${button('start', 'Начать вариант', 'primary', `data-mode="${key}" ${active ? 'disabled' : ''}`)}</section>`).join('')}</div>
      <p>Варианты и ответы сохраняются в этом браузере отдельно от прогресса по карточкам. При следующей сборке приоритет получают карточки и группы тем, реже встречавшиеся в завершённых вариантах. Результат с теорией отмечается отдельно.</p>
      <section class="panel"><h2>Завершённые варианты</h2>${history.length ? `<ul class="exam-history">${history.map(s => `<li>${button('result', `${esc(modes[s.mode])} · ${new Date(s.finishedAt).toLocaleDateString('ru-RU')} · ${s.results.filter(r => r.correct).length}/26 верно${s.mode === 'scored' ? ' · '+s.results.reduce((n,r) => n+r.points,0)+'/28 баллов' : ''}`, 'quiet', `data-id="${esc(s.id)}"`)}</li>`).join('')}</ul>` : '<p>Здесь появятся результаты завершённых вариантов.</p>'}</section>`);
  }
  async function render() {
    const token = ++serial;
    const s = session();
    if (view === 'home' || !s) { home(); return; }
    if (s.finishedAt) { await result(s, token); return; }
    if (!validateSession(s, getCatalog())) {
      error = 'Материал варианта изменился или стал недоступен для проверки. Ответы сохранены. Вернитесь к списку и создайте новый вариант.';
      wrap(`${button('home', 'К списку вариантов')}`); return;
    }
    const isEssay = s.cursor === 26;
    const item = s.items[s.cursor];
    wrap('<p role="status">Открываем задание…</p>');
    try {
      const card = await getCard(isEssay ? s.essayId : item.id);
      if (token !== serial || !isCurrent()) return;
      const meta = getCatalog().cards.find(c => c.id === card.id);
      const t = isEssay ? null : theoryFor(item.task);
      const value = isEssay ? s.essay : s.answers[item.id] || '';
      const completed = Object.values(s.answers).filter(v => v.trim()).length;
      wrap(`<div class="exam-toolbar">${button('home', 'К списку', 'quiet')}<span>${esc(modes[s.mode])} · заполнено <b data-exam-completed>${completed}</b> / 26</span>${button('finish-ask', 'Завершить вариант', 'secondary')}</div>
        <nav class="exam-numbers" aria-label="Задания варианта">${s.items.map((it,i) => button('jump', String(it.task), 'quiet', `data-index="${i}" aria-label="Задание ${it.task}${s.answers[it.id]?.trim() ? ', ответ сохранён' : ''}" ${s.cursor === i ? 'aria-current="step"' : ''} ${s.answers[it.id]?.trim() ? 'data-answered' : ''}`)).join('')}${s.essayId ? button('jump', 'Черновик', 'quiet', `data-index="26" ${isEssay ? 'aria-current="step"' : ''}`) : ''}</nav>
        ${confirming === 'finish' ? `<section class="panel exam-confirm" role="region" aria-label="Завершение варианта"><h2>Завершить и проверить?</h2><p>Без ответа: ${26-completed}. Они получат 0 баллов. После завершения ответы нельзя изменить.</p>${button('finish', 'Завершить и проверить', 'primary')}${button('cancel', 'Продолжить решение', 'quiet')}</section>` : ''}
        ${t && s.mode === 'learning' ? `<details class="exam-theory panel" data-exam-theory><summary>Теория · ${esc(t.title)}</summary><p>${esc(t.rule)}</p><ol>${t.steps.map(step => `<li>${esc(step)}</li>`).join('')}</ol><p><b>Обратите внимание:</b> ${esc(t.trap)}</p>${theoryComparison(t.comparison)}<div class="rule-links">${sourceLinks(item.task, meta)}</div><p class="muted">Краткая учебная опора; разбор конкретного задания появится после завершения варианта.</p></details>` : ''}
        <article class="exercise"><span class="eyebrow">${isEssay ? 'ДОПОЛНИТЕЛЬНО · БЕЗ АВТОМАТИЧЕСКОЙ ОЦЕНКИ' : `ЗАДАНИЕ ${item.task} · КАРТОЧКА ${item.id}`}</span><h2>${isEssay ? 'Письменный черновик' : esc(getCatalog().taskNames[item.task])}</h2>
        ${isEssay ? '<p class="feedback warning">Письменное задание из банка может относиться к прежнему формату. Это дополнительная практика; текст не входит в балл за №1–26.</p>' : s.mode === 'scored' ? `<p>Максимум за задание: ${maxPoints(item.task)}. Баллы начисляются только за полностью правильный ответ.</p>` : ''}
        ${card.passage ? `<details class="passage" open><summary>Текст к заданию</summary><div class="passage-content">${rich(card.passage)}</div></details>` : ''}
        <div class="question-text">${rich(card.instruction)}</div>
        ${matchingColumns(card)}
        ${card.options.length ? `<div class="options">${card.options.map((x,i) => `<div class="option static-option"><span class="option-number">${i+1}</span><span>${rich(x)}</span></div>`).join('')}</div>` : ''}
        <div class="answer-form"><label for="exam-answer">${isEssay ? 'Ваш черновик' : 'Ваш ответ'}</label>${isEssay ? `<textarea id="exam-answer" rows="14">${esc(value || '')}</textarea>` : `<input id="exam-answer" autocomplete="off" value="${esc(value)}" placeholder="${card.responseType === 'matching' ? 'Номера в порядке соответствий, например 13254' : 'Введите ответ'}">`}<p class="muted">Ответ сохраняется автоматически. ${isEssay ? '' : 'Проверка — после завершения всего варианта.'}</p></div>
        <div class="exam-toolbar">${button('previous', 'Назад', 'quiet', s.cursor === 0 ? 'disabled' : '')}${button('next', isEssay || s.cursor === 25 && !s.essayId ? 'К завершению' : 'Следующее задание', 'primary')}</div></article>`);
    } catch(e) {
      if (token === serial && isCurrent()) { error = e.message; wrap(`${button('retry', 'Повторить загрузку')}${button('home', 'К списку', 'quiet')}`); }
    }
  }
  async function result(s, token) {
    wrap('<p role="status">Открываем результат…</p>');
    try {
      const cards = await Promise.all(s.items.map(item => getCard(item.id)));
      if (token !== serial || !isCurrent()) return;
      const points = s.results.reduce((sum,r) => sum+r.points,0), correct = s.results.filter(r => r.correct).length;
      wrap(`${button('home', 'К списку вариантов', 'quiet')}${!validateSession(s,getCatalog()) ? '<p class="feedback warning">Материал обновился после этого прохождения. Баллы и ответы сохранены по версии на момент завершения; ниже показаны текущие разборы.</p>' : ''}<section class="panel"><span class="eyebrow">${esc(modes[s.mode])} · ЗАВЕРШЕНО</span><h2>${s.mode === 'scored' ? `${points} из 28 баллов` : `${correct} из 26 заданий верно`}</h2><p>${s.mode === 'scored' ? `${correct} из 26 заданий верно. ` : ''}Теория открывалась в ${s.theoryUsed.length} заданиях. Время: ${Math.max(1,Math.round((s.finishedAt-s.startedAt)/60000))} мин.</p><p>Это результат учебной сборки. Баллы не переводятся в официальную экзаменационную оценку. Прохождение с теорией учитывается отдельно.</p></section>
      <section><h2>Результат по заданиям</h2>${s.results.map((r,i) => `<details class="panel exam-result"><summary>№${r.task} · ${r.correct ? 'Верно' : 'Неверно / нет ответа'}${s.mode === 'scored' ? ` · ${r.points}/${r.max} балла` : ''}${r.assisted ? ' · с теорией' : ''}</summary><p><b>Ваш ответ:</b> ${esc(r.answer || 'не дан')}</p><p><b>Правильный ответ:</b> ${r.expected.map(esc).join(' / ')}</p><div class="explanation-text">${cards[i].explanation ? cardExplanation(cards[i].explanation, r.task) : '<p>Разбор этой карточки пока не подготовлен.</p>'}</div><a class="text-link" href="#card/${r.id}">Открыть карточку ${r.id} и источники</a></details>`).join('')}</section>
      ${s.essayId ? `<details class="panel"><summary>Письменный черновик · без оценки</summary><pre class="exam-draft">${esc(s.essay || 'Черновик не заполнен.')}</pre></details>` : ''}`);
    } catch(e) { if (token === serial && isCurrent()) { error=e.message; wrap(`${button('retry','Повторить загрузку')}${button('home','К списку','quiet')}`); } }
  }
  main.addEventListener('input', e => {
    if (e.target.id !== 'exam-answer') return;
    const s = session();
    if (!s || s.finishedAt) return;
    if (s.cursor === 26) s.essay = e.target.value;
    else s.answers[s.items[s.cursor].id] = e.target.value;
    save();
    const completed = main.querySelector('[data-exam-completed]');
    if (completed) completed.textContent = Object.values(s.answers).filter(v => v.trim()).length;
    const current = main.querySelector('[aria-current="step"]');
    if (current && s.cursor < 26) current.toggleAttribute('data-answered', Boolean(e.target.value.trim()));
    if (confirming === 'finish') { confirming = ''; main.querySelector('.exam-confirm')?.remove(); }
  });
  main.addEventListener('toggle', e => {
    if (!e.target.matches('[data-exam-theory]') || !e.target.open) return;
    const s = session();
    if (!s || s.finishedAt || s.mode !== 'learning') return;
    const id = s.items[s.cursor]?.id;
    if (id && !s.theoryUsed.includes(id)) { s.theoryUsed.push(id); save(); }
  }, true);
  main.addEventListener('click', async e => {
    const b = e.target.closest('[data-exam]');
    if (!b || busy || !isCurrent()) return;
    error = '';
    const action = b.dataset.exam, s = session();
    try {
      if (action === 'home') { view='home'; confirming=''; }
      if (action === 'start') {
        if (state.sessions.some(s => s.id === state.activeId && !s.finishedAt && !s.abandonedAt)) return;
        const seed = crypto.getRandomValues(new Uint32Array(1))[0];
        const next = generateVariant(getCatalog(), state.sessions, { seed, mode: b.dataset.mode });
        state.sessions.push(next); state.activeId=selectedId=next.id; view='session'; save();
      }
      if (action === 'resume') { selectedId=state.activeId; view='session'; }
      if (action === 'result') { selectedId=b.dataset.id; view='result'; }
      if (action === 'discard-ask') confirming='discard';
      if (action === 'discard') { state.sessions=state.sessions.filter(x=>x.id!==state.activeId); state.activeId=null; selectedId=null; confirming=''; save(); }
      if (action === 'cancel') confirming='';
      if (s && !s.finishedAt) {
        if (action === 'jump') { s.cursor=Math.max(0,Math.min(s.essayId ? 26 : 25,Number(b.dataset.index))); confirming=''; save(); }
        if (action === 'previous') { s.cursor=Math.max(0,s.cursor-1); confirming=''; save(); }
        if (action === 'next') {
          if (s.cursor === (s.essayId ? 26 : 25)) confirming='finish';
          else s.cursor++;
          save();
        }
        if (action === 'finish-ask') confirming='finish';
        if (action === 'finish') {
          if (!validateSession(s,getCatalog())) throw new Error('Материал изменился. Ответы сохранены; создайте новый вариант.');
          busy=true;
          main.querySelectorAll('input, textarea, button').forEach(el => { el.disabled=true; });
          b.textContent='Проверяем…';
          const cards=await Promise.all(s.items.map(it=>getCard(it.id)));
          s.results=gradeVariant(s,cards); s.finishedAt=Date.now(); state.activeId=null; confirming=''; save();
        }
      }
    } catch(e) { error=e.message; }
    finally { busy=false; if (isCurrent()) { await render(); if (action !== 'cancel') main.scrollIntoView({block:'start'}); } }
  });
  return { render };
}
