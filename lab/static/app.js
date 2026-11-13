const $ = (id) => document.getElementById(id);
const state = { entries: [], group: 'Series', parent: null, selected: null, token: '', status: {}, detailRequest: 0, page: location.hash && location.hash !== '#runs' ? 'results' : 'runs', pilot: null, launching: false };
const groups = ['Series', 'Pilots', 'Custom metrics', 'Checks & diagnostics'];
const noteDrafts = new Map();
window.addEventListener('beforeunload', event => {
  if ([...noteDrafts.values()].some(note => note.text !== note.saved)) { event.preventDefault(); event.returnValue = ''; }
});

async function renderNotes(id, request, title='Notes') {
  const panel = document.createElement('details');
  panel.className = 'result-notes';
  panel.innerHTML = '<summary>Notes</summary><p class="field-note">Saved in notes.md for this run or series.</p><label>Problems and observations<textarea rows="5" maxlength="20000" placeholder="Describe what happened…"></textarea></label><div><button type="button" disabled>Save notes</button><span role="status">Loading…</span></div>';
  panel.querySelector('summary').textContent = title;
  $('preview').append(panel);
  const input = panel.querySelector('textarea'), button = panel.querySelector('button'), status = panel.querySelector('[role=status]');
  input.disabled = true;
  try {
    let note = noteDrafts.get(id);
    if (!note || note.text === note.saved) {
      const loaded = await api(`/api/notes?id=${encodeURIComponent(id)}`);
      note = {...loaded, saved:loaded.text};
      noteDrafts.set(id, note);
    }
    if (request !== state.detailRequest) return;
    input.disabled = false;
    input.value = note.text;
    panel.open = !!note.text;
    const update = () => {
      button.disabled = note.saving || note.text === note.saved;
      status.textContent = note.saving ? 'Saving…' : note.text !== note.saved ? 'Unsaved changes' : note.text ? 'Saved' : 'No notes yet';
    };
    update();
    input.oninput = () => { note.text = input.value; update(); };
    button.onclick = async () => {
      const text = note.text;
      note.saving = true; update();
      try {
        if (!state.token) state.token = (await api('/api/status')).token;
        const saved = await api('/api/notes', {id, text, revision:note.revision});
        note.saved = saved.text; note.revision = saved.revision;
        note.saving = false; update();
      } catch(error) { note.saving = false; update(); status.textContent = error.message; }
    };
  } catch(error) { status.textContent = error.message; }
}
function showCustomFolder() {
  state.group = 'Custom metrics'; state.parent = null; state.selected = null;
  const request = ++state.detailRequest;
  history.replaceState(null, '', '#custom-metric');
  renderList();
  $('breadcrumb').textContent = 'results / custom-metric';
  $('preview').innerHTML = '<div class="eyebrow">Custom metrics</div><div class="preview-title"><h3>Custom metrics</h3></div><p class="preview-subtitle">Preparation and CPU/request HPA comparisons.</p>';
  renderNotes('custom-metric', request, 'About this folder');
}
const icon = (name) => `<svg aria-hidden="true"><use href="#${name}"/></svg>`;
const escape = (value) => String(value ?? '—').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = (row) => `<span class="badge ${escape(row.tone)}">${escape(row.status)}</span>`;
const mode = (value) => ({'fixed-1':'Fixed 1', 'fixed-3':'Fixed 3', 'autoscaling':'HPA · 1–3'}[value] || value || '—');
const date = (value) => value ? new Date(value).toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}) : '—';
const numeric = (value) => value == null ? '—' : Number(value).toLocaleString('en-GB', {maximumFractionDigits:0});
const latency = (value) => value == null ? '—' : `${(value / 1000).toFixed(3)} s`;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Lab-Token':state.token}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Cannot read local results');
  return data;
}
function notice(message) { $('notice').textContent = message || ''; $('notice').hidden = !message; }
function showPage(page, writeHash=true) {
  state.page = page;
  $('runs-page').hidden = page !== 'runs';
  $('results-page').hidden = page !== 'results';
  $('runs-tab').setAttribute('aria-pressed', String(page === 'runs'));
  $('results-tab').setAttribute('aria-pressed', String(page === 'results'));
  if (writeHash) history.replaceState(null, '', page === 'runs' ? '#runs' : `#${state.selected ? encodeURIComponent(state.selected) : 'results'}`);
  if (page === 'results') revealSelected();
}
function rowButton(row) {
  return `<button class="entry ${row.id === state.selected ? 'selected' : ''}" data-id="${escape(row.id)}" aria-pressed="${row.id === state.selected}" title="results/${escape(row.id)}">${icon(row.kind === 'series' ? 'folder' : 'file')}<span class="entry-body"><span class="entry-name">${escape(row.name)}</span><span class="entry-meta">${escape(mode(row.mode))}${row.profile ? ` · ${escape(row.profile)}` : ''}${row.kind === 'series' ? ` · ${row.completed}/${row.total} complete` : ''}</span><span class="entry-bottom">${badge(row)}<span class="entry-date">${date(row.date)}</span></span></span>${row.kind === 'series' ? '<svg class="chevron" aria-hidden="true"><use href="#arrow"/></svg>' : ''}</button>`;
}
function revealSelected() {
  const entry = $('entries').querySelector('.selected');
  if (!entry) return;
  const item = entry.getBoundingClientRect(), list = $('entries').getBoundingClientRect();
  if (item.bottom > list.bottom) $('entries').scrollTop += item.bottom - list.bottom + 5;
  else if (item.top < list.top) $('entries').scrollTop -= list.top - item.top + 5;
}
function renderList() {
  const focusedId = document.activeElement?.dataset.id;
  const focusedGroup = document.activeElement?.dataset.group;
  $('groups').innerHTML = groups.map(group => `<button class="group ${state.group === group ? 'selected' : ''}" aria-pressed="${state.group === group}" data-group="${group}">${icon('folder')}<span>${group}</span><span class="count">${state.entries.filter(e => e.group === group && e.kind === 'run').length}</span></button>`).join('');
  const parent = state.entries.find(e => e.id === state.parent);
  const rows = state.entries.filter(e => e.group === state.group && (parent ? e.parent === parent.id : !e.parent));
  if (parent) rows.sort((a,b) => a.id.localeCompare(b.id));
  $('back').hidden = !parent;
  $('list-title').textContent = parent ? parent.name : state.group;
  $('list-title').title = parent ? parent.id : state.group;
  $('list-count').textContent = `${rows.length} ${parent ? 'attempts' : 'items'}`;
  $('entries').innerHTML = rows.length ? rows.map(rowButton).join('') : '<div class="empty">No saved results in this group yet.</div>';
  revealSelected();
  const focus = [...$('entries').querySelectorAll('[data-id]'), ...$('groups').querySelectorAll('[data-group]')]
    .find(button => (focusedId && button.dataset.id === focusedId) || (focusedGroup && button.dataset.group === focusedGroup));
  focus?.focus({preventScroll:true});
  $('total').textContent = `${state.entries.filter(e => e.kind === 'run').length} runs`;
}
function folderBar(row) {
  return `<div class="folder-bar"><button id="open-folder">${icon('folder')}Open folder</button><span class="folder-path" title="${escape(row.path)}">results/${escape(row.id)}</span></div>`;
}
function plot(row) {
  return `<div class="plot-title">${icon('chart')}Saved plot<span>${row.plot ? 'Preview · open full plot ↗' : 'From disk'}</span></div>${row.plot ? `<a class="plot" href="/plot?id=${encodeURIComponent(row.plot)}" target="_blank" rel="noopener" title="Open full-size plot"><img src="/plot?id=${encodeURIComponent(row.plot)}" alt="Top of saved measurements for ${escape(row.name)}; open for the full plot"></a>` : '<div class="no-plot">No saved plot for this result.</div>'}`;
}
function metric(label, value, hint, small=false) {
  return `<div class="metric"><span class="metric-label">${escape(label)}</span><span class="metric-value${small ? ' small' : ''}">${escape(value)}</span><span class="metric-hint">${escape(hint)}</span></div>`;
}
async function select(id, enter=false) {
  const row = state.entries.find(e => e.id === id);
  if (!row) return;
  state.selected = id;
  state.group = row.group;
  state.parent = row.kind === 'run' ? row.parent || null : (enter ? row.id : null);
  if (state.page === 'results') history.replaceState(null, '', `#${encodeURIComponent(id)}`);
  renderList();
  $('breadcrumb').textContent = `results / ${id.replaceAll('/', ' / ')}`;
  $('preview').innerHTML = '<div class="empty">Reading saved result…</div>';
  const request = ++state.detailRequest;
  try {
    const data = await api(`/api/detail?id=${encodeURIComponent(id)}`);
    if (request !== state.detailRequest) return;
    const heading = `<div class="eyebrow">${icon(data.kind === 'series' ? 'folder' : 'file')}${escape(data.group)}<span>/</span>${data.kind === 'series' ? 'Series overview' : 'Run preview'}</div><div class="preview-title"><h3>${escape(data.name)}</h3>${badge(data)}</div><p class="preview-subtitle">${escape(mode(data.mode))} · ${date(data.date)}${data.profile ? ` · ${escape(data.profile)}` : ''}</p>`;
    const issues = [...(data.issues || []), ...(data.errors || [])].map(e => `<p class="issue">${escape(e)}</p>`).join('');
    if (data.kind === 'series') {
      const targetSummary = data.target_assessed ? `<p class="saved-state">Target met: ${data.target_met} / ${data.target_assessed} assessed runs. Completion and target attainment are separate.</p>` : '';
      $('preview').innerHTML = heading + `<div class="series-summary"><strong>${data.completed} / ${data.total}</strong><span>runs completed</span></div>${data.saved_status === 'running' ? '<p class="saved-state">The manifest says “running”. Live activity is checked separately above.</p>' : ''}${issues}<div class="attempt-heading"><strong>Attempts</strong><span>${data.children.length} saved</span></div><div class="attempt-list">${data.children.map(child => `<button class="attempt" data-id="${escape(child.id)}">${icon('file')}<span class="attempt-name">${escape(child.name)}<small>${escape(mode(child.mode))} · ${escape(child.profile)}</small></span>${badge(child)}${icon('arrow')}</button>`).join('') || '<p class="saved-state">No attempt files yet.</p>'}</div>${data.plot ? `<br>${plot(data)}` : ''}${folderBar(data)}`;
      $('preview').querySelector('.series-summary').insertAdjacentHTML('afterend', targetSummary);
    } else {
      const rate = data.rate == null ? '—' : data.profile === 'burst' ? `${data.low_rate ?? '—'} → ${data.rate} → ${data.low_rate ?? '—'}` : String(data.rate);
      const collection = data.collection_valid === true ? {tone:'good',status:'Valid collection'} : data.collection_valid === false ? {tone:'bad',status:'Invalid collection'} : {tone:'muted',status:'Collection not verified'};
      $('preview').innerHTML = heading + `<div class="metrics">${metric('Profile',data.profile ? data.profile[0].toUpperCase()+data.profile.slice(1) : '—',mode(data.mode),true)}${metric('Request rate',rate,'requests / 10 seconds',true)}${metric(`p95 · ${data.p95_scope.toLowerCase()}`,latency(data.p95_ms),data.target_ms == null ? 'Successful responses' : `Target ≤ ${data.target_ms / 1000} s`)}${metric('Successful',numeric(data.successful),'whole run')}${metric('Errors',numeric(data.failed),'includes timeouts')}${metric('Timeouts',numeric(data.timeouts),'whole run')}</div><div class="data-note">${badge(collection)}p95 uses successful responses only.<br>Unfinished: ${numeric(data.unfinished)} · Dropped starts: ${numeric(data.dropped)}${data.warnings.length ? ` · ${data.warnings.length} saved warning(s)` : ''}</div>${issues}${plot(data)}${folderBar(data)}`;
    }
    $('open-folder').onclick = async () => { try { await api('/api/open',{id}); notice(''); } catch(error) { notice(error.message); } };
    renderNotes(id, request);
    $('preview').querySelectorAll('[data-id]').forEach(button => button.onclick = () => select(button.dataset.id));
    revealSelected();
  } catch(error) { if (request === state.detailRequest) $('preview').innerHTML = `<div class="empty">${escape(error.message)}</div>`; }
}
async function refresh() {
  try {
    state.entries = await api('/api/results');
    const previous = $('series-path').value;
    const series = state.entries.filter(e => e.kind === 'series' && e.id.startsWith('main/'));
    $('series-path').innerHTML = series.length ? series.map(e => `<option value="${escape(e.id)}">${escape(e.name)} · ${e.completed}/${e.total} complete</option>`).join('') : '<option value="">No existing main series</option>';
    if (series.some(e => e.id === previous)) $('series-path').value = previous;
    renderList();
    if (state.selected && state.entries.some(e => e.id === state.selected)) await select(state.selected, state.parent === state.selected);
    else if (!state.selected) {
      let id;
      try { id = decodeURIComponent(location.hash.slice(1)); } catch { id = ''; }
      if (id === 'custom-metric' || state.group === 'Custom metrics') {
        showCustomFolder();
        $('connection').textContent = 'Local files connected';
        updateButtons();
        return;
      }
      const initial = state.entries.find(e => e.id === id) || series[0] || state.entries[0];
      if (initial) await select(initial.id);
      else $('preview').innerHTML = '<div class="empty">No saved results yet. Run a pilot to create the first result.</div>';
    }
    $('connection').textContent = 'Local files connected';
    updateButtons();
  } catch(error) { notice(error.message); $('connection').textContent = 'Cannot read results'; }
}
async function poll() {
  try {
    const status = await api('/api/status');
    const wasActive = state.status.job?.active;
    state.status = status;
    state.token = status.token;
    if (status.dry_only) { $('dry').checked = true; $('dry').disabled = true; }
    const job = status.job;
    const active = job?.active ? job : status.external;
    const display = active || job;
    $('activity-bar').hidden = !display && !status.scan_error;
    const phase = display?.phase.replaceAll('_',' ');
    $('phase').textContent = phase ? phase[0].toUpperCase()+phase.slice(1) : 'Process check unavailable';
    $('run-number').textContent = display ? `${active === status.external && active ? 'External · ' : job?.dry_run ? 'Dry run · ' : 'Run '}${display.run}` : status.scan_error;
    $('output').hidden = !job;
    $('command-output').textContent = job ? `${job.command}\n\n${job.lines.join('\n')}${job.exit_code != null ? `\nExit code: ${job.exit_code}\nLog: ${job.log}` : ''}` : '';
    $('view-active').hidden = !display?.result;
    $('view-active').onclick = async () => { if (display?.result) { showPage('results'); await refresh(); select(display.result); } };
    updateButtons();
    revealSelected();
    if (wasActive && !job?.active) await refresh();
  } catch(error) { state.token = ''; notice(`Connection lost: ${error.message}`); updateButtons(); }
}
function updateButtons() {
  const series = state.entries.find(e => e.id === $('series-path').value);
  $('pending').textContent = series ? `${Math.max(0,series.total-series.completed)} pending · ${series.completed}/${series.total} saved` : 'No existing series';
  const blocked = state.launching || state.status.job?.active || (!$('dry').checked && (state.status.external || state.status.scan_error));
  $('pilot').disabled = $('start-pilot').disabled = !!blocked || !state.token || !state.pilot;
  const complete = series && series.completed >= series.total;
  $('series').disabled = !series || (!complete && (!!blocked || !state.token));
  $('series').textContent = complete ? 'View results' : 'Resume main v1.1';
  $('pilot').title = $('series').title = blocked ? 'Wait for the active experiment, or use dry run.' : '';
  $('pilot-dry').checked = $('dry').checked;
  $('pilot-dry').disabled = $('dry').disabled;
  $('start-pilot').querySelector('span').textContent = $('dry').checked ? 'Check pilot' : 'Run pilot';
}
async function launch(kind) {
  const isPilot = kind === 'pilot';
  try {
    notice('');
    $('pilot-error').hidden = true;
    const activity = isPilot ? $('pilot-activity') : $('activity');
    if (!$('dry').checked && !activity.value.trim()) {
      if (!isPilot) $('settings').open = true;
      activity.focus();
      throw new Error('Describe current host activity before starting a live run.');
    }
    const pilot = isPilot ? pilotValues() : undefined;
    state.launching = true;
    updateButtons();
    await api('/api/launch',{kind,dry_run:$('dry').checked,series:$('series-path').value,activity:activity.value.trim() || 'Dry run; no load',pilot});
    if (isPilot) {
      state.pilot = pilot;
      $('pilot-preset').textContent = pilotDescription(pilot);
      $('pilot-dialog').close();
    }
    $('settings').open = false;
    $('output').open = true;
    await poll();
  } catch(error) {
    if (isPilot) { $('pilot-error').textContent = error.message; $('pilot-error').hidden = false; }
    else notice(error.message);
  } finally { state.launching = false; updateButtons(); }
}
function pilotValues() {
  const value = {mode:$('pilot-mode').value, profile:$('pilot-profile').value, rate:Number($('pilot-rate').value), low_rate:Number($('pilot-low-rate').value), slo_ms:Number($('pilot-target').value)};
  if (value.profile === 'steady') value.duration_seconds = Number($('pilot-duration').value);
  return value;
}
function pilotDescription(value) {
  const burst = value.profile === 'burst';
  const rate = burst ? `${value.low_rate} → ${value.rate} → ${value.low_rate}` : value.rate;
  return `${burst ? 'Burst' : 'Steady'} · ${mode(value.mode)} · ${rate} req / 10 s · ${burst ? state.burstSeconds : value.duration_seconds} s`;
}
function updatePilotForm() {
  const hpa = $('pilot-mode').value === 'autoscaling';
  $('pilot-profile').querySelector('[value=steady]').disabled = hpa;
  if (hpa) $('pilot-profile').value = 'burst';
  const burst = $('pilot-profile').value === 'burst';
  $('low-rate-field').hidden = $('pilot-low-rate').disabled = !burst;
  $('duration-field').hidden = $('pilot-duration').disabled = burst;
  $('burst-note').hidden = !burst;
  $('burst-note').textContent = `Burst duration is ${state.burstSeconds} seconds, from the saved workload stages. HPA uses this profile with preparation gates.`;
  $('rate-label').textContent = burst ? 'Peak rate' : 'Request rate';
  $('pilot-rate').setCustomValidity(burst && Number($('pilot-rate').value) < Number($('pilot-low-rate').value) ? 'Peak rate must be at least the low rate.' : '');
  const value = pilotValues();
  $('pilot-summary').textContent = `${pilotDescription(value)} · 1 repeat · p95 target ${value.slo_ms / 1000} s`;
}
async function loadPilotSettings() {
  try {
    const config = await api('/api/pilot-settings');
    state.pilot = config.defaults;
    state.burstSeconds = config.burst_seconds;
    $('pilot-preset').textContent = pilotDescription(state.pilot);
    updateButtons();
  } catch(error) { notice(`Cannot load pilot settings: ${error.message}`); }
}
function openPilot() {
  for (const [field, id] of Object.entries({mode:'pilot-mode',profile:'pilot-profile',rate:'pilot-rate',low_rate:'pilot-low-rate',duration_seconds:'pilot-duration',slo_ms:'pilot-target'})) {
    $(id).value = state.pilot[field] ?? (field === 'duration_seconds' ? 120 : '');
  }
  $('pilot-error').hidden = true;
  updatePilotForm();
  updateButtons();
  $('pilot-dialog').showModal();
}
$('groups').onclick = (event) => {
  const button = event.target.closest('[data-group]');
  if (!button) return;
  state.group = button.dataset.group; state.parent = null; renderList();
  if (state.group === 'Custom metrics') { showCustomFolder(); return; }
  const first = state.entries.find(e => e.group === state.group && !e.parent);
  if (first) select(first.id);
  else { state.selected = null; ++state.detailRequest; $('preview').innerHTML = '<div class="empty">No saved results in this group yet.</div>'; }
};
$('entries').onclick = (event) => { const button = event.target.closest('[data-id]'); if (button) select(button.dataset.id); };
$('entries').onkeydown = (event) => {
  const buttons = [...$('entries').querySelectorAll('button')], index = buttons.indexOf(document.activeElement);
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); buttons[Math.max(0,Math.min(buttons.length-1,index+(event.key === 'ArrowDown' ? 1 : -1)))]?.focus(); }
  if (event.key === 'ArrowLeft' && state.parent) { event.preventDefault(); $('back').click(); }
};
$('back').onclick = () => select(state.parent);
$('refresh').onclick = () => { notice(''); refresh(); poll(); };
$('dry').onchange = updateButtons;
$('series-path').onchange = updateButtons;
$('pilot').onclick = openPilot;
$('pilot-form').onsubmit = event => { event.preventDefault(); if (!state.launching) launch('pilot'); };
$('pilot-form').oninput = updatePilotForm;
$('pilot-mode').onchange = updatePilotForm;
$('pilot-profile').onchange = updatePilotForm;
$('close-pilot').onclick = $('cancel-pilot').onclick = () => $('pilot-dialog').close();
$('pilot-dry').onchange = () => { $('dry').checked = $('pilot-dry').checked; updateButtons(); };
$('runs-tab').onclick = () => showPage('runs');
$('results-tab').onclick = () => showPage('results');
$('series').onclick = () => {
  const series = state.entries.find(e => e.id === $('series-path').value);
  if (series && series.completed >= series.total) { showPage('results'); select(series.id); }
  else launch('series');
};
window.onhashchange = () => {
  try {
    const id = decodeURIComponent(location.hash.slice(1));
    showPage(!id || id === 'runs' ? 'runs' : 'results', false);
    if (id !== state.selected) select(id);
  }
  catch { notice('Invalid result link'); }
};
window.onresize = revealSelected;
showPage(state.page, false);
updateButtons();
loadPilotSettings();
refresh();
poll();
setInterval(poll, 3000);
