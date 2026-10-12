import React, { useState } from 'react';
import { apiReview, apiExplain } from './api.js';

export const SEV_ORDER = ['action_required', 'policy_review', 'warning', 'info'];
export const SEV_LABEL = { info: 'Verified', warning: 'Warning', action_required: 'Action required', policy_review: 'Policy review' };
export const inr = n => n == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n);

const DECISIONS = [['confirmed', 'Confirm'], ['dismissed', 'Dismiss'], ['inconclusive', 'Inconclusive']];
// Only these checks carry money in extracted/expected values (others may be invoice numbers or dates).
const isMoney = code => /^(TOTAL_|COVERAGE_)/.test(code);

export default function FindingCard({ f, auditId, reviewer }) {
  const [decision, setDecision] = useState('');
  const [comment, setComment] = useState('');
  const [saved, setSaved] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [expl, setExpl] = useState('');
  const [explaining, setExplaining] = useState(false);
  const val = v => isMoney(f.code) && !isNaN(Number(v)) ? inr(Number(v)) : v;
  const pct = Math.round(f.confidence * 100);

  async function submit() {
    if (!decision) { setMsg('Choose a decision first.'); return; }
    if (!reviewer.trim()) { setMsg('Enter your name in “Reviewing as” above.'); return; }
    setSaving(true); setMsg('');
    try {
      await apiReview({ audit_id: auditId, finding_code: f.code, decision, comment: comment.trim(), reviewer: reviewer.trim() });
      setSaved(decision);
    } catch (e) { setMsg('Review not saved: ' + e.message); }
    finally { setSaving(false); }
  }
  async function explain() {
    setExplaining(true);
    try { setExpl((await apiExplain(f.policy_clause)).explanation); }
    catch (e) { setExpl('Explanation unavailable: ' + e.message); }
    finally { setExplaining(false); }
  }

  return (
    <article className={`finding sv-${f.severity}`}>
      <div className="finding-head">
        <span className={`pill p-${f.severity}`}>{SEV_LABEL[f.severity] || f.severity}</span>
        <h3>{f.title}</h3>
        <span className="mono code" title="Finding code">{f.code}</span>
      </div>
      <p className="finding-detail">{f.detail}</p>

      {(f.extracted_value || f.document_ref || f.policy_clause) && (
        <div className="evidence">
          {f.extracted_value && (
            <div className="ev-vals">
              <div><span className="ev-l">Found</span><span className="mono">{val(f.extracted_value)}</span></div>
              {f.expected_value && <div><span className="ev-l">Expected</span><span className="mono">{val(f.expected_value)}</span></div>}
            </div>
          )}
          {f.document_ref && <div className="ev-row"><span className="ev-l">Source</span><span>{f.document_ref}</span></div>}
          {f.policy_clause && (
            <blockquote className="clause">
              “{f.policy_clause}”
              <button className="text-btn" disabled={explaining} onClick={explain}>{explaining ? 'Asking local LLM…' : 'Explain this clause'}</button>
            </blockquote>
          )}
          {expl && <div className="expl"><span className="ev-l">AI explanation — verify against the policy</span>{expl}</div>}
        </div>
      )}

      <div className="finding-meta">
        <div className="conf" title="How sure the extraction behind this finding is">
          <div className="conf-bar"><i style={{ width: `${pct}%` }} className={pct < 60 ? 'low' : ''} /></div>
          <span className="small">{pct}% confidence{pct < 60 ? ' — verify manually' : ''}</span>
        </div>
        {f.action && <div className="next"><span className="ev-l">Next step</span>{f.action}</div>}
      </div>

      {auditId && (
        <div className="review">
          {saved ? (
            <div className="saved">✓ Recorded as <b>{saved}</b> by {reviewer} <button className="text-btn" onClick={() => setSaved('')}>Change</button></div>
          ) : (
            <>
              <div className="seg" role="radiogroup" aria-label="Reviewer decision">
                {DECISIONS.map(([v, l]) => (
                  <button key={v} role="radio" aria-checked={decision === v} className={`seg-btn d-${v} ${decision === v ? 'on' : ''}`} onClick={() => setDecision(v)}>{l}</button>
                ))}
              </div>
              <input type="text" className="comment" placeholder="Add a note for the audit trail (optional)" value={comment} onChange={e => setComment(e.target.value)} maxLength={1000} />
              <button className="primary sm" disabled={saving} onClick={submit}>{saving ? 'Saving…' : 'Save review'}</button>
            </>
          )}
          {msg && <div className="review-msg">{msg}</div>}
        </div>
      )}
    </article>
  );
}
