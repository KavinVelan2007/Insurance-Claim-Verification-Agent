import React, { useEffect, useRef } from 'react';
import { Logo, useStaggerIn } from './ui.jsx';

function PaperHero() {
  const canvas = useRef(null);
  useEffect(() => {
    let scene, dead = false;
    import('./paperScene.js')
      .then(m => { if (!dead) scene = m.createPaperScene(canvas.current); })
      .catch(() => { if (canvas.current) canvas.current.style.display = 'none'; }); // no WebGL: plain hero
    return () => { dead = true; scene?.dispose(); };
  }, []);
  return <canvas ref={canvas} className="hero-canvas" aria-hidden="true" />;
}

function SiteNav({ me }) {
  // Sections live on the home page; from other pages, go home first, then scroll once it renders.
  const toSection = id => {
    const scroll = () => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    if (document.getElementById(id)) return scroll();
    location.hash = '/';
    setTimeout(scroll, 100);
  };
  return (
    <header className="nav">
      <div className="wrap nav-in">
        <a href="#/" className="brand-link"><Logo /></a>
        <nav className="site-links">
          <button className="nav-link" onClick={() => toSection('how')}>How it works</button>
          <button className="nav-link" onClick={() => toSection('checks')}>What it checks</button>
          <a className="nav-link" href="#/security">Security</a>
          {me ? <a className="btn primary sm" href="#/app">Open workspace</a>
            : <><a className="nav-link" href="#/login">Sign in</a><a className="btn primary sm" href="#/signup">Get started</a></>}
        </nav>
      </div>
    </header>
  );
}

function SiteFooter() {
  return (
    <footer className="site-foot">
      <div className="wrap foot-in">
        <Logo size={24} />
        <span className="mut small">Kaagaz never approves, rejects or labels fraud. Findings are decision support; a person makes every call.</span>
        <nav><a href="#/security">Security</a><a href="#/login">Sign in</a></nav>
      </div>
    </footer>
  );
}

const STEPS = [
  ['Upload', 'Drop in the policy, hospital bills, discharge summary, prescriptions, reports and claim form as PDFs.'],
  ['Read', 'Digital PDFs are read from their text layer; scanned pages are read from their images. A vision AI model turns each document into structured fields.'],
  ['Check', 'Plain, deterministic rules recalculate bills and test the claim against the policy. The AI extracts — it never decides.'],
  ['Decide', 'Your reviewer sees every issue with its evidence and records confirm, dismiss or inconclusive. Each decision is logged.'],
];
const CHECKS = [
  ['Bill arithmetic', 'Recalculates every invoice from its line items and flags totals that don’t add up.'],
  ['Duplicate invoices', 'Catches the same invoice uploaded twice, or already submitted in an earlier claim.'],
  ['Missing documents', 'Compares uploads with the documents the policy requires.'],
  ['Policy period', 'Flags admission, discharge or invoice dates outside the policy’s validity.'],
  ['Coverage limit', 'Compares the claimed amount with the sum insured and notes any deductible.'],
  ['Exclusions', 'Flags treatments that match the policy’s exclusion list, with the clause quoted.'],
  ['Consistency', 'Spots different claim numbers or patient names across the documents.'],
  ['Read quality', 'Marks low-confidence or partially scanned documents for manual checking.'],
];

export function Landing({ me }) {
  const stepsRef = useStaggerIn('.lp-step', []);
  return (
    <>
      <SiteNav me={me} />
      <section className="hero">
        <PaperHero />
        <div className="wrap hero-in">
          <div className="eyebrow">Health-insurance claim verification</div>
          <h1>Every claim, checked<br />against its <em>paper trail</em>.</h1>
          <p>Kaagaz reads the policy, bills and medical records, recalculates every invoice and checks it against the policy — then hands your reviewers an evidence-backed report.</p>
          <div className="hero-cta">
            <a className="btn primary" href={me ? '#/app' : '#/signup'}>{me ? 'Open workspace' : 'Create a workspace'}</a>
            <button className="btn ghost" onClick={() => document.getElementById('how').scrollIntoView({ behavior: 'smooth' })}>See how it works</button>
          </div>
        </div>
      </section>

      <section className="lp-section" id="how">
        <div className="wrap">
          <div className="lp-head"><div className="eyebrow">How it works</div><h2>From a pile of PDFs to a reviewed claim</h2></div>
          <ol className="lp-steps" ref={stepsRef}>
            {STEPS.map(([t, d], i) => <li key={t} className="lp-step"><span className="step-n">{i + 1}</span><h3>{t}</h3><p>{d}</p></li>)}
          </ol>
        </div>
      </section>

      <section className="lp-section alt" id="checks">
        <div className="wrap lp-split">
          <div>
            <div className="eyebrow">What it checks</div>
            <h2>The checks your reviewers do by hand, done first</h2>
            <p className="lp-lead">Each check is ordinary code you can audit, so the same documents always give the same result.</p>
            <div className="lp-checks">
              {CHECKS.map(([t, d]) => <div key={t} className="lp-check"><b>{t}</b><span>{d}</span></div>)}
            </div>
          </div>
          <div className="lp-sample" aria-label="Example finding">
            <div className="finding sv-action_required">
              <div className="finding-head"><span className="pill p-action_required">Action required</span><h3>Invoice total does not match its line items</h3></div>
              <p className="finding-detail">invoice_B.pdf: 4 line items sum to 73,000.00, but the stated total is 78,000.00 (difference 5,000.00).</p>
              <div className="evidence">
                <div className="ev-vals"><div><span className="ev-l">Found</span><span className="mono">₹78,000.00</span></div><div><span className="ev-l">Expected</span><span className="mono">₹73,000.00</span></div></div>
                <div><span className="ev-l">Next step</span>Ask the hospital for a corrected invoice before settlement.</div>
              </div>
              <div className="review"><div className="seg"><span className="seg-btn on d-confirmed">Confirm</span><span className="seg-btn">Dismiss</span><span className="seg-btn">Inconclusive</span></div></div>
            </div>
            <p className="mut small center">Every finding carries its evidence, source document and suggested next step.</p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="wrap lp-trio">
          <div><h3>People decide</h3><p>Kaagaz never approves, rejects or labels a claim as fraud. It prepares the file; your reviewer makes the call and it’s recorded.</p></div>
          <div><h3>Explainable</h3><p>Every flag shows the values found, what was expected, the document it came from and the policy clause behind it.</p></div>
          <div><h3>Private by design</h3><p>Documents go only to AI providers that don’t collect your data. Stored PDFs are encrypted and deleted on a schedule. <a href="#/security">How we handle data →</a></p></div>
        </div>
      </section>

      <section className="lp-cta">
        <div className="wrap">
          <h2>Give your reviewers a head start on every claim.</h2>
          <a className="btn primary" href={me ? '#/app' : '#/signup'}>{me ? 'Open workspace' : 'Create a workspace'}</a>
        </div>
      </section>
      <SiteFooter />
    </>
  );
}

const SECURITY = [
  ['Privacy-filtered AI', 'Documents are read by an AI model through OpenRouter, routed only to providers that do not collect or train on your data. Kaagaz can instead point at a model server you host, so documents never leave your infrastructure.'],
  ['Encrypted storage', 'Uploaded PDFs are encrypted (Fernet: AES-128 with HMAC) before they are written to the database. Connections to the database use TLS.'],
  ['Separate workspaces', 'Each organisation’s claims, documents and reviews are isolated, and every query is scoped to the signed-in user’s organisation. Database tables are closed to direct public API access.'],
  ['Roles and sessions', 'Admins manage the team and can delete claims; reviewers verify and review. Sessions use secure, http-only cookies that expire automatically.'],
  ['Audit trail', 'Sign-ins, uploads, claim views, PDF downloads, review decisions and deletions are logged with who did them and when.'],
  ['Retention', 'Original PDFs are deleted automatically after a set number of days (90 by default). The verification report and decisions are kept for audit.'],
  ['Abuse protection', 'Sign-in, sign-up, uploads and AI explanations are rate-limited; uploads are checked for type and size before processing.'],
];

export function Security({ me }) {
  const ref = useStaggerIn('.sec-item', []);
  return (
    <>
      <SiteNav me={me} />
      <section className="lp-section page-head">
        <div className="wrap narrow">
          <div className="eyebrow">Security &amp; data handling</div>
          <h1 className="page-title">Health records deserve careful handling</h1>
          <p className="lp-lead">Here is exactly what Kaagaz does with the documents you upload.</p>
          <div className="sec-list" ref={ref}>
            {SECURITY.map(([t, d]) => <div key={t} className="sec-item"><h3>{t}</h3><p>{d}</p></div>)}
          </div>
        </div>
      </section>
      <SiteFooter />
    </>
  );
}
