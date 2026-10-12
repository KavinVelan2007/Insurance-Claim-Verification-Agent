import React, { useState } from 'react';
import { api } from './api.js';
import { Logo } from './ui.jsx';

export default function Auth({ mode, onAuthed }) {
  const signup = mode === 'signup';
  const [f, setF] = useState({ org_name: '', name: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const set = k => e => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      onAuthed(signup ? await api.signup(f) : await api.login({ email: f.email, password: f.password }));
    } catch (x) { setErr(x.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="auth">
      <a href="#/" className="brand-link auth-logo"><Logo size={36} /></a>
      <form className="card auth-card" onSubmit={submit}>
        <h1>{signup ? 'Create your workspace' : 'Sign in'}</h1>
        <p className="mut">{signup ? 'You’ll be the admin and can add reviewers afterwards.' : 'Welcome back. Pick up where your team left off.'}</p>
        {signup && (
          <>
            <label className="field">Organisation<input type="text" required minLength={2} maxLength={120} value={f.org_name} onChange={set('org_name')} placeholder="e.g. Acme Health TPA" autoComplete="organization" /></label>
            <label className="field">Your name<input type="text" required maxLength={120} value={f.name} onChange={set('name')} autoComplete="name" /></label>
          </>
        )}
        <label className="field">Work email<input type="email" required maxLength={254} value={f.email} onChange={set('email')} autoComplete="email" /></label>
        <label className="field">Password
          <input type="password" required minLength={signup ? 10 : 1} maxLength={200} value={f.password} onChange={set('password')} autoComplete={signup ? 'new-password' : 'current-password'} />
          {signup && <span className="hint">At least 10 characters.</span>}
        </label>
        {err && <div className="err" role="alert">{err}</div>}
        <button className="primary block" disabled={busy}>{busy ? <span className="spin" /> : null}{signup ? 'Create workspace' : 'Sign in'}</button>
        <p className="mut small center">
          {signup ? <>Already have an account? <a href="#/login">Sign in</a></> : <>New to Kaagaz? <a href="#/signup">Create a workspace</a></>}
        </p>
        {!signup && <p className="mut small center">Reviewer accounts are created by your workspace admin.</p>}
      </form>
    </div>
  );
}
