"""PDF -> ParsedDocument: PyMuPDF text layer, scanned pages rendered to images,
one vision-LLM call per document, then deterministic cleaning (types, dates,
invoice-only money)."""
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

from . import llm
from .config import settings
from .models import ParsedDocument, ItemizedCharge

SCANNED_CHARS = 50   # a page with less extractable text than this is treated as an image
IMAGE_DPI = 150      # legible for bills at A4; higher only adds image tokens
DOC_TYPES = {"policy", "invoice", "discharge_summary", "prescription",
             "diagnostic_report", "claim_form", "other"}
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
                 "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d")


def page_count(pdf: bytes) -> int:
    """Validates the PDF (raises ValueError) and returns its page count."""
    if pdf[:5] != b"%PDF-":
        raise ValueError("not a PDF file")
    try:
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            locked, n = doc.needs_pass, doc.page_count
    except Exception as e:
        raise ValueError("unreadable or corrupt PDF") from e
    if locked:
        raise ValueError("PDF is password-protected")
    if n == 0:
        raise ValueError("PDF has no pages")
    return n


def read_pages(pdf: bytes) -> Tuple[str, List[bytes], str, List[str]]:
    """Returns (text, scanned_page_jpegs, method, warnings). Digital pages contribute
    their text layer; image-only pages are rendered for the vision model."""
    parts, images, warns = [], [], []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            t = page.get_text("text") or ""
            if len(t.strip()) >= SCANNED_CHARS:
                parts.append(f"[page {i + 1}]\n{t}")
            elif len(images) < settings.max_image_pages:
                images.append(page.get_pixmap(dpi=IMAGE_DPI).tobytes("jpeg", jpg_quality=80))
                parts.append(f"[page {i + 1}: scanned, see image {len(images)}]")
            else:
                warns.append(f"Page {i + 1} is scanned but over the {settings.max_image_pages}-image limit; it was not read.")
    method = "vision" if images and len(images) == len(parts) else ("text+vision" if images else "text")
    return "\n\n".join(parts), images, method, warns


def iso_date(v: Any) -> Optional[str]:
    """Normalise to YYYY-MM-DD; None when unparseable (day-first, Indian convention)."""
    if not v:
        return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(v).strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").replace("₹", "").replace("INR", "").strip())
    except ValueError:
        return None


def _strs(v: Any) -> List[str]:
    vals = v if isinstance(v, list) else [v]
    return [str(x).strip()[:1000] for x in vals if x is not None and str(x).strip()]


def _s(v: Any) -> Optional[str]:
    return str(v).strip()[:300] or None if v is not None else None


def clean(data: Dict[str, Any], filename: str, method: str, warns: List[str]) -> ParsedDocument:
    """Make LLM output safe for the verifier: right types, ISO dates, invoice-only money."""
    warns = list(warns)
    dt = data.get("document_type") if data.get("document_type") in DOC_TYPES else "other"
    items: List[ItemizedCharge] = []
    total = _num(data.get("total_amount"))
    if dt == "invoice":
        for c in data.get("itemized_charges") or []:
            if not isinstance(c, dict):
                continue
            desc, amt = str(c.get("description") or "").strip()[:200], _num(c.get("amount"))
            if desc and amt is not None:
                items.append(ItemizedCharge(description=desc, amount=amt))
    else:
        total = None  # the LLM sometimes reads claimed amounts off claim forms as invoice totals
    dates = {}
    for k in ("invoice_date", "admission_date", "discharge_date", "policy_valid_from", "policy_valid_to"):
        raw = data.get(k)
        dates[k] = iso_date(raw)
        if raw and not dates[k]:
            warns.append(f"Could not read {k.replace('_', ' ')} '{raw}'.")
    conf = _num(data.get("confidence"))
    return ParsedDocument(
        filename=filename, document_type=dt, extraction_method=method, warnings=warns,
        claim_id=_s(data.get("claim_id")), patient_name=_s(data.get("patient_name")),
        hospital_name=_s(data.get("hospital_name")), invoice_number=_s(data.get("invoice_number")),
        diagnosis=_s(data.get("diagnosis")), policy_number=_s(data.get("policy_number")),
        itemized_charges=items, total_amount=total,
        coverage_limit=_num(data.get("coverage_limit")), deductible=_num(data.get("deductible")),
        exclusions=_strs(data.get("exclusions") or []),
        required_documents=_strs(data.get("required_documents") or []),
        policy_clauses=_strs(data.get("policy_clauses") or []),
        confidence=max(0.0, min(1.0, conf if conf is not None else 0.5)),
        **dates)


def parse_pdf(pdf: bytes, filename: str) -> ParsedDocument:
    text, images, method, warns = read_pages(pdf)
    if not images and len(re.sub(r"\[page \d+\]", "", text).strip()) == 0:
        return ParsedDocument(filename=filename, extraction_method=method, confidence=0.0,
                              warnings=warns + ["No readable content found."])
    doc = clean(llm.extract(text, images, filename), filename, method, warns)
    if method != "text":
        # Read from page images: good but not certain; never report above 0.8.
        doc.confidence = min(doc.confidence, 0.8)
    return doc
