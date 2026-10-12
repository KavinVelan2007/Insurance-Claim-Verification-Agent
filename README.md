# ClaimLens AI — Insurance Claim Verification Agent

`React (Vite) → FastAPI → PyMuPDF / local Ollama LLM → Python verification rules → PostgreSQL (Supabase) → React report`

## Parsing API (local Ollama, your request)
- `POST /api/parse` — upload 1..N PDFs → structured JSON per document: claim details,
  invoice numbers, itemized charges, totals, hospitalization dates, policy validity,
  coverage limits, exclusions, required documents. Model: `granite3-moe:3b` (local, ~2 GB).
- `POST /api/verify` — parse + deterministic verification + PostgreSQL audit row.
- `POST /api/review` — human-in-the-loop confirm / dismiss / inconclusive + comment.
- `GET /api/audits` — audit trail. `POST /api/explain` — explains a quoted clause only.

## VLM vs OCR+LLM (accuracy–speed decision)
Default = **PyMuPDF text → local text LLM → validated JSON**.
- Digital PDFs: PyMuPDF is ~100× faster than a VLM and near-perfect → VLM adds
  seconds/page for zero accuracy gain.
- Scanned pages (<50 chars/page) → rendered PNG → **local Ollama VLM** (auto-detected:
  moondream / llava / qwen2-vl / llama3.2-vision / …) for transcription → same text LLM.
- No VLM installed + scanned input → graceful `regex-fallback` with a warning, never
  hallucinated text. Pull one only for scans: `ollama pull moondream`.

## Quickstart
```powershell
ollama serve                                   # local daemon
cd backend
pip install -r requirements.txt
copy .env.example .env                         # OLLAMA_MODEL=granite3-moe:3b
$env:OLLAMA_HOST='http://127.0.0.1:11434'      # if your env has 0.0.0.0, use 127.0.0.1
python -m uvicorn app.main:app --port 8002
cd ..\frontend; npm install; npm run dev       # http://localhost:5173 (proxies /api → :8002)
```

## Demo (3 synthetic scenarios, no real PHI)
`python samples/make_pdfs.py` regenerates the PDFs, or use `samples/*.pdf` directly.

| Scenario | Upload | Expected |
|---|---|---|
| A consistent | `policy_A invoice_A discharge_A prescription_A diagnostic_A claimform_A` | `consistent`: TOTAL_OK + COVERAGE_OK (info). Note: B's files carry CLM-DEMO-B vs A's CLM-DEMO-A claim IDs |
| B total mismatch | same set but `invoice_B_mismatch` (stated 78000, items sum 73000) | `incomplete`: `action_required TOTAL_MISMATCH` (diff 5000) |
| C missing docs | `policy_A invoice_A` only | `incomplete`: 4× `action_required MISSING_*` (discharge, prescription, diagnostics, claim form) |

Fast check without the LLM: `python backend/tests/test_verifier.py` logic via
`python -c "import sys;sys.path.insert(0,'backend');from tests.test_verifier import *;..."`.
The tool never auto-approves/rejects or labels fraud — worst status is
`incomplete`/`needs_review` for human review.

## Safety & limits
- Server-side keys (`.env`); PDFs validated (magic bytes, 15 MB cap); Pydantic-validated
  model JSON; low-confidence values flagged; non-invoice charges/totals dropped.
- Verification is deterministic Python (totals, duplicates, dates, coverage, claim-ID
  consistency); the LLM only extracts and quotes clauses.
- Scanned PDFs need a local VLM or they degrade to regex-fallback with a warning.