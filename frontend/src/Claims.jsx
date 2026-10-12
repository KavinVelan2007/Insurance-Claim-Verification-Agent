import React, { useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { Count, StatusBadge, ago, go, inr, kb, usePoll, useStaggerIn } from './ui.jsx';

const TILES = [['in_progress', 'In progress'], ['incomplete', 'Incomplete'], ['needs_review', 'Needs review'], ['consistent', 'Consistent']];

export function ClaimList() {
  const [data, setData] = useState(null);
  const [more, setMore] = useState([]);
  const [q, setQ] = useState('');
  const [err, setErr] = useState('');
  const load = (query = q) => api.claims(query).then(d => { setData(d); setMore([]); setErr(''); }).catch(e => setErr(e.message));

  useEffect(() => { const t = setTimeout(() => load(q), q ? 300 : 0); return () => clearTimeout(t); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const items = [...(data?.items || []), ...more];
  const busy = items.some(c => c.state === 'queued' || c.state === 'processing');
  usePoll(() => load(), 4000, busy && !more.length);
  const ref = useStaggerIn('.row-in', [data?.items?.length]);

  async function loadMore() {
    const d = await api.claims(q, items.length).catch(e => { setErr(e.message); return null; });
    if (d) setMore([...more, ...d.items]);
  }

  return (
    <>
      <div className="page-bar">
        <div><h1 className="page-title">Claims</h1><p className="mut">Every verification in your workspace, newest first.</p></div>
        <a className="btn primary" href="#/app/new">New claim</a>
      </div>
      {data && (
        <div className="tiles">
          {TILES.map(([k, l]) => <div key={k} className={`tile t-${k}`}><b><Count value={data.stats[k]} /></b><span>{l}</span></div>)}
        </div>
      )}
      <section className="card flush">
        <div className="table-tools">
          <input type="search" placeholder="Search by claim number, patient or hospital" value={q} onChange={e => setQ(e.target.value)} aria-label="Search claims" />
        </div>
        {err && <div className="err m">{err}</div>}
        {!data && !err && <div className="empty-row"><span className="spin dark" /></div>}
        {data && !items.length && (
          <div className="empty-row">
            {q ? 'No claims match your search.' : <>No claims yet. <a href="#/app/new">Verify your first claim →</a></>}
          </div>
        )}
        {items.length > 0 && (
          <div className="table-scroll" ref={ref}>
            <table className="table claims-table">
              <thead><tr><th>Claim</th><th>Patient</th><th>Hospital</th><th className="num">Billed</th><th>Status</th><th className="num">Open issues</th><th>Submitted</th></tr></thead>
              <tbody>
                {items.map(c => (
                  <tr key={c.id} className="row-in clickable" tabIndex={0} onClick={() => go(`/app/claims/${c.id}`)}
                    onKeyDown={e => e.key === 'Enter' && go(`/app/claims/${c.id}`)}>
                    <td className="mono strong">{c.claim_ref || `#${c.id}`}</td>
                    <td>{c.patient_name || <span className="mut">—</span>}</td>
                    <td className="ellipsis-cell" title={c.hospital_name || ''}>{c.hospital_name || <span className="mut">—</span>}</td>
                    <td className="num">{inr(c.total_claimed)}</td>
                    <td><StatusBadge claim={c} /></td>
                    <td className="num">{c.state === 'done' ? (c.open_findings ? <span className="open-n">{c.open_findings}</span> : '0') : '—'}</td>
                    <td className="small"><div>{ago(c.created_at)}</div><div className="mut">{c.created_by || ''} · {c.doc_count} docs</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {items.length > 0 && items.length % 25 === 0 && <div className="more-row"><button className="ghost sm" onClick={loadMore}>Load more</button></div>}
      </section>
    </>
  );
}

function Dropzone({ files, setFiles, disabled, maxMb, maxFiles, onReject }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);
  const listRef = useStaggerIn('.file', [files.length]);
  function add(list) {
    const bad = [];
    const next = [...files];
    for (const f of list) {
      if (!/\.pdf$/i.test(f.name)) bad.push(`${f.name}: not a PDF`);
      else if (f.size > maxMb * 1048576) bad.push(`${f.name}: over ${maxMb} MB`);
      else if (next.length >= maxFiles) bad.push(`${f.name}: limit is ${maxFiles} files`);
      else if (!next.some(x => x.name === f.name && x.size === f.size)) next.push(f);
    }
    setFiles(next);
    onReject(bad.join(' · '));
  }
  const pick = () => !disabled && input.current.click();
  return (
    <>
      <div className={`drop ${over ? 'over' : ''} ${disabled ? 'disabled' : ''}`} role="button" tabIndex={0}
        onClick={pick} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && pick()}
        onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={e => { e.preventDefault(); setOver(false); if (!disabled) add(e.dataTransfer.files); }}>
        <img src="/kaagaz-mark.png" alt="" className="drop-mark" />
        <div><b>Drop the claim’s PDFs here</b> or <span className="link">browse</span></div>
        <div className="mut small">Policy · hospital invoices · discharge summary · prescriptions · diagnostic reports · claim form</div>
        <div className="mut small">Up to {maxFiles} PDFs, {maxMb} MB each. Scanned PDFs are fine.</div>
        <input ref={input} type="file" multiple accept="application/pdf,.pdf" hidden onChange={e => { add(e.target.files); e.target.value = ''; }} />
      </div>
      {files.length > 0 && (
        <ul className="files" ref={listRef}>
          {files.map((f, i) => (
            <li key={f.name + f.size} className="file">
              <span className="file-ic">PDF</span>
              <span className="file-name" title={f.name}>{f.name}</span>
              <span className="mut small">{kb(f.size)}</span>
              <button className="icon-btn" disabled={disabled} aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}>×</button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function NewClaim() {
  const [files, setFiles] = useState([]);
  const [ref, setRef] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [sys, setSys] = useState(null);
  useEffect(() => { api.system().then(setSys).catch(() => {}); }, []);
  const notReady = sys && (!sys.llm.configured || !sys.db);

  async function submit() {
    setBusy(true); setErr('');
    try { const r = await api.createClaim(files, ref.trim()); go(`/app/claims/${r.id}`); }
    catch (e) { setErr(e.message); setBusy(false); }
  }

  return (
    <>
      <div className="page-bar"><div><a href="#/app" className="back">← Claims</a><h1 className="page-title">New claim</h1>
        <p className="mut">Add every document for one claim. Kaagaz reads them in the background — you can leave this page.</p></div></div>
      {notReady && (
        <div className="err">The verification engine isn’t ready: {[!sys.llm.configured && 'no AI key is configured', !sys.db && 'the database is offline'].filter(Boolean).join(' and ')}. Claims will wait in the queue until it is. Details in <a href="#/app/settings">Settings</a>.</div>
      )}
      <div className="new-grid">
        <section className="card">
          <Dropzone files={files} setFiles={setFiles} disabled={busy} maxMb={sys?.max_upload_mb || 15} maxFiles={sys?.max_files || 20} onReject={setErr} />
          <label className="field">Claim number <span className="mut">(optional — read from the documents if blank)</span>
            <input type="text" maxLength={64} placeholder="e.g. CLM-2026-00481" value={ref} onChange={e => setRef(e.target.value)} disabled={busy} />
          </label>
          {err && <div className="err" role="alert">{err}</div>}
          <div className="actions">
            <button className="primary" disabled={busy || !files.length} onClick={submit}>{busy ? <><span className="spin" />Uploading…</> : `Verify ${files.length || ''} document${files.length === 1 ? '' : 's'}`}</button>
            {files.length > 0 && !busy && <button className="ghost" onClick={() => { setFiles([]); setErr(''); }}>Clear</button>}
          </div>
        </section>
        <aside className="card tips">
          <h2>For the best result</h2>
          <ul>
            <li>Include the <b>policy schedule</b> — without it, coverage, dates, exclusions and required documents can’t be checked.</li>
            <li>Upload the <b>final itemised bill</b>, not only a summary bill.</li>
            <li>Scanned pages are read by the AI from their images; clear, upright pages read best.</li>
          </ul>
        </aside>
      </div>
    </>
  );
}
