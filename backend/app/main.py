"""ClaimLens AI API — parse (PyMuPDF+VLM/LLM->JSON), verify, review, audit."""
import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .models import ParseResponse, VerificationReport, ReviewInput, Finding
from .service import parse_one_pdf
from .verifier import verify, recalc_invoice
from . import store
from . import llm as llm_mod

app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)


@app.get("/api/health")
def health():
    vlm = llm_mod.pick_vision_model()
    return {"status": "ok", "llm": settings.ollama_model, "vlm": vlm or "none",
            "db": "postgres:up" if store.ping() else "postgres:down (check DATABASE_URL in backend/.env)",
            "pipeline": "pymupdf -> " + ("vlm+llm" if vlm else "llm (vlm on scanned pages if installed)")}


@app.post("/api/parse", response_model=ParseResponse)
async def parse(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded.")
    docs, used = [], settings.ollama_model
    for f in files:
        raw = await f.read()
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, f"{f.filename}: only PDF allowed.")
        try:
            doc, used = parse_one_pdf(raw, f.filename or "upload.pdf")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(502, f"Extraction failed for {f.filename}: {e}")
        docs.append(doc)
    pipe = docs[0].extraction_method if docs else "text+llm"
    return ParseResponse(documents=docs, model_used=used, pipeline=f"pymupdf+{pipe}")


@app.post("/api/verify", response_model=VerificationReport)
async def verify_claim(files: List[UploadFile] = File(...), claim_id: str = ""):
    parsed = await parse(files)
    cid = claim_id or (parsed.documents[0].claim_id if parsed.documents else None) \
        or f"CLM-{uuid.uuid4().hex[:8].upper()}"
    findings = verify(parsed.documents, cid)
    # Deterministic cross-document check: all pages should reference one claim.
    cids = sorted({d.claim_id for d in parsed.documents if d.claim_id})
    if len(cids) > 1:
        findings.append(Finding(
            code="CLAIM_ID_MISMATCH", title="Claim IDs differ across documents",
            severity="warning",
            detail=f"Documents reference different claim IDs: {', '.join(cids)}. "
                   "Possibly mixed uploads; confirm the correct claim before review.",
            extracted_value=", ".join(cids),
            document_ref=", ".join(d.filename for d in parsed.documents if d.claim_id),
            confidence=0.9,
            action="Confirm which claim these documents belong to."))
    sev = {f.severity for f in findings}
    status = "incomplete" if any(s == "action_required" for s in sev) \
        else ("needs_review" if ("warning" in sev or "policy_review" in sev) else "consistent")
    totals = {d.filename: {"stated": d.total_amount,
                           "recalculated": recalc_invoice(d) if d.document_type == "invoice" else None}
              for d in parsed.documents}
    aid = _save_verification(cid, status,
                               json.dumps([f.model_dump() for f in findings]),
                               json.dumps([d.model_dump() for d in parsed.documents]))
    return VerificationReport(claim_id=cid, status=status, findings=findings,
                              documents=parsed.documents,
                              totals_recalculated=totals, audit_id=aid)


def _save_verification(cid: str, status: str, findings_json: str, docs_json: str) -> Optional[int]:
    # Don't discard a finished report because the DB is down; audit_id=None tells the UI it wasn't saved.
    try:
        return store.save_verification(cid, status, findings_json, docs_json)
    except Exception:
        return None


@app.post("/api/review")
def review(inp: ReviewInput):
    try:
        rid = store.save_review(inp.audit_id, inp.finding_code, inp.decision,
                                inp.comment, inp.reviewer)
    except Exception as e:
        raise HTTPException(503, f"Database unavailable (check DATABASE_URL): {e}")
    return {"review_id": rid, "status": "recorded"}


@app.get("/api/audits")
def audits(limit: int = 50):
    try:
        return store.list_verifications(limit)
    except Exception as e:
        raise HTTPException(503, f"Database unavailable (check DATABASE_URL): {e}")


@app.post("/api/explain")
def explain(payload: dict):
    clause = str(payload.get("clause", ""))[:2000]
    q = str(payload.get("question", "Explain its relevance to this claim."))
    if not clause:
        raise HTTPException(400, "clause is required.")
    try:
        return {"explanation": llm_mod.llm_explain_clause(clause, q)}
    except Exception as e:
        raise HTTPException(502, f"LLM unavailable: {e}")
