import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import { fmtDate } from './ui.jsx';

const ACTIONS = {
  'auth.signup': 'created the workspace', 'auth.login': 'signed in', 'auth.password_changed': 'changed their password',
  'team.member_added': 'added a member', 'claim.created': 'uploaded a claim', 'claim.viewed': 'viewed a claim',
  'document.opened': 'opened a PDF', 'finding.reviewed': 'reviewed a finding', 'claim.retried': 'retried a claim',
  'claim.deleted': 'deleted a claim',
};

function Password() {
  const [f, setF] = useState({ current: '', new: '' });
  const [msg, setMsg] = useState(null);
  async function submit(e) {
    e.preventDefault();
    try { await api.changePassword(f); setF({ current: '', new: '' }); setMsg({ ok: true, t: 'Password changed.' }); }
    catch (x) { setMsg({ ok: false, t: x.message }); }
  }
  return (
    <form onSubmit={submit} className="inline-form">
      <label className="field">Current password<input type="password" required value={f.current} onChange={e => setF({ ...f, current: e.target.value })} autoComplete="current-password" /></label>
      <label className="field">New password<input type="password" required minLength={10} value={f.new} onChange={e => setF({ ...f, new: e.target.value })} autoComplete="new-password" /></label>
      <button className="ghost">Change password</button>
      {msg && <div className={msg.ok ? 'ok-msg' : 'err'}>{msg.t}</div>}
    </form>
  );
}

function Team({ admin }) {
  const [members, setMembers] = useState([]);
  const [f, setF] = useState({ name: '', email: '', password: '', role: 'reviewer' });
  const [msg, setMsg] = useState(null);
  useEffect(() => { api.team().then(setMembers).catch(() => {}); }, []);
  const set = k => e => setF({ ...f, [k]: e.target.value });
  async function add(e) {
    e.preventDefault();
    try {
      const m = await api.addMember(f);
      setMembers([...members, m]); setF({ name: '', email: '', password: '', role: 'reviewer' });
      setMsg({ ok: true, t: `${m.name} can now sign in with that email and password. Ask them to change it in Settings.` });
    } catch (x) { setMsg({ ok: false, t: x.message }); }
  }
  return (
    <>
      <div className="table-scroll"><table className="table">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Added</th></tr></thead>
        <tbody>{members.map(m => <tr key={m.id}><td>{m.name}</td><td>{m.email}</td><td><span className="mini">{m.role}</span></td><td className="small mut">{fmtDate(m.created_at)}</td></tr>)}</tbody>
      </table></div>
      {admin && (
        <form onSubmit={add} className="member-form">
          <h3>Add a member</h3>
          <div className="grid-4">
            <label className="field">Name<input type="text" required maxLength={120} value={f.name} onChange={set('name')} /></label>
            <label className="field">Email<input type="email" required value={f.email} onChange={set('email')} /></label>
            <label className="field">Temporary password<input type="text" required minLength={10} value={f.password} onChange={set('password')} autoComplete="off" /></label>
            <label className="field">Role
              <select value={f.role} onChange={set('role')}><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select>
            </label>
          </div>
          <button className="primary sm">Add member</button>
          {msg && <div className={msg.ok ? 'ok-msg' : 'err'}>{msg.t}</div>}
        </form>
      )}
    </>
  );
}

function System() {
  const [s, setS] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => { api.system().then(setS).catch(e => setErr(e.message)); }, []);
  if (err) return <div className="err">{err}</div>;
  if (!s) return <span className="spin dark" />;
  const row = (label, ok, value, fix) => (
    <tr><td>{label}</td><td><span className={`dot ${ok ? 'on' : 'off'}`} /> {value}</td><td className="small mut">{!ok && fix}</td></tr>
  );
  return (
    <div className="table-scroll"><table className="table">
      <tbody>
        {row('AI model', s.llm.configured, `${s.llm.model} via ${s.llm.provider}`, 'Set OPENROUTER_API_KEY in backend/.env.')}
        {row('Database', s.db, s.db ? 'Connected' : 'Offline', 'Check DATABASE_URL in backend/.env.')}
        {row('Background worker', s.worker, s.worker ? 'Running in API' : 'Separate process', 'Run: python -m app.worker')}
        <tr><td>PDF retention</td><td>{s.retention_days} days</td><td className="small mut">Reports and decisions are kept.</td></tr>
        <tr><td>Upload limits</td><td>{s.max_files} files · {s.max_upload_mb} MB each</td><td /></tr>
      </tbody>
    </table></div>
  );
}

function Activity() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.activity().then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return <span className="spin dark" />;
  return (
    <ul className="activity">
      {rows.map((a, i) => (
        <li key={i}>
          <span><b>{a.user_name || 'Someone'}</b> {ACTIONS[a.action] || a.action}
            {a.claim_id && <> — <a href={`#/app/claims/${a.claim_id}`}>claim #{a.claim_id}</a></>}
            {a.detail && <span className="mut"> ({a.detail})</span>}</span>
          <span className="small mut">{fmtDate(a.created_at)}</span>
        </li>
      ))}
      {!rows.length && <li className="mut">No activity yet.</li>}
    </ul>
  );
}

export default function Settings({ me }) {
  const admin = me.role === 'admin';
  return (
    <>
      <div className="page-bar"><div><h1 className="page-title">Settings</h1><p className="mut">{me.org_name}</p></div></div>
      <div className="settings-grid">
        <section className="card">
          <h2>Your account</h2>
          <dl className="kv"><dt>Name</dt><dd>{me.name}</dd><dt>Email</dt><dd>{me.email}</dd><dt>Role</dt><dd className="cap">{me.role}</dd></dl>
          <Password />
        </section>
        <section className="card">
          <h2>Verification engine</h2>
          <System />
        </section>
        <section className="card wide">
          <h2>Team</h2>
          <Team admin={admin} />
        </section>
        {admin && (
          <section className="card wide">
            <h2>Activity log</h2>
            <p className="mut small">Sign-ins, uploads, views, PDF downloads and review decisions in this workspace.</p>
            <Activity />
          </section>
        )}
      </div>
    </>
  );
}
