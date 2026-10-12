const BASE = '';
async function req(path, opts = {}) {
  const r = await fetch(BASE + path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `Request failed (${r.status})`);
  return body;
}
export async function apiParse(files) {
  const fd = new FormData();
  [...files].forEach(f => fd.append('files', f));
  return req('/api/parse', { method: 'POST', body: fd });
}
export async function apiVerify(files, claimId = '') {
  const fd = new FormData();
  [...files].forEach(f => fd.append('files', f));
  const q = claimId ? `?claim_id=${encodeURIComponent(claimId)}` : '';
  return req('/api/verify' + q, { method: 'POST', body: fd });
}
export async function apiReview(payload) {
  return req('/api/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
}
export async function apiAudits() { return req('/api/audits'); }
export async function apiHealth() { return req('/api/health'); }
export async function apiExplain(clause, question) {
  return req('/api/explain', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ clause, question }) });
}
