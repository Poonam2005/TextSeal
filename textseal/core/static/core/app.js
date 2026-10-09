const sample = `Artificial intelligence is a tool, not a substitute for human judgment.\n\nThis short research note was prepared for a classroom demonstration of text provenance.`;
const csrf = document.querySelector('#csrf-token input')?.value || '';

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function provenanceHtml(provenance) {
  if (!provenance) return '';
  const items = [
    ['Text ID', provenance.text_id], ['SHA-256', provenance.content_hash], ['Ledger ref', provenance.blockchain_reference],
    ['Model', provenance.model_info], ['Ledger', provenance.ledger_status ? `Verified / block ${provenance.block_number}` : 'Unavailable or inconsistent'], ['Created', new Date(provenance.created_at).toLocaleString()], ['Length', `${provenance.canonical_length} chars`],
  ];
  return `<div class="provenance">${items.map(([name, value]) => `<div><span>${escapeHtml(name)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`).join('')}</div>`;
}

function resultClass(result) {
  if (result === 'authentic' || result === 'registered') return 'success';
  if (result === 'modified' || result === 'not_registered') return 'warning';
  return 'danger';
}

function renderResult(container, data, registration = false) {
  container.hidden = false;
  const tone = resultClass(data.result || data.status);
  const icon = tone === 'success' ? '✓' : tone === 'warning' ? '!' : '×';
  const label = registration ? 'Text sealed & registered' : (data.label || 'Verification result');
  const textOutput = registration ? `<textarea readonly aria-label="Watermarked output">${escapeHtml(data.watermarked_text)}</textarea><div class="result-actions"><span class="limit">Invisible characters are preserved in this field.</span><button class="copy-button" type="button" data-copy>Copy sealed text</button></div>` : '';
  container.className = `result ${tone}`;
  const receiptActions = registration && data.receipt_url ? `<div class="receipt-actions"><a class="copy-button" href="${escapeHtml(data.receipt_url)}" target="_blank" rel="noopener">Open verification receipt</a><button class="copy-button" type="button" data-copy-receipt="${escapeHtml(data.receipt_url)}">Copy receipt link</button><button class="quiet-button" type="button" data-evaluate>Run robustness test</button></div>` : '';
  container.innerHTML = `<div class="result-header"><div><p class="result-kicker">${registration ? 'Registration complete' : 'Verification complete'}</p><h3>${escapeHtml(label)}</h3><p class="result-copy">${escapeHtml(data.message || data.detail || '')}</p></div><span class="status-dot">${icon}</span></div>${textOutput}${receiptActions}${provenanceHtml(data.provenance)}`;
  const button = container.querySelector('[data-copy]');
  if (button) button.addEventListener('click', async () => {
    const output = container.querySelector('textarea').value;
    await navigator.clipboard.writeText(output);
    button.textContent = 'Copied'; setTimeout(() => { button.textContent = 'Copy sealed text'; }, 1500);
  });
  const receiptButton = container.querySelector('[data-copy-receipt]');
  if (receiptButton) receiptButton.addEventListener('click', async () => {
    await navigator.clipboard.writeText(receiptButton.dataset.copyReceipt);
    receiptButton.textContent = 'Link copied';
  });
  const evaluationButton = container.querySelector('[data-evaluate]');
  if (evaluationButton) evaluationButton.addEventListener('click', () => {
    document.getElementById('evaluation-text').value = data.watermarked_text;
    document.getElementById('evaluation-tab').click();
  });
}

function renderError(container, message) {
  container.hidden = false; container.className = 'result danger';
  container.innerHTML = `<div class="result-header"><div><p class="result-kicker">Could not complete request</p><h3>Check the text</h3><p class="result-copy">${escapeHtml(message)}</p></div><span class="status-dot">×</span></div>`;
}

async function submitForm(event, endpoint, resultId, kind) {
  event.preventDefault();
  const form = event.currentTarget; const result = document.getElementById(resultId); const button = form.querySelector('[type="submit"]');
  const text = form.querySelector('textarea').value;
  const file = form.querySelector('input[type="file"]')?.files[0];
  if (!text.trim() && !file) { renderError(result, 'Enter text or upload a supported document file.'); return; }
  const body = new FormData(); body.append('text', text);
  if (kind === 'watermark') { body.append('model_info', document.getElementById('model-info').value); body.append('source_note', document.getElementById('source-note').value); }
  if (file) body.append('file', file);
  button.disabled = true; button.querySelector('span').textContent = kind === 'watermark' ? 'Sealing…' : 'Verifying…';
  try {
    const response = await fetch(endpoint, { method:'POST', headers:{'X-CSRFToken': csrf}, body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The service could not process this request.');
    renderResult(result, data, kind === 'watermark');
    if (kind === 'watermark') document.getElementById('verify-text').value = data.watermarked_text;
  } catch (error) { renderError(result, error.message); }
  finally { button.disabled = false; button.querySelector('span').textContent = kind === 'watermark' ? 'Seal text' : 'Verify text'; }
}

async function evaluateRobustness(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const result = document.getElementById('evaluation-result');
  button.disabled = true;
  button.querySelector('span').textContent = 'Evaluating…';
  try {
    const response = await fetch('/api/evaluate', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: document.getElementById('evaluation-text').value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The evaluation could not be completed.');
    result.hidden = false;
    result.className = `result ${data.passed === data.total ? 'success' : 'warning'}`;
    result.innerHTML = `<div class="result-header"><div><p class="result-kicker">Deterministic test summary</p><h3>${data.passed} of ${data.total} cases matched expectations</h3></div><span class="status-dot">${data.passed === data.total ? '✓' : '!'}</span></div><div class="evaluation-table"><div class="evaluation-row evaluation-heading"><span>Transformation</span><span>Expected</span><span>Observed</span><span>Check</span></div>${data.cases.map(item => `<div class="evaluation-row"><span>${escapeHtml(item.name)}</span><span>${escapeHtml(item.expected.replaceAll('_', ' '))}</span><span>${escapeHtml(item.actual.replaceAll('_', ' '))}</span><strong>${item.passed ? 'Pass' : 'Mismatch'}</strong></div>`).join('')}</div>`;
  } catch (error) { renderError(result, error.message); }
  finally { button.disabled = false; button.querySelector('span').textContent = 'Run evaluation'; }
}

function shortId(value) { return value ? `${value.slice(0, 8)}…${value.slice(-4)}` : 'No record'; }

function formatTime(value) { return new Date(value).toLocaleString(); }

async function loadHistory() {
  const container = document.getElementById('history-result');
  try {
    const response = await fetch('/api/history');
    const data = await response.json();
    if (!response.ok) throw new Error('Could not load the ledger activity.');
    const recordItems = data.records.length ? data.records.map(record => `<div class="history-item"><i class="history-dot"></i><div><strong title="${escapeHtml(record.text_id)}">${escapeHtml(shortId(record.text_id))}</strong><span>Block ${record.block_number ?? '—'} · ${escapeHtml(formatTime(record.created_at))}</span></div></div>`).join('') : '<div class="history-empty">No protected texts yet.</div>';
    const verificationItems = data.verifications.length ? data.verifications.map(item => `<div class="history-item"><i class="history-dot ${item.result === 'authentic' ? '' : 'warn'}"></i><div><strong>${escapeHtml(item.result.replaceAll('_', ' '))}</strong><span>${escapeHtml(shortId(item.text_id))} · ${escapeHtml(formatTime(item.created_at))}</span></div></div>`).join('') : '<div class="history-empty">No verification events yet.</div>';
    container.innerHTML = `<div class="history-summary"><div class="${data.ledger_integrity ? 'ledger-good' : 'ledger-bad'}"><span>Ledger integrity</span><strong>${data.ledger_integrity ? 'Verified' : 'Attention needed'}</strong></div><div><span>Protected texts</span><strong>${data.registered_count}</strong></div><div><span>Verification events</span><strong>${data.verification_count}</strong></div></div><div class="history-columns"><div class="history-column"><p class="history-heading">Recent registrations</p>${recordItems}</div><div class="history-column"><p class="history-heading">Recent verification activity</p>${verificationItems}</div></div>`;
  } catch (error) { container.innerHTML = `<div class="history-error">${escapeHtml(error.message)}</div>`; }
}

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(item => { item.classList.remove('active'); item.setAttribute('aria-selected', 'false'); });
  document.querySelectorAll('.panel').forEach(panel => { panel.classList.remove('active'); panel.hidden = true; });
  tab.classList.add('active'); tab.setAttribute('aria-selected', 'true'); const panel = document.getElementById(tab.dataset.tab); panel.hidden = false; panel.classList.add('active');
  if (tab.dataset.tab === 'history-panel') loadHistory();
}));
document.querySelectorAll('.sample-button').forEach(button => button.addEventListener('click', () => { document.getElementById(button.dataset.target).value = sample; }));
document.getElementById('watermark-form').addEventListener('submit', event => submitForm(event, '/api/watermark', 'watermark-result', 'watermark'));
document.getElementById('verify-form').addEventListener('submit', event => submitForm(event, '/api/verify', 'verify-result', 'verify'));
document.getElementById('evaluation-form').addEventListener('submit', evaluateRobustness);
document.getElementById('refresh-history').addEventListener('click', loadHistory);
