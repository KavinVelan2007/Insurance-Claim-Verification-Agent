import React, { useEffect, useRef, useState } from 'react';
import { animate, stagger } from 'animejs';
import { apiParse, apiVerify, apiAudits, apiHealth } from './api.js';
import FindingCard, { SEV_LABEL, SEV_ORDER, inr } from './FindingCard.jsx';

const MAX_MB = 15;
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const kb = b => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

const DOC_LABEL = { policy: 'Policy', invoice: 'Hospital invoice', discharge_summary: 'Discharge summary', prescription: 'Prescription', diagnostic_report: 'Diagnostic report', claim_form: 'Claim form', other: 'Other' };
const STATUS = {
  consistent: { label: 'Consistent', hint: 'No blocking issues found. A reviewer still signs off.' },
  needs_review: { label: 'Needs review', hint: 'Warnings or policy questions need a reviewer’s judgement.' },
  incomplete: { label: 'Incomplete', hint: 'Action required before this claim can proceed.' },
};
const STEPS = [
  ['Extract', 'PDF text, or local vision OCR for scanned pages'],
  ['Structure', 'Local LLM turns each document into validated JSON'],
  ['Verify', 'Deterministic rules: totals, duplicates, dates, coverage, missing docs'],
  ['Review', 'You confirm or dismiss each finding — Kaagaz never auto-decides'],
];

function PaperHero({ busy }) {
  const canvas = useRef(null);
  const scene = useRef(null);
  useEffect(() => {
    let dead = false;
    import('./paperScene.js')
      .then(m => { if (!dead) scene.current = m.createPaperScene(canvas.current); })
      .catch(() => { if (canvas.current) canvas.current.style.display = 'none'; }); // no WebGL: plain hero
    return () => { dead = true; scene.current?.dispose(); };
  }, []);
  useEffect(() => { scene.current?.setBusy(busy); }, [busy]);
  return <canvas ref={canvas} className="hero-canvas" aria-hidden="true" />;
}

function Count({ value }) {
  const ref = useRef(null);
  useEffect(() => {
    if (reducedMotion()) { ref.current.textContent = value; return; }
    const o = { n: 0 };
    const a = animate(o, { n: value, duration: 900, ease: 'outExpo', onUpdate: () => { if (ref.current) ref.current.textContent = Math.round(o.n); } });
    return () => a.pause();
  }, [value]);
  return <span ref={ref}>0</span>;
}

function useStaggerIn(selector, deps) {
  const ref = useRef(null);
  useEffect(() => {
    const els = ref.current?.querySelectorAll(selector);
    if (!els?.length || reducedMotion()) return;
    const a = animate(els, { opacity: [0, 1], translateY: [14, 0], delay: stagger(55), duration: 520, ease: 'outCubic' });
    return () => a.pause();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return ref;
}

function Health({ health }) {
  if (!health) return <div className="chips"><span className="chip"><i className="dot wait" />Connecting…</span></div>;
  if (health.status !== 'ok') return <div className="chips"><span className="chip bad"><i className="dot off" />API offline</span></div>;
  const dbUp = String(health.db || '').includes(':up');
  return (
    <div className="chips">
      <span className="chip" title="Text model used for extraction"><i className="dot on" />LLM · {health.llm}</span>
      <span className="chip" title="Vision model for scanned pages">
        <i className={`dot ${health.vlm && health.vlm !== 'none' ? 'on' : 'idle'}`} />OCR · {health.vlm && health.vlm !== 'none' ? health.vlm : 'text PDFs only'}
      </span>
      <span className={`chip ${dbUp ? '' : 'bad'}`} title={health.db}><i className={`dot ${dbUp ? 'on' : 'off'}`} />Audit DB · {dbUp ? 'connected' : 'offline'}</span>
    </div>
  );
}

function Dropzone({ files, setFiles, disabled, onReject }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);
  const listRef = useStaggerIn('.file', [files.length]);
  function add(list) {
    const bad = [];
    const next = [...files];
    for (const f of list) {
      if (!/\.pdf$/i.test(f.name)) bad.push(`${f.name}: not a PDF`);
      else if (f.size > MAX_MB * 1048576) bad.push(`${f.name}: over ${MAX_MB} MB`);
      else if (!next.some(x => x.name === f.name && x.size === f.size)) next.push(f);
    }
    setFiles(next);
    onReject(bad.join(' · '));
  }
  return (
    <>
      <div
        className={`drop ${over ? 'over' : ''} ${disabled ? 'disabled' : ''}`}
        role="button" tabIndex={0}
        onClick={() => !disabled && input.current.click()}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && !disabled && input.current.click()}
        onDragOver={e => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); if (!disabled) add(e.dataTransfer.files); }}
      >
        <img src="/kaagaz-mark.png" alt="" className="drop-mark" />
        <div><b>Drop claim PDFs here</b> or <span className="link">browse</span></div>
        <div className="mut small">Policy · invoices · discharge summary · prescription · reports · claim form (PDF, ≤ {MAX_MB} MB each)</div>
        <input ref={input} type="file" multiple accept="application/pdf,.pdf" hidden
          onChange={e => { add(e.target.files); e.target.value = ''; }} />
      </div>
      {files.length > 0 && (
        <ul className="files" ref={listRef}>
          {files.map((f, i) => (
            <li key={f.name + f.size} className="file">
              <span className="file-ic">PDF</span>
              <span className="file-name" title={f.name}>{f.name}</span>
              <span className="mut small">{kb(f.size)}</span>
              <button className="icon-btn" disabled={disabled} aria-label={`Remove ${f.name}`}
                onClick={() => setFiles(files.filter((_, j) => j !== i))}>×</button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Processing({ count, mode }) {
  const [s, setS] = useState(0);
  useEffect(() => { const t = setInterval(() => setS(x => x + 1), 1000); return () => clearInterval(t); }, []);
  return (
    <div className="card processing">
      <div className="scan"><div className="scan-page" /><div className="scan-page" /><div className="scan-page" /><div className="scan-line" /></div>
      <h3>{mode === 'parse' ? 'Reading' : 'Verifying'} {count} document{count > 1 ? 's' : ''}…</h3>
      <p className="mut">Running locally. LLM extraction can take up to a minute per document. <span className="mono">{Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}</span></p>
    </div>
  );
}

function EmptyState() {
  const ref = useStaggerIn('.step', []);
  return (
    <div className="card empty" ref={ref}>
      <h3>How Kaagaz checks a claim</h3>
      <ol className="steps">
        {STEPS.map(([t, d], i) => <li key={t} className="step"><span className="step-n">{i + 1}</span><div><b>{t}</b><div className="mut small">{d}</div></div></li>)}
      </ol>
      <p className="mut small">Add the claim’s PDFs on the left, then <b>Verify claim</b> for the full report or <b>Extract only</b> to inspect the structured data.</p>
    </div>
  );
}

function DocumentCard({ d }) {
  const money = new Set(['coverage_limit', 'deductible', 'total_amount']);
  const fields = [
    ['Patient', 'patient_name'], ['Hospital', 'hospital_name'], ['Claim ID', 'claim_id'], ['Policy no.', 'policy_number'],
    ['Invoice no.', 'invoice_number'], ['Invoice date', 'invoice_date'], ['Admission', 'admission_date'], ['Discharge', 'discharge_date'],
    ['Diagnosis', 'diagnosis'], ['Valid from', 'policy_valid_from'], ['Valid to', 'policy_valid_to'],
    ['Coverage limit', 'coverage_limit'], ['Deductible', 'deductible'], ['Stated total', 'total_amount'],
  ].filter(([, k]) => d[k] != null && d[k] !== '' && !(k === 'deductible' && !d[k]));
  const lists = [['Required documents', d.required_documents], ['Exclusions', d.exclusions], ['Policy clauses', d.policy_clauses]].filter(([, v]) => v?.length);
  const pct = Math.round(d.confidence * 100);
  return (
    <article className="doc">
      <header className="doc-head">
        <span className={`doc-type t-${d.document_type}`}>{DOC_LABEL[d.document_type] || d.document_type}</span>
        <span className="doc-file" title={d.filename}>{d.filename}</span>
      </header>
      <div className="conf" title={`Extraction confidence ${pct}%`}>
        <div className="conf-bar"><i style={{ width: `${pct}%` }} className={pct < 60 ? 'low' : ''} /></div>
        <span className="mut small">{pct}% · {d.extraction_method}</span>
      </div>
      {fields.length > 0 && (
        <dl className="kv">{fields.map(([l, k]) => <React.Fragment key={k}><dt>{l}</dt><dd>{money.has(k) ? inr(d[k]) : d[k]}</dd></React.Fragment>)}</dl>
      )}
      {d.itemized_charges?.length > 0 && (
        <table className="charges">
          <tbody>{d.itemized_charges.map((c, i) => <tr key={i}><td>{c.description}</td><td className="num">{inr(c.amount)}</td></tr>)}</tbody>
        </table>
      )}
      {lists.map(([l, v]) => (
        <details key={l} className="more"><summary>{l} ({v.length})</summary><ul>{v.map((x, i) => <li key={i}>{x}</li>)}</ul></details>
      ))}
      {d.warnings?.length > 0 && <div className="doc-warn">{d.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}</div>}
      <details className="more"><summary>Raw JSON</summary><pre className="json">{JSON.stringify(d, null, 2)}</pre></details>
    </article>
  );
}

function Documents({ docs }) {
  const ref = useStaggerIn('.doc', [docs]);
  return <div className="docs" ref={ref}>{docs.map((d, i) => <DocumentCard key={i} d={d} />)}</div>;
}

function Report({ report }) {
  const [filter, setFilter] = useState('all');
  const [reviewer, setReviewer] = useState(() => { try { return localStorage.getItem('kaagaz.reviewer') || ''; } catch { return ''; } });
  useEffect(() => { try { localStorage.setItem('kaagaz.reviewer', reviewer); } catch { /* storage blocked */ } }, [reviewer]);
  const sorted = [...report.findings].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  const counts = Object.fromEntries(SEV_ORDER.map(s => [s, report.findings.filter(f => f.severity === s).length]));
  const shown = filter === 'all' ? sorted : sorted.filter(f => f.severity === filter);
  const listRef = useStaggerIn('.finding', [report, filter]);
  const st = STATUS[report.status] || STATUS.needs_review;
  const totals = Object.entries(report.totals_recalculated || {}).filter(([, t]) => t.recalculated != null || t.stated != null);
  return (
    <>
      <section className={`card summary s-${report.status}`}>
        <div className="summary-top">
          <div>
            <div className="eyebrow">Claim</div>
            <div className="claim-id mono">{report.claim_id}</div>
          </div>
          <div className="status-badge"><i />{st.label}</div>
        </div>
        <p className="mut">{st.hint}</p>
        <div className="stats">
          {SEV_ORDER.map(s => <div key={s} className={`stat sv-${s}`}><b><Count value={counts[s]} /></b><span>{SEV_LABEL[s]}</span></div>)}
          <div className="stat"><b><Count value={report.documents.length} /></b><span>Documents</span></div>
        </div>
        <div className="summary-foot">
          {report.audit_id
            ? <span className="chip"><i className="dot on" />Saved to audit trail · #{report.audit_id}</span>
            : <span className="chip bad"><i className="dot off" />Not saved — audit database unavailable, reviews disabled</span>}
          {report.audit_id && (
            <label className="reviewer">Reviewing as
              <input type="text" value={reviewer} onChange={e => setReviewer(e.target.value)} placeholder="Your name" maxLength={80} />
            </label>
          )}
        </div>
      </section>

      {totals.length > 0 && (
        <section className="card">
          <h2>Bill check</h2>
          <div className="table-scroll"><table className="table">
            <thead><tr><th>Document</th><th className="num">Stated</th><th className="num">Recalculated</th><th className="num">Difference</th></tr></thead>
            <tbody>{totals.map(([file, t]) => {
              const diff = t.stated != null && t.recalculated != null ? t.stated - t.recalculated : null;
              return (
                <tr key={file}>
                  <td className="ellipsis" title={file}>{file}</td>
                  <td className="num">{inr(t.stated)}</td>
                  <td className="num">{inr(t.recalculated)}</td>
                  <td className={`num ${diff && Math.abs(diff) > 1 ? 'neg' : diff != null ? 'pos' : ''}`}>{diff == null ? '—' : Math.abs(diff) > 1 ? inr(diff) : 'Matches'}</td>
                </tr>
              );
            })}</tbody>
          </table></div>
        </section>
      )}

      <section className="card">
        <div className="section-head">
          <h2>Findings</h2>
          <div className="tabs" role="tablist">
            {['all', ...SEV_ORDER].filter(s => s === 'all' || counts[s]).map(s => (
              <button key={s} role="tab" aria-selected={filter === s} className={`tab ${filter === s ? 'on' : ''}`} onClick={() => setFilter(s)}>
                {s === 'all' ? 'All' : SEV_LABEL[s]} <span>{s === 'all' ? report.findings.length : counts[s]}</span>
              </button>
            ))}
          </div>
        </div>
        <div ref={listRef}>{shown.map(f => <FindingCard key={f.code} f={f} auditId={report.audit_id} reviewer={reviewer} />)}</div>
      </section>

      <section className="card">
        <h2>Extracted documents</h2>
        <Documents docs={report.documents} />
      </section>
    </>
  );
}

function AuditTrail({ audits, error, onRefresh }) {
  return (
    <section className="card">
      <div className="section-head">
        <h2>Audit trail</h2>
        <button className="ghost sm" onClick={onRefresh}>Refresh</button>
      </div>
      {error ? <div className="mut small">{error}</div>
        : !audits.length ? <div className="mut small">No verifications recorded yet.</div>
          : (
            <div className="audit-scroll">
              <table className="table">
                <thead><tr><th>#</th><th>Claim</th><th>Status</th><th>When</th></tr></thead>
                <tbody>{audits.map(a => (
                  <tr key={a.id}>
                    <td className="mono">{a.id}</td>
                    <td className="mono ellipsis" title={a.claim_id}>{a.claim_id}</td>
                    <td><span className={`mini s-${a.status}`}>{STATUS[a.status]?.label || a.status}</span></td>
                    <td className="mut small">{a.ts ? new Date(a.ts * 1000).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
    </section>
  );
}

export default function App() {
  const [files, setFiles] = useState([]);
  const [claimId, setClaimId] = useState('');
  const [busy, setBusy] = useState(null); // null | 'parse' | 'verify'
  const [error, setError] = useState('');     // run failures
  const [fileErr, setFileErr] = useState(''); // rejected uploads
  const [parsed, setParsed] = useState(null);
  const [report, setReport] = useState(null);
  const [health, setHealth] = useState(null);
  const [audits, setAudits] = useState([]);
  const [auditErr, setAuditErr] = useState('');
  const resultRef = useRef(null);

  const loadAudits = () => apiAudits().then(a => { setAudits(a); setAuditErr(''); }).catch(e => setAuditErr(e.message));
  useEffect(() => {
    apiHealth().then(setHealth).catch(() => setHealth({ status: 'offline' }));
    loadAudits();
  }, []);

  async function run(mode) {
    if (!files.length) return;
    setError(''); setFileErr(''); setBusy(mode); setParsed(null); setReport(null);
    if (window.innerWidth < 980) resultRef.current?.scrollIntoView({ behavior: 'smooth' });
    try {
      if (mode === 'parse') setParsed(await apiParse(files));
      else { setReport(await apiVerify(files, claimId.trim())); loadAudits(); }
    } catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }

  return (
    <>
      <header className="nav">
        <div className="wrap nav-in">
          <a className="brand" href="/"><img src="/kaagaz-mark.png" alt="" /><span>kaagaz</span></a>
          <Health health={health} />
        </div>
      </header>

      <section className="hero">
        <PaperHero busy={!!busy} />
        <div className="wrap hero-in">
          <div className="eyebrow">Health-insurance claim verification</div>
          <h1>Every claim, checked<br />against its <em>paper trail</em>.</h1>
          <p>Kaagaz reads the policy, bills and medical records, recalculates every invoice and checks it against policy terms — then hands your reviewers an evidence-backed report. People make the decision.</p>
        </div>
      </section>

      <main className="wrap grid">
        <aside className="side">
          <section className="card">
            <h2>Claim documents</h2>
            <Dropzone files={files} setFiles={setFiles} disabled={!!busy} onReject={setFileErr} />
            <label className="field">Claim ID <span className="mut">(optional — read from documents if blank)</span>
              <input type="text" placeholder="e.g. CLM-2026-00481" value={claimId} onChange={e => setClaimId(e.target.value)} disabled={!!busy} />
            </label>
            <div className="actions">
              <button className="primary" disabled={!!busy || !files.length} onClick={() => run('verify')}>
                {busy === 'verify' ? <><span className="spin" />Verifying…</> : 'Verify claim'}
              </button>
              <button className="ghost" disabled={!!busy || !files.length} onClick={() => run('parse')}>
                {busy === 'parse' ? <><span className="spin dark" />Extracting…</> : 'Extract only'}
              </button>
            </div>
            {files.length > 0 && !busy && <button className="text-btn" onClick={() => { setFiles([]); setFileErr(''); }}>Clear all files</button>}
            {fileErr && <div className="err" role="alert">{fileErr}</div>}
          </section>
          <AuditTrail audits={audits} error={auditErr} onRefresh={loadAudits} />
        </aside>

        <div className="results" ref={resultRef}>
          {busy && <Processing count={files.length} mode={busy} />}
          {error && !busy && <div className="err big" role="alert"><b>Couldn’t complete the run.</b> {error}</div>}
          {!busy && !parsed && !report && <EmptyState />}
          {parsed && (
            <section className="card">
              <div className="section-head">
                <h2>Extracted documents</h2>
                <span className="mut small mono">{parsed.pipeline} · {parsed.model_used}</span>
              </div>
              <Documents docs={parsed.documents} />
            </section>
          )}
          {report && <Report report={report} />}
        </div>
      </main>

      <footer className="wrap foot">
        <img src="/kaagaz-mark.png" alt="" />
        <span>Kaagaz never approves, rejects or labels fraud. Findings are decision support; a human reviewer makes every call.</span>
      </footer>
    </>
  );
}
