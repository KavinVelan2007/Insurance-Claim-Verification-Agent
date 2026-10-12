"""Orchestration: validate -> PyMuPDF -> optional VLM OCR -> LLM -> JSON."""
from typing import Tuple
from .models import ParsedDocument, ItemizedCharge
from .extractor import extract_pages, is_pdf, png_to_b64
from . import llm as llm_mod
from .fallback import fallback_parse
from .config import settings


def _clean_str_list(data: dict, key: str, warns: list) -> list:
    vals = data.get(key) or []
    if not isinstance(vals, list):
        vals = [vals]
    kept = [str(v).strip() for v in vals if str(v or "").strip()]
    if len(kept) != len(vals):
        warns.append(f"Dropped {len(vals) - len(kept)} empty entries from {key}.")
    return kept


def _coerce(data: dict, filename: str, method: str, chars: int) -> ParsedDocument:
    warns = data.get("warnings") or []
    if not isinstance(warns, list):
        warns = [str(warns)]
    allowed = {"policy", "invoice", "discharge_summary", "prescription",
               "diagnostic_report", "claim_form", "other"}
    dt = data.get("document_type") or "other"
    if dt not in allowed:
        dt = "other"
        warns.append(f"Unknown document_type '{data.get('document_type')}' -> other.")
    # Only invoices carry charges/totals — the LLM sometimes leaks them
    # (e.g. drug names as charges, claimed amounts as totals) elsewhere.
    items = []
    if dt == "invoice":
        for c in data.get("itemized_charges") or []:
            try:
                c = c or {}
                desc = str(c.get("description", "")).strip()[:200]
                amt = float(c.get("amount", 0) or 0)
            except (ValueError, TypeError, AttributeError):
                continue
            if not desc:
                continue
            items.append(ItemizedCharge(description=desc, amount=amt))
    elif data.get("itemized_charges"):
        warns.append("Dropped itemized charges on non-invoice document.")
    try:
        conf = float(data.get("confidence", 0.6) or 0.0)
    except (ValueError, TypeError):
        conf, warns = 0.4, warns + ["Bad confidence value."]
    conf = max(0.0, min(1.0, conf))
    clean = {}
    for k in ("total_amount", "coverage_limit", "deductible"):
        v = data.get(k)
        try:
            clean[k] = None if v is None else float(v)
        except (ValueError, TypeError):
            clean[k] = None
            warns.append(f"Ignored non-numeric {k}={v!r}.")
    if dt != "invoice" and clean["total_amount"] is not None:
        warns.append("Dropped total_amount on non-invoice document.")
        clean["total_amount"] = None
    return ParsedDocument(
        filename=filename, document_type=dt,  # type: ignore
        claim_id=data.get("claim_id"), patient_name=data.get("patient_name"),
        hospital_name=data.get("hospital_name"),
        invoice_number=data.get("invoice_number"), invoice_date=data.get("invoice_date"),
        itemized_charges=items, total_amount=clean["total_amount"],
        currency=data.get("currency") or "INR",
        admission_date=data.get("admission_date"),
        discharge_date=data.get("discharge_date"), diagnosis=data.get("diagnosis"),
        policy_number=data.get("policy_number"),
        policy_valid_from=data.get("policy_valid_from"),
        policy_valid_to=data.get("policy_valid_to"),
        coverage_limit=clean["coverage_limit"], deductible=clean["deductible"] or 0.0,
        exclusions=_clean_str_list(data, "exclusions", warns),
        required_documents=_clean_str_list(data, "required_documents", warns),
        policy_clauses=_clean_str_list(data, "policy_clauses", warns),
        confidence=conf, extraction_method=method, warnings=warns,
        raw_text_chars=chars)
