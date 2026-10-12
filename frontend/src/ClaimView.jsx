import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import { Count, SEV_LABEL, SEV_ORDER, STATUS, StatusBadge, ago, fmtDate, go, inr, usePoll, useStaggerIn } from './ui.jsx';

const DOC_LABEL = { policy: 'Policy', invoice: 'Hospital invoice', discharge_summary: 'Discharge summary', prescription: 'Prescription', diagnostic_report: 'Diagnostic report', claim_form: 'Claim form', other: 'Other document' };
const DECISIONS = [['confirmed', 'Confirm'], ['dismissed', 'Dismiss'], ['inconclusive', 'Inconclusive']];
const DECIDED = { confirmed: 'Confirmed', dismissed: 'Dismissed', inconclusive: 'Inconclusive' };
// Only these checks carry money in found/expected (others hold invoice numbers, names or dates).
const isMoney = code => /^(TOTAL_|COVERAGE_)/.test(code);

function Elapsed({ from }) {
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick(x => x + 1), 1000); return () => clearInterval(t); }, []);
  const s = Math.max(0, Math.floor((Date.now() - new Date(from)) / 1000));
  return <span className="mono">{Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}</span>;
}

function FindingCard({ f, onReviewed }) {
  const latest = f.reviews[0];
  const [editing, setEditing] = useState(!latest && f.severity !== 'info');
  const [decision, setDecision] = useState('');
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [expl, setExpl] = useState('');
  const [explaining, setExplaining] = useState(false);
  const [history, setHistory] = useState(false);
  const val = v => isMoney(f.code) && !isNaN(Number(v)) ? inr(Number(v)) : v;
  const pct = Math.round(f.confidence * 100);

  async function save() {
    if (!decision) { setMsg('Choose a decision first.'); return; }
    setSaving(true); setMsg('');
    try { await api.review(f.id, decision, comment.trim()); setEditing(false); setDecision(''); setComment(''); await onReviewed(); }
    catch (e) { setMsg(e.message); }
    finally { setSaving(false); }
  }
  async function explain() {
    setExplaining(true);
    try { setExpl((await api.explain(f.id)).explanation); }
    catch (e) { setExpl('Explanation unavailable: ' + e.message); }
    finally { setExplaining(false); }
  }

  return (
    <article className={`finding sv-${f.severity}`}>
      <div className="finding-head">
        <span className={`pill p-${f.severity}`}>{SEV_LABEL[f.severity]}</span>
        <h3>{f.title}</h3>
        {latest && <span className={`decided d-${latest.decision}`}>{DECIDED[latest.decision]}</span>}
      </div>
      <p className="finding-detail">{f.detail}</p>

      {(f.extracted_value || f.document_ref || f.policy_clause || f.action) && (
        <div className="evidence">
          {f.extracted_value && (
            <div className="ev-vals">
              <div><span className="ev-l">Found</span><span className="mono">{val(f.extracted_value)}</span></div>
              {f.expected_value && <div><span className="ev-l">Expected</span><span className="mono">{val(f.expected_value)}</span></div>}
            </div>
          )}
          {f.document_ref && <div><span className="ev-l">Source</span>{f.document_ref}</div>}
          {f.policy_clause && (
            <blockquote className="clause">“{f.policy_clause}”
              <button className="text-btn" disabled={explaining} onClick={explain}>{explaining ? 'Asking the AI…' : 'Explain this clause'}</button>
            </blockquote>
          )}
          {expl && <div className="expl"><span className="ev-l">AI explanation — check against the policy</span>{expl}</div>}
          {f.action && <div><span className="ev-l">Suggested next step</span>{f.action}</div>}
        </div>
      )}

      <div className="conf" title="How reliable the extraction behind this finding is">
        <div className="conf-bar"><i style={{ width: `${pct}%` }} className={pct < 60 ? 'low' : ''} /></div>
        <span className="small mut">{pct}% confidence{pct < 60 ? ' — check the source document' : ''}</span>
      </div>

      {(f.severity !== 'info' || latest || editing) && <div className="review">
        {latest && !editing && (
          <div className="review-latest">
            <div><b>{DECIDED[latest.decision]}</b> by {latest.reviewer || 'a former member'} · {ago(latest.at)}{latest.comment && <> — “{latest.comment}”</>}</div>
            <div className="review-links">
              <button className="text-btn" onClick={() => setEditing(true)}>Change decision</button>
              {f.reviews.length > 1 && <button className="text-btn" onClick={() => setHistory(!history)}>{history ? 'Hide' : 'Show'} history ({f.reviews.length})</button>}
            </div>
            {history && <ul className="history">{f.reviews.slice(1).map((r, i) => <li key={i}>{DECIDED[r.decision]} by {r.reviewer || '—'} · {fmtDate(r.at)}{r.comment && ` — “${r.comment}”`}</li>)}</ul>}
          </div>
        )}
        {!latest && !editing && f.severity !== 'info' && <button className="text-btn" onClick={() => setEditing(true)}>Record a decision</button>}
        {editing && (
          <div className="review-form">
            <div className="seg" role="radiogroup" aria-label="Decision">
              {DECISIONS.map(([v, l]) => <button key={v} role="radio" aria-checked={decision === v} className={`seg-btn d-${v} ${decision === v ? 'on' : ''}`} onClick={() => setDecision(v)}>{l}</button>)}
            </div>
            <input type="text" className="comment" placeholder="Note for the audit trail (optional)" value={comment} onChange={e => setComment(e.target.value)} maxLength={1000} />
            <button className="primary sm" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save'}</button>
            {latest && <button className="ghost sm" onClick={() => { setEditing(false); setMsg(''); }}>Cancel</button>}
            {msg && <div className="review-msg">{msg}</div>}
          </div>
        )}
      </div>}
    </article>
  );
}

function DocumentCard({ d, claimId }) {
  const x = d.data || {};
  const money = new Set(['coverage_limit', 'deductible', 'total_amount']);
  const fields = [
    ['Patient', 'patient_name'], ['Hospital', 'hospital_name'], ['Claim no.', 'claim_id'], ['Policy no.', 'policy_number'],
    ['Invoice no.', 'invoice_number'], ['Invoice date', 'invoice_date'], ['Admitted', 'admission_date'], ['Discharged', 'discharge_date'],
    ['Diagnosis', 'diagnosis'], ['Valid from', 'policy_valid_from'], ['Valid to', 'policy_valid_to'],
    ['Sum insured', 'coverage_limit'], ['Deductible', 'deductible'], ['Stated total', 'total_amount'],
  ].filter(([, k]) => x[k] != null && x[k] !== '' && !(k === 'deductible' && !x[k]));
  const lists = [['Required documents', x.required_documents], ['Exclusions', x.exclusions], ['Policy clauses', x.policy_clauses]].filter(([, v]) => v?.length);
  const pct = Math.round((x.confidence || 0) * 100);
  const how = { text: 'Digital text', vision: 'Scanned (read from image)', 'text+vision': 'Text + scanned pages' }[d.extraction_method] || d.extraction_method;
  return (
    <article className="doc">
      <header className="doc-head">
        <span className={`doc-type t-${d.doc_type}`}>{DOC_LABEL[d.doc_type] || 'Document'}</span>
        <span className="doc-file" title={d.filename}>{d.filename}</span>
        <span className="mut small">{d.pages} page{d.pages === 1 ? '' : 's'} · {how}</span>
      </header>
      <div className="conf" title={`Extraction confidence ${pct}%`}>
        <div className="conf-bar"><i style={{ width: `${pct}%` }} className={pct < 60 ? 'low' : ''} /></div>
        <span className="mut small">{pct}% confidence</span>
      </div>
      {fields.length > 0 && <dl className="kv">{fields.map(([l, k]) => <React.Fragment key={k}><dt>{l}</dt><dd>{money.has(k) ? inr(x[k]) : x[k]}</dd></React.Fragment>)}</dl>}
      {x.itemized_charges?.length > 0 && (
        <table className="charges"><tbody>{x.itemized_charges.map((c, i) => <tr key={i}><td>{c.description}</td><td className="num">{inr(c.amount)}</td></tr>)}</tbody></table>
      )}
      {lists.map(([l, v]) => <details key={l} className="more"><summary>{l} ({v.length})</summary><ul>{v.map((s, i) => <li key={i}>{s}</li>)}</ul></details>)}
      {x.warnings?.length > 0 && <div className="doc-warn">{x.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>}
      <div className="doc-foot">
        {d.has_file ? <a className="text-btn" href={api.fileUrl(claimId, d.id)} target="_blank" rel="noopener">Open original PDF ↗</a>
          : <span className="mut small">Original PDF deleted after the retention period</span>}
      </div>
    </article>
  );
}

function Report({ claim, reload }) {
  const [filter, setFilter] = useState('all');
  const fs = claim.findings;
  const counts = Object.fromEntries(SEV_ORDER.map(s => [s, fs.filter(f => f.severity === s).length]));
  const needDecision = fs.filter(f => f.severity !== 'info');
  const decided = needDecision.filter(f => f.reviews.length).length;
  const shown = filter === 'all' ? fs : filter === 'open' ? needDecision.filter(f => !f.reviews.length) : fs.filter(f => f.severity === filter);
  const listRef = useStaggerIn('.finding', [filter]);
  const docsRef = useStaggerIn('.doc', []);
  const invoices = claim.documents.filter(d => d.doc_type === 'invoice' && d.data);
  const tabs = [['all', 'All', fs.length], ['open', 'Awaiting decision', needDecision.length - decided], ...SEV_ORDER.map(s => [s, SEV_LABEL[s], counts[s]])].filter(([k, , n]) => k === 'all' || n);

  return (
    <>
      <section className={`card summary s-${claim.status}`}>
        <p className="summary-hint">{STATUS[claim.status]?.hint}</p>
        <div className="stats">
          {SEV_ORDER.map(s => <div key={s} className={`stat sv-${s}`}><b><Count value={counts[s]} /></b><span>{SEV_LABEL[s]}</span></div>)}
          <div className="stat"><b><Count value={claim.documents.length} /></b><span>Documents</span></div>
        </div>
        {needDecision.length > 0 && (
          <div className="progress">
            <div className="progress-bar"><i style={{ width: `${(decided / needDecision.length) * 100}%` }} /></div>
            <span className="small">{decided} of {needDecision.length} issues reviewed</span>
          </div>
        )}
      </section>

      {invoices.length > 0 && (
        <section className="card">
          <h2>Bill check</h2>
          <div className="table-scroll"><table className="table">
            <thead><tr><th>Invoice</th><th className="num">Stated total</th><th className="num">Sum of line items</th><th className="num">Difference</th></tr></thead>
            <tbody>{invoices.map(d => {
              const stated = d.data.total_amount;
              const items = d.data.itemized_charges || [];
              const calc = items.length ? items.reduce((a, c) => a + c.amount, 0) : null;
              const diff = stated != null && calc != null ? stated - calc : null;
              return (
                <tr key={d.id}>
                  <td>{d.data.invoice_number || d.filename}</td>
                  <td className="num">{inr(stated)}</td><td className="num">{inr(calc)}</td>
                  <td className={`num ${diff == null ? '' : Math.abs(diff) > 1 ? 'neg' : 'pos'}`}>{diff == null ? 'Can’t check' : Math.abs(diff) > 1 ? inr(diff) : 'Matches'}</td>
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
            {tabs.map(([k, l, n]) => <button key={k} role="tab" aria-selected={filter === k} className={`tab ${filter === k ? 'on' : ''}`} onClick={() => setFilter(k)}>{l} <span>{n}</span></button>)}
          </div>
        </div>
        <div ref={listRef}>
          {shown.map(f => <FindingCard key={f.id} f={f} onReviewed={reload} />)}
          {!shown.length && <p className="mut">Nothing here.</p>}
        </div>
      </section>

      <section className="card">
        <h2>Documents</h2>
        <div className="docs" ref={docsRef}>{claim.documents.map(d => <DocumentCard key={d.id} d={d} claimId={claim.id} />)}</div>
      </section>
    </>
  );
}

export default function ClaimView({ id, me }) {
  const [claim, setClaim] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const load = () => api.claim(id).then(c => { setClaim(c); setErr(''); }).catch(e => setErr(e.message));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const running = claim && (claim.state === 'queued' || claim.state === 'processing');
  usePoll(load, 3000, running);

  async function act(fn) {
    setBusy(true);
    try { await fn(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  const retry = () => act(async () => { await api.retry(id); await load(); });
  const remove = () => {
    if (!window.confirm('Delete this claim, its documents, findings and reviews? This cannot be undone.')) return;
    act(async () => { await api.deleteClaim(id); go('/app'); });
  };

  if (!claim) return err ? <div className="err">{err} <a href="#/app">Back to claims</a></div> : <div className="empty-row"><span className="spin dark" /></div>;

  return (
    <>
      <div className="page-bar">
        <div>
          <a href="#/app" className="back">← Claims</a>
          <h1 className="page-title mono-title">{claim.claim_ref || `Claim #${claim.id}`} <StatusBadge claim={claim} /></h1>
          <p className="mut small">
            {[claim.patient_name, claim.hospital_name, claim.total_claimed != null && inr(claim.total_claimed)].filter(Boolean).join(' · ')}
            {(claim.patient_name || claim.hospital_name) && <br />}
            Submitted by {claim.created_by || 'a former member'} · {fmtDate(claim.created_at)}
          </p>
        </div>
        {me.role === 'admin' && <button className="ghost sm danger" disabled={busy} onClick={remove}>Delete claim</button>}
      </div>
      {err && <div className="err">{err}</div>}

      {running && (
        <div className="card processing">
          <div className="scan"><div className="scan-page" /><div className="scan-page" /><div className="scan-page" /><div className="scan-line" /></div>
          <h3>{claim.state === 'queued' ? 'Waiting in the queue…' : `Reading ${claim.documents.length} document${claim.documents.length === 1 ? '' : 's'}…`}</h3>
          <p className="mut">
            {claim.state === 'processing'
              ? <>The AI reads each document (scanned pages from their images), then the rules check the claim. <Elapsed from={claim.started_at} /></>
              : 'Another claim is being verified. This one starts automatically.'}
            <br />You can leave this page — the claim keeps processing.
          </p>
        </div>
      )}

      {claim.state === 'failed' && (
        <div className="card failed">
          <h3>Verification couldn’t finish</h3>
          <p className="mut">{claim.error || 'Unknown error.'}</p>
          <p className="mut small">This is usually the AI service being unavailable or out of credits. Your documents are stored; you can try again.</p>
          <button className="primary" disabled={busy} onClick={retry}>{busy ? 'Queuing…' : 'Try again'}</button>
        </div>
      )}

      {claim.state === 'done' && <Report claim={claim} reload={load} />}
    </>
  );
}
