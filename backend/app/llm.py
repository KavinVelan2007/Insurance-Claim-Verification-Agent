"""Ollama client — local text LLM + optional local VLM, JSON-validated.

Accuracy/speed decision:
- OCR+VLM is NOT the default: without tesseract installed and no vision
  model pulled, it would only add latency. Default pipeline is
  PyMuPDF text -> local text LLM (granite3-moe:3b) -> validated JSON.
- VLM path activates ONLY when (a) scanned pages exist AND (b) a local
  vision model (moondream/llava/bakllava/qwen2-vl/llama3.2-vision/minicpm-v)
  is found via `ollama list`. Otherwise we return a graceful failure flag.
"""
import json
import re
from typing import Optional, Dict, Any, List

import ollama

from .config import settings

EXTRACTION_SCHEMA_HINT = """Return ONLY valid JSON (no markdown, no commentary) with keys:
{"document_type": "policy|invoice|discharge_summary|prescription|diagnostic_report|claim_form|other",
"claim_id": string|null, "patient_name": string|null, "hospital_name": string|null,
"invoice_number": string|null, "invoice_date": "YYYY-MM-DD"|null,
"itemized_charges": [{"description": string, "amount": number}],
"total_amount": number|null, "currency": "INR",
"admission_date": "YYYY-MM-DD"|null, "discharge_date": "YYYY-MM-DD"|null,
"diagnosis": string|null, "policy_number": string|null,
"policy_valid_from": "YYYY-MM-DD"|null, "policy_valid_to": "YYYY-MM-DD"|null,
"coverage_limit": number|null, "deductible": number,
"exclusions": [string], "required_documents": [string],
"policy_clauses": [string], "confidence": 0.0-1.0}
Rules: use null when unknown (never invent numbers/dates); copy itemized amounts exactly;
normalize dates to YYYY-MM-DD; confidence < 0.5 when text is garbled.
For policy documents: itemized_charges MUST be [], admission/discharge/invoice dates MUST be null
(dates in a policy are validity dates, not treatment dates); invoice_number MUST be null.
For non-invoice documents (discharge_summary, prescription, diagnostic_report, claim_form, policy):
itemized_charges MUST be [] and total_amount MUST be null — only invoices have charges/totals.
For claim forms: capture claim_id, patient_name, hospital_name, admission/discharge dates if present."""

VLM_OCR_PROMPT = (
    "Transcribe this document page EXACTLY. Return only the visible text, "
    "preserving line breaks and numbers. Do not summarize or invent anything."
)

VISION_MODEL_KEYWORDS = (
    "moondream", "llava", "bakllava", "qwen2-vl", "qwen2.5vl", "qwen2.5-vl",
    "llama3.2-vision", "minicpm-v", " granite-vision",
)


def _client() -> ollama.Client:
    return ollama.Client(host=settings.ollama_host, timeout=settings.ollama_timeout_s)


def pick_vision_model() -> Optional[str]:
    """Return configured or auto-detected local vision model, else None."""
    if settings.ollama_vlm_model.strip():
        return settings.ollama_vlm_model.strip()
    try:
        models = _client().list().get("models", [])
        names = [m.get("name", "") or m.get("model", "") for m in models]
    except Exception:
        return None
    for n in names:
        low = n.lower()
        if any(k.strip() in low for k in VISION_MODEL_KEYWORDS if k.strip()):
            return n
    return None


def vlm_ocr_page(image_b64: str, model: str) -> str:
    import base64
    img = base64.b64decode(image_b64)
    resp = _client().generate(model=model, prompt=VLM_OCR_PROMPT, images=[img])
    return (resp.get("response") or "").strip()


def llm_extract(document_text: str, filename: str = "") -> Dict[str, Any]:
    """Text -> structured JSON via local Ollama text model. Never raises on bad JSON."""
    client = _client()
    prompt = (
        "You are a health-insurance document parser. Extract the fields precisely.\n"
        + EXTRACTION_SCHEMA_HINT
        + f"\n\nSOURCE FILE: {filename}\nDOCUMENT TEXT (may be truncated):\n{document_text[:12000]}"
    )
    resp = client.generate(
        model=settings.ollama_model,
        prompt=prompt,
        format="json",
        options={"temperature": 0},
    )
    raw = (resp.get("response") or "").strip()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
        return data
    except Exception:
        # Salvage the first {...} block if the model added stray text
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"_parse_error": raw[:2000]}


def llm_explain_clause(clause: str, question: str = "Explain its relevance to this claim.") -> str:
    resp = _client().generate(
        model=settings.ollama_model,
        prompt=(
            "You are a claim assistant. Explain ONLY the policy clause quoted below. "
            "Do not invent policy terms.\nCLAUSE: " + clause[:2000] + "\nQUESTION: " + question
        ),
        options={"temperature": 0.2},
    )
    return (resp.get("response") or "").strip()
