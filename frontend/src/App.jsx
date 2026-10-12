import React, { useEffect, useState } from 'react';
import { apiParse, apiVerify, apiAudits, apiHealth } from './api.js';
import FindingCard from './FindingCard.jsx';

export default function App() {
  const [files, setFiles] = useState([]);
  const [claimId, setClaimId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [parsed, setParsed] = useState(null);
  const [report, setReport] = useState(null);
  const [health, setHealth] = useState(null);
  const [audits, setAudits] = useState([]);
  useEffect(() => {
    apiHealth().then(setHealth).catch(() => setHealth({ status: 'backend offline' }));
    apiAudits().then(setAudits).catch(() => {});
  }, []);
  async function run(mode) {
    setError(''); setBusy(true);
    try {
      if (!files.length) throw new Error('Select at least one PDF.');
      if (mode === 'parse') { setReport(null); setParsed(await apiParse(files)); }
      else { setParsed(null); const r = await apiVerify(files, claimId); setReport(r); setAudits(await apiAudits()); }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return (
    <div className="wrap">
      <div className="top">
        <div className="brand"><h1>ClaimLens AI</h1><p>Upload → parse (local LLM JSON) → deterministic verification → human review. Never auto-approves.</p></div>
        <div className="health">{health ? `Backend: ${health.status} · LLM: ${health.llm || '?'} · VLM: ${health.vlm || '?'}` : 'Checking backend…'}</div>
      </div>
      <div className="grid">
        <div className="card">
          <h2>1 · Upload claim PDFs</h2>
          <input type="file" multiple accept="application/pdf" onChange={e => setFiles([...e.target.files])} />
          <div className="mut" style={{ margin: '8px 0' }}>{files.length ? `${files.length} file(s): ${files.map(f => f.name).join(', ')}` : 'Policy, invoice, discharge summary, prescription…'}</div>
          <input type="text" placeholder="Claim ID (optional)" value={claimId} onChange={e => setClaimId(e.target.value)} style={{ marginBottom: 8 }} />
          <div className="row">
            <button disabled={busy} onClick={() => run('parse')}>{busy ? 'Working…' : 'Parse only (JSON)'}</button>
            <button disabled={busy} onClick={() => run('verify')}>{busy ? 'Working…' : 'Verify claim'}</button>
          </div>
          {error && <div className="err">{error}</div>}
          <div className="notice">Keys stay server-side; PDFs validated; failures degrade gracefully.</div>
          <h2 style={{ marginTop: 16 }}>Audit trail</h2>
          <table><thead><tr><th>ID</th><th>Claim</th><th>Status</th></tr></thead>
          <tbody>{audits.map(a => <tr key={a.id}><td>{a.id}</td><td>{a.claim_id}</td><td>{a.status}</td></tr>)}</tbody></table>
        </div>
        <div className="card">
          <h2>2 · Verification report</h2>
          {!parsed && !report && <div className="mut">Run Parse only for JSON, or Verify claim for the full report.</div>}
          {parsed && (<><div className="mut">Pipeline: {parsed.pipeline} · Model: {parsed.model_used}</div>
            <pre className="json">{JSON.stringify(parsed.documents, null, 2)}</pre></>)}
          {report && (
            <>
              <div className="row"><span>Claim <b>{report.claim_id}</b></span><span className="status">· {report.status}</span><span className="mut">· audit #{report.audit_id}</span></div>
              <div className="mut" style={{ marginTop: 8 }}>Recalculated totals:</div>
              <pre className="json">{JSON.stringify(report.totals_recalculated, null, 2)}</pre>
              {report.findings.map(f => <FindingCard key={f.code} f={f} auditId={report.audit_id} />)}
              <h2>Extracted documents</h2>
              <pre className="json">{JSON.stringify(report.documents, null, 2)}</pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
