"""Regex fallback — used ONLY when the LLM returns unparsable output."""
import re
from typing import Dict, Any, List


def fallback_parse(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"confidence": 0.35, "warnings": ["LLM output invalid; regex fallback used."]}
    low = text.lower()
    if "policy" in low and ("coverage" in low or "exclusion" in low):
        out["document_type"] = "policy"
    elif "invoice" in low or "amount" in low:
        out["document_type"] = "invoice"
    elif "discharge" in low:
        out["document_type"] = "discharge_summary"
    elif "prescription" in low or "rx" in low:
        out["document_type"] = "prescription"
    elif "lab" in low or "report" in low or "test" in low:
        out["document_type"] = "diagnostic_report"
    else:
        out["document_type"] = "other"
    m = re.search(r"(?:invoice\s*(?:no|number|#)?\s*[:\-]?\s*)([A-Z0-9\-/]{3,30})", text, re.I)
    if m:
        out["invoice_number"] = m.group(1).strip()
    totals = [float(x.replace(",", "")) for x in
              re.findall(r"(?:total|grand total|net payable|amount payable)\s*[:\-]?\s*(?:rs\.?|inr)?\s*([\d,]+\.?\d*)", text, re.I)]
    if totals:
        out["total_amount"] = totals[-1]
    items: List[Dict[str, Any]] = []
    for mm in re.finditer(r"^(.{3,60}?)\s{2,}([\d,]+\.\d{2}|\d+)\s*$", text, re.M):
        try:
            items.append({"description": mm.group(1).strip(),
                          "amount": float(mm.group(2).replace(",", ""))})
        except ValueError:
            pass
    if items:
        out["itemized_charges"] = items[:50]
    dates = re.findall(r"(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})", text)
    if dates:
        out["invoice_date"] = dates[0]
    m2 = re.search(r"(?:policy\s*(?:no|number)?\s*[:\-]?\s*)([A-Z0-9\-/]{4,30})", text, re.I)
    if m2:
        out["policy_number"] = m2.group(1).strip()
    lim = re.search(r"(?:coverage|sum insured|limit)\s*[:\-]?\s*(?:rs\.?|inr)?\s*([\d,]+)", text, re.I)
    if lim:
        try:
            out["coverage_limit"] = float(lim.group(1).replace(",", ""))
        except ValueError:
            pass
    return out
