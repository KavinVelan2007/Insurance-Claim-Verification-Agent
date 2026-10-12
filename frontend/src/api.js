// All calls go to the same origin (Vite proxies /api in dev); the session is an httpOnly cookie.
let onUnauthorized = () => {};
export const setUnauthorizedHandler = fn => { onUnauthorized = fn; };

async function req(path, opts = {}) {
  let r;
  try { r = await fetch(path, { credentials: 'same-origin', ...opts }); }
  catch { throw new Error('Cannot reach the Kaagaz server. Check that the backend is running.'); }
  const body = await r.json().catch(() => ({}));
  if (r.status === 401 && !path.startsWith('/api/auth') && path !== '/api/me') onUnauthorized();
  if (!r.ok) {
    // FastAPI validation errors (422) come back as a list of {loc, msg}.
    const d = Array.isArray(body.detail)
      ? body.detail.map(x => `${x.loc?.at(-1) ?? ''}: ${x.msg}`.replace(/^: /, '')).join('; ')
      : body.detail;
    throw new Error(d || `Request failed (${r.status})`);
  }
  return body;
}
const json = (method, path, body) => req(path, { method, headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });

export const api = {
  me: () => req('/api/me'),
  signup: b => json('POST', '/api/auth/signup', b),
  login: b => json('POST', '/api/auth/login', b),
  logout: () => json('POST', '/api/auth/logout'),
  changePassword: b => json('POST', '/api/me/password', b),
  team: () => req('/api/team'),
  addMember: b => json('POST', '/api/team', b),
  activity: () => req('/api/activity'),
  system: () => req('/api/system'),
  claims: (q = '', offset = 0) => req(`/api/claims?limit=25&offset=${offset}&q=${encodeURIComponent(q)}`),
  claim: id => req(`/api/claims/${id}`),
  createClaim(files, claimRef) {
    const fd = new FormData();
    files.forEach(f => fd.append('files', f));
    fd.append('claim_ref', claimRef);
    return req('/api/claims', { method: 'POST', body: fd });
  },
  retry: id => json('POST', `/api/claims/${id}/retry`),
  deleteClaim: id => json('DELETE', `/api/claims/${id}`),
  review: (fid, decision, comment) => json('POST', `/api/findings/${fid}/reviews`, { decision, comment }),
  explain: fid => json('POST', `/api/findings/${fid}/explain`),
  fileUrl: (cid, did) => `/api/claims/${cid}/documents/${did}/file`,
};
