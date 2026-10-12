import React, { useState } from 'react';
import { apiReview, apiExplain } from './api.js';

export const SEV_LABEL = { info: 'Information complete', warning: 'Warning', action_required: 'Action required', policy_review: 'Policy review' };

export default function FindingCard({ f, auditId }) {
  const [decision, setDecision] = useState('confirmed');
  const [comment, setComment] = useState('');
  const [reviewer, setReviewer] = useState('reviewer');
  const [msg, setMsg] = useState('');
  const [expl, setExpl] = useState('');
  async function submit() {
    try {
      await apiReview({ audit_id: auditId, finding_code: f.code, decision, comment, reviewer });
      setMsg('Recorded: ' + decision);
    } catch (e) { setMsg('Review failed: ' + e.message); }
  }
  async function explain() {
    if (!f.policy_clause) { setExpl('No policy clause attached.'); return; }
    try { const r = await apiExplain(f.policy_clause); setExpl(r.explanation); }
    catch (e) { setExpl('Explain failed: ' + e.message); }
  }
  return (
    <div className="finding">
      <div className="row"><span className={`pill p-${f.severity}`}>{SEV_LABEL[f.severity] || f.severity}</span><b>{f.title}</b></div>
      <div className="mut" style={{ marginTop: 6 }}>{f.detail}</div>
      <div className="meta">
        {f.extracted_value && <div>Extracted: <code>{f.extracted_value}</code>{f.expected_value && <> | Expected: <code>{f.expected_value}</code></>}</div>}
        {f.document_ref && <div>Document: {f.document_ref}</div>}
        {f.policy_clause && <div>Policy clause: <i>{f.policy_clause}</i></div>}
        <div>Confidence: {(f.confidence * 100).toFixed(0)}%{f.confidence < 0.6 ? ' — low, verify manually' : ''}</div>
        {f.action && <div>Next action: {f.action}</div>}
      </div>
      {f.policy_clause && <div className="row" style={{ marginTop: 8 }}><button className="ghost" onClick={explain}>Explain clause (LLM)</button></div>}
      {expl && <div className="mut" style={{ marginTop: 6 }}>{expl}</div>}
      {auditId ? (
        <div className="row" style={{ marginTop: 8 }}>
          <select value={decision} onChange={e => setDecision(e.target.value)}>
            <option value="confirmed">Confirm</option>
            <option value="dismissed">Dismiss</option>
            <option value="inconclusive">Inconclusive</option>
          </select>
          <input type="text" placeholder="Reviewer" value={reviewer} onChange={e => setReviewer(e.target.value)} style={{ maxWidth: 130 }} />
          <input type="text" placeholder="Comment" value={comment} onChange={e => setComment(e.target.value)} style={{ flex: 1 }} />
          <button onClick={submit}>Save review</button>
          {msg && <span className="mut">{msg}</span>}
        </div>
      ) : null}
    </div>
  );
}
