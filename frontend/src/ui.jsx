import React, { useEffect, useRef, useState } from 'react';
import { animate, stagger } from 'animejs';

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
export const inr = n => n == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n);
export const fmtDate = t => t ? new Date(t).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—';
export const kb = b => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

export function ago(t) {
  const s = Math.max(0, (Date.now() - new Date(t)) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return fmtDate(t);
}

// Hash routing: #/app/claims/12 -> "/app/claims/12". No router dependency needed.
export function useRoute() {
  const read = () => window.location.hash.slice(1) || '/';
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const f = () => { setRoute(read()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', f);
    return () => window.removeEventListener('hashchange', f);
  }, []);
  return route;
}
export const go = path => { window.location.hash = path; };

export const SEV_ORDER = ['action_required', 'policy_review', 'warning', 'info'];
export const SEV_LABEL = { action_required: 'Action required', policy_review: 'Policy review', warning: 'Warning', info: 'Verified' };
export const STATUS = {
  consistent: { label: 'Consistent', hint: 'No blocking issues found. A reviewer still signs off.' },
  needs_review: { label: 'Needs review', hint: 'Warnings or policy questions need a reviewer’s judgement.' },
  incomplete: { label: 'Incomplete', hint: 'Action is required before this claim can proceed.' },
};

export function StatusBadge({ claim }) {
  if (claim.state === 'queued' || claim.state === 'processing')
    return <span className="badge s-progress"><span className="spin dark xs" />{claim.state === 'queued' ? 'Queued' : 'Verifying'}</span>;
  if (claim.state === 'failed') return <span className="badge s-failed"><i />Failed</span>;
  return <span className={`badge s-${claim.status}`}><i />{STATUS[claim.status]?.label || claim.status}</span>;
}

export function Logo({ size = 30 }) {
  return <span className="logo"><img src="/kaagaz-mark.png" alt="" style={{ height: size }} /><span>kaagaz</span></span>;
}

export function Count({ value }) {
  const ref = useRef(null);
  useEffect(() => {
    if (reducedMotion()) { ref.current.textContent = value; return; }
    const o = { n: 0 };
    const a = animate(o, { n: value, duration: 900, ease: 'outExpo', onUpdate: () => { if (ref.current) ref.current.textContent = Math.round(o.n); } });
    return () => a.pause();
  }, [value]);
  return <span ref={ref}>0</span>;
}

export function useStaggerIn(selector, deps) {
  const ref = useRef(null);
  useEffect(() => {
    const els = ref.current?.querySelectorAll(selector);
    if (!els?.length || reducedMotion()) return;
    const a = animate(els, { opacity: [0, 1], translateY: [14, 0], delay: stagger(50), duration: 500, ease: 'outCubic' });
    return () => a.pause();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return ref;
}

// Re-runs fn every `ms` while `active`; stops when the tab is hidden.
export function usePoll(fn, ms, active) {
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => { if (!document.hidden) fn(); }, ms);
    return () => clearInterval(t);
  }, [active, ms]); // eslint-disable-line react-hooks/exhaustive-deps
}
