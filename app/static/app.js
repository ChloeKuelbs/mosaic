'use strict';
const $ = id => document.getElementById(id);
const trials = new Map();
const selected = new Set();
let nextToken = null;
let activeQuery = '';
let loading = false;
const pretty = value => value == null || value === '' ? 'Not reported' : String(value).replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
const list = values => values?.length ? values.map(pretty).join(' · ') : 'Not reported';
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function source(trial) {
  const a = element('a', `${trial.nct_id} ↗`);
  // Construct from a validated identifier rather than accepting arbitrary URLs.
  a.href = `https://clinicaltrials.gov/study/${encodeURIComponent(trial.nct_id)}`;
  a.target = '_blank'; a.rel = 'noopener noreferrer';
  return a;
}
function renderCards() {
  $('results').replaceChildren();
  for (const trial of trials.values()) {
    const card = element('article', undefined, 'trial');
    const top = element('div', undefined, 'trial-top');
    top.append(source(trial), element('span', pretty(trial.status), 'badge'));
    const dl = element('dl');
    for (const [label, value] of [
      ['Interventions', list(trial.interventions.map(i => i.name))],
      ['Participants', trial.enrollment == null ? 'Not reported' : `${trial.enrollment.toLocaleString()} · ${pretty(trial.enrollment_type)}`],
      ['Study type', pretty(trial.study_type)], ['Phase', list(trial.phases)]
    ]) {
      const pair = element('div'); pair.append(element('dt', label), element('dd', value)); dl.append(pair);
    }
    const label = element('label', undefined, 'select');
    const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.checked = selected.has(trial.nct_id);
    checkbox.setAttribute('aria-label', `Compare ${trial.nct_id}`);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked && selected.size >= 3) {
        checkbox.checked = false;
        $('status').textContent = 'Compare up to 3 trials at a time. Deselect a trial to choose another.';
        return;
      }
      checkbox.checked ? selected.add(trial.nct_id) : selected.delete(trial.nct_id);
      renderComparison(); syncAiState();
    });
    label.append(checkbox, document.createTextNode('Add to comparison'));
    card.append(top, element('h3', trial.title || 'Title not reported'), dl, label);
    $('results').append(card);
  }
}
function renderComparison() {
  $('comparison').hidden = selected.size === 0;
  if ($('ai-answer')) $('ai-answer').hidden = true;
  const table = $('comparison-table'); table.replaceChildren();
  if (!selected.size) return;
  const chosen = [...selected].map(id => trials.get(id));
  const caption = element('caption', `Comparison of ${chosen.length} selected trial${chosen.length === 1 ? '' : 's'}`);
  table.append(caption);
  const head = element('thead'), heading = element('tr');
  heading.append(element('th', 'Registry field'));
  chosen.forEach(trial => {
    const th = element('th'); th.scope = 'col'; th.append(source(trial), element('p', trial.title || 'Title not reported')); heading.append(th);
  });
  head.append(heading); table.append(head);
  const body = element('tbody');
  const rows = [
    ['Status', t => pretty(t.status)],
    ['Interventions', t => list(t.interventions.map(i => i.name))],
    ['Study design', t => [pretty(t.study_type), list(t.phases), `Allocation: ${pretty(t.allocation)}`, `Masking: ${pretty(t.masking)}`].join('\n')],
    ['Enrollment', t => t.enrollment == null ? 'Not reported' : `${t.enrollment.toLocaleString()} (${pretty(t.enrollment_type)})`],
    ['Eligibility', t => {
      const wrapper = element('div', `Sex: ${pretty(t.eligibility_sex)} · Age: ${t.minimum_age || 'Not reported'} to ${t.maximum_age || 'Not reported'}`);
      if (t.eligibility_criteria) { const d = element('details'); d.append(element('summary', 'Full eligibility criteria'), element('p', t.eligibility_criteria)); wrapper.append(d); }
      return wrapper;
    }],
    ['Primary outcomes', t => {
      const wrapper = element('div');
      if (!t.primary_outcomes.length) return 'Not reported';
      t.primary_outcomes.forEach(o => wrapper.append(element('p', `${o.measure} — Time frame: ${o.time_frame || 'Not reported'}`)));
      return wrapper;
    }],
    ['Sponsor', t => t.sponsor || 'Not reported'],
    ['Results posted', t => t.has_results == null ? 'Not reported' : t.has_results ? 'Yes · open source for results' : 'No'],
    ['Registry updated', t => t.last_update || 'Not reported']
  ];
  for (const [label, getValue] of rows) {
    const row = element('tr'), th = element('th', label); th.scope = 'row'; row.append(th);
    chosen.forEach(trial => { const td = element('td'), value = getValue(trial); td.style.whiteSpace = 'pre-line'; td.append(value instanceof Node ? value : document.createTextNode(value)); row.append(td); });
    body.append(row);
  }
  table.append(body);
}
function syncAiState() {
  const disabled = !selected.size;
  $('ai-submit').disabled = disabled || aiLoading;
  if (!aiLoading) $('ai-message').textContent = disabled ? 'Select trial cards to enable analysis.' : `${selected.size} selected trial${selected.size === 1 ? '' : 's'} · Ask a question about these records.`;
}
let aiLoading = false;
async function askAi() {
  if (aiLoading || selected.size === 0) return;
  aiLoading = true; syncAiState();
  $('ai-submit').disabled = true;
  $('ai-answer').hidden = true;
  $('ai-message').textContent = 'Reading selected trial records and generating a grounded answer…';
  try {
    const response = await fetch('/ai/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: $('ai-question').value.trim(), nct_ids: [...selected]})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Unable to generate an answer right now.');
    $('ai-answer-text').textContent = data.answer;
    const sources = $('ai-sources'); sources.replaceChildren();
    sources.append(element('strong', 'Registry sources: '));
    const cited = new Set(data.cited_ids);
    data.sources.filter(s => cited.has(s.nct_id)).forEach(s => {
      const a = element('a', s.nct_id + ' ↗');
      a.href = 'https://clinicaltrials.gov/study/' + encodeURIComponent(s.nct_id);
      a.target = '_blank'; a.rel = 'noopener noreferrer';
      sources.append(a);
    });
    if (!cited.size) sources.append(element('span', 'No supporting registry fields identified.'));
    $('ai-answer').hidden = false;
    $('ai-message').textContent = 'AI-generated answer. Verify details in the source records.';
  } catch (err) {
    $('ai-message').textContent = err.message;
  } finally {
    aiLoading = false; syncAiState();
  }
}
async function search(append = false) {
  if (loading) return;
  loading = true;
  if (!append) {
    activeQuery = $('intervention').value.trim(); nextToken = null; trials.clear(); selected.clear(); renderCards(); renderComparison(); syncAiState();
  }
  $('error').hidden = true; $('results').setAttribute('aria-busy', 'true');
  $('search-button').disabled = true; $('load-more').disabled = true;
  document.querySelectorAll('[data-query]').forEach(b => b.disabled = true);
  $('search-button').textContent = 'Searching…'; $('status').textContent = 'Searching ClinicalTrials.gov…';
  const params = new URLSearchParams({page_size: '10'});
  if (activeQuery) params.set('intervention', activeQuery);
  if (append && nextToken) params.set('page_token', nextToken);
  try {
    const response = await fetch(`/trials/compare?${params}`);
    if (!response.ok) throw new Error(response.status === 504 ? 'The registry took too long to respond. Please try again.' : 'We couldn’t retrieve trials. Please try again shortly.');
    const data = await response.json();
    data.trials.forEach(t => trials.set(t.nct_id, t)); nextToken = data.next_page_token;
    renderCards();
    const count = data.total_count == null ? '' : ` of ${data.total_count.toLocaleString()} registry matches`;
    $('status').textContent = trials.size ? `${trials.size} shown${count} · Select up to 3 to compare below. Retrieved ${new Date(data.retrieved_at).toLocaleString()}.` : 'No trials found. Try another intervention or leave the search blank.';
  } catch (error) {
    $('error').textContent = error.message; $('error').hidden = false;
    $('status').textContent = append ? `${trials.size} trials remain available. Select “Load more trials” to retry.` : 'Search unavailable. Submit your search again to retry.';
  } finally {
    loading = false; $('results').setAttribute('aria-busy', 'false');
    $('search-button').disabled = false; $('search-button').textContent = 'Explore trials →';
    $('load-more').disabled = false; $('load-more').hidden = !nextToken;
    document.querySelectorAll('[data-query]').forEach(b => b.disabled = false);
  }
}
$('search-form').addEventListener('submit', event => { event.preventDefault(); search(); });
document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => { $('intervention').value = button.dataset.query; search(); }));
$('load-more').addEventListener('click', () => search(true));
$('clear').addEventListener('click', () => { selected.clear(); renderCards(); renderComparison(); syncAiState(); });

$('ai-form').addEventListener('submit', e => { e.preventDefault(); askAi(); });
document.querySelectorAll('[data-ai-prompt]').forEach(b => b.addEventListener('click', () => { $('ai-question').value = b.dataset.aiPrompt; askAi(); }));
syncAiState();
