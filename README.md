# Kaagaz — health-insurance claim verification

Upload a claim's PDFs (policy, hospital invoices, discharge summary, prescriptions,
diagnostic reports, claim form). Kaagaz reads them with a vision LLM, runs
deterministic checks, and gives reviewers an evidence-backed report to confirm or
dismiss. It never approves, rejects or labels fraud.

```
React (Vite) ──► FastAPI ──► Postgres queue (claims) ──► worker
                                                 │
            PyMuPDF text layer + scanned-page images ──► LLM (OpenRouter) ──► JSON (strict schema)
                                                 │
                         verifier.py (pure Python rules) ──► findings ──► reviewer decisions
```

## Pipeline
- **Digital pages** use the PDF text layer (exact, free). **Scanned pages** (<50 chars of text)
  are rendered to JPEG and sent as images in the *same* call — one LLM call per document.
- The model returns JSON constrained by a strict schema; `pipeline.clean()` then normalises
  dates to ISO, parses money, and drops totals/charges that the model put on non-invoices.
- `verifier.py` decides everything: bill arithmetic, duplicate invoices (in the claim and
  across earlier claims), missing required documents, policy period, coverage limit,
  exclusions, claim-number/patient consistency, low-confidence reads.
- Requests to OpenRouter set `provider.data_collection = "deny"` (only providers that don't
  collect prompt data). Set `LLM_BASE_URL=http://localhost:11434/v1` to use a local Ollama
  vision model instead.

**Model:** `google/gemini-2.5-flash` is the default (strong at reading bills, ≈1¢ per
6-document claim). Without OpenRouter credits, use `dots-studio/dots-3-note-preview:free`
(scored 22/22 on the sample invoices and policy, but slow, ~30 s per document, and capped at ~50 requests/day).

## Data model (`backend/app/schema.sql`, applied on startup)
`orgs` → `users` (admin | reviewer) → `claims` (job `state` + outcome `status`) →
`documents` (encrypted PDF, extracted `data` JSONB) → `findings` → `reviews` (append-only
history). `access_log` records sign-ins, uploads, views, PDF downloads, reviews, deletions.
Every query is scoped by `org_id`; RLS is enabled so Supabase's public REST API can't read tables.

## Run locally
```powershell
# 1. Backend
cd backend
python -m venv ..\.venv; ..\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # fill DATABASE_URL, SECRET_KEY, FILE_ENCRYPTION_KEY, OPENROUTER_API_KEY
..\.venv\Scripts\python -m uvicorn app.main:app --port 8002
# 2. Frontend
cd ..\frontend; npm install; npm run dev     # http://localhost:5173 (proxies /api -> :8002)
```
Create a workspace at `/#/signup`; add reviewers under Settings → Team.
The worker runs inside the API by default; for more throughput set `WORKER_ENABLED=false`
and run `python -m app.worker` (any number of them — the queue uses `SKIP LOCKED`).

## Demo documents (synthetic, no real PHI)
`python samples/make_pdfs.py` regenerates them.

| Scenario | Upload | Expected |
|---|---|---|
| A | policy_A, invoice_A, discharge_A, prescription_A, diagnostic_A, claimform_A | consistent |
| B | A with `invoice_B_mismatch` | incomplete — total mismatch (78,000 vs 73,000) |
| C | policy_A, invoice_A | incomplete — 4 required documents missing |
| D | A with `invoice_A_scanned` (image-only) | read via vision; flags "invoice already submitted" if C exists |

## Tests
`python -m pytest backend/tests` — verifier, extraction cleaning, auth, schema (no DB/LLM needed).

## Production notes
- `COOKIE_SECURE=true` behind HTTPS; set `CORS_ORIGINS` to the real frontend origin.
- Keep `FILE_ENCRYPTION_KEY` safe — losing it makes stored PDFs unreadable.
- Rate limits are in-process; move them to Redis/Postgres if you run several API processes.
