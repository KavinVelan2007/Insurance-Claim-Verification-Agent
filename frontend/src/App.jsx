import React, { useEffect, useState } from 'react';
import { api, setUnauthorizedHandler } from './api.js';
import { Logo, go, useRoute } from './ui.jsx';
import { Landing, Security } from './Landing.jsx';
import Auth from './Auth.jsx';
import { ClaimList, NewClaim } from './Claims.jsx';
import ClaimView from './ClaimView.jsx';
import Settings from './Settings.jsx';

function AppShell({ me, route, onLogout, children }) {
  const [open, setOpen] = useState(false);
  const link = (path, label, active) => (
    <a href={`#${path}`} className={`nav-link ${active ? 'on' : ''}`} onClick={() => setOpen(false)}>{label}</a>
  );
  return (
    <>
      <header className="nav">
        <div className="wrap nav-in">
          <a href="#/app" className="brand-link"><Logo /></a>
          <button className="icon-btn menu-btn" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
          <nav className={`nav-links ${open ? 'open' : ''}`}>
            {link('/app', 'Claims', route === '/app' || route.startsWith('/app/claims'))}
            {link('/app/new', 'New claim', route === '/app/new')}
            {link('/app/settings', 'Settings', route === '/app/settings')}
            <span className="nav-user" title={me.email}>{me.name} · <span className="mut">{me.org_name}</span></span>
            <button className="ghost sm" onClick={onLogout}>Sign out</button>
          </nav>
        </div>
      </header>
      <main className="wrap page">{children}</main>
    </>
  );
}

export default function App() {
  const route = useRoute();
  const [me, setMe] = useState(undefined); // undefined = checking session

  useEffect(() => {
    setUnauthorizedHandler(() => { setMe(null); go('/login'); });
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  async function logout() {
    await api.logout().catch(() => {});
    setMe(null);
    go('/');
  }

  const inApp = route.startsWith('/app');
  useEffect(() => {
    if (me === null && inApp) go('/login');
    if (me && (route === '/login' || route === '/signup')) go('/app');
  }, [me, route, inApp]);

  if (route === '/login' || route === '/signup') return <Auth mode={route.slice(1)} onAuthed={u => { setMe(u); go('/app'); }} />;
  if (route === '/security') return <Security me={me} />;
  if (!inApp) return <Landing me={me} />;
  if (!me) return <div className="boot"><Logo size={40} /></div>;

  const claim = route.match(/^\/app\/claims\/(\d+)$/);
  return (
    <AppShell me={me} route={route} onLogout={logout}>
      {claim ? <ClaimView id={claim[1]} me={me} key={claim[1]} />
        : route === '/app/new' ? <NewClaim />
          : route === '/app/settings' ? <Settings me={me} />
            : <ClaimList />}
    </AppShell>
  );
}
