"""Deterministic verification. The LLM never decides outcomes; every check here is
plain Python over the cleaned extraction (dates are already ISO, money is float).

Finding codes are derived from content (not order), so the same claim always
yields the same codes.
"""
import re
from collections import Counter
from typing import Dict, List, Optional

from .models import Finding, ParsedDocument

LOW_CONFIDENCE = 0.6
# Policy wording for required documents -> our document types.
REQUIRED_ALIASES = {
    "invoice": "invoice", "bill": "invoice", "hospital bill": "invoice", "final bill": "invoice",
    "itemized bill": "invoice", "itemised bill": "invoice", "itemized invoice": "invoice",
    "discharge summary": "discharge_summary", "discharge card": "discharge_summary",
    "prescription": "prescription", "prescriptions": "prescription",
    "diagnostic report": "diagnostic_report", "diagnostic reports": "diagnostic_report",
    "lab report": "diagnostic_report", "lab reports": "diagnostic_report",
    "investigation report": "diagnostic_report", "investigation reports": "diagnostic_report",
    "claim form": "claim_form", "policy": "policy", "policy document": "policy",
}
_TITLES = re.compile(r"\b(mr|mrs|ms|miss|dr|shri|smt|kumari)\b\.?")


def _slug(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")[:40] or "X"


def _money(x: float) -> str:
    return f"{x:,.2f}"


def _name(s: Optional[str]) -> str:
    return " ".join(_TITLES.sub(" ", re.sub(r"[^a-z\s.]", " ", (s or "").lower())).replace(".", " ").split())


def recalc_invoice(doc: ParsedDocument) -> float:
    return round(sum(c.amount for c in doc.itemized_charges), 2)


def _totals(invoices, out):
    for inv in invoices:
        ref = _slug(inv.invoice_number or inv.filename)
        if inv.total_amount is None or not inv.itemized_charges:
            out.append(Finding(
                code=f"TOTAL_UNVERIFIABLE:{ref}", title="Invoice total could not be recalculated",
                severity="warning",
                detail=f"{inv.filename}: total {'missing' if inv.total_amount is None else _money(inv.total_amount)}, "
                       f"{len(inv.itemized_charges)} itemized charges found.",
                document_ref=inv.filename, confidence=0.6,
                action="Request an itemized bill or check the invoice manually."))
            continue
        calc = recalc_invoice(inv)
        diff = round(inv.total_amount - calc, 2)
        ok = abs(diff) <= 1.0
        out.append(Finding(
            code=f"TOTAL_{'OK' if ok else 'MISMATCH'}:{ref}",
            title="Invoice total verified" if ok else "Invoice total does not match its line items",
            severity="info" if ok else "action_required",
            detail=(f"{inv.filename}: {len(inv.itemized_charges)} line items sum to {_money(calc)}, "
                    + ("matching the stated total." if ok else
                       f"but the stated total is {_money(inv.total_amount)} (difference {_money(diff)}).")),
            extracted_value=str(inv.total_amount), expected_value=str(calc),
            document_ref=inv.filename, confidence=0.95,
            action=None if ok else "Ask the hospital for a corrected invoice before settlement."))


def _duplicates(invoices, prior_invoices: Dict[str, str], out):
    for num, n in Counter(d.invoice_number for d in invoices if d.invoice_number).items():
        if n > 1:
            out.append(Finding(
                code=f"DUPLICATE_INVOICE:{_slug(num)}", title="Same invoice uploaded more than once",
                severity="action_required",
                detail=f"Invoice {num} appears {n} times in this claim; it may be counted twice.",
                extracted_value=num,
                document_ref=", ".join(d.filename for d in invoices if d.invoice_number == num),
                confidence=0.9, action="Keep one copy and confirm the claimed amount."))
    for d in invoices:
        if d.invoice_number and d.invoice_number in prior_invoices:
            out.append(Finding(
                code=f"PRIOR_INVOICE:{_slug(d.invoice_number)}", title="Invoice already submitted in another claim",
                severity="action_required",
                detail=f"Invoice {d.invoice_number} was also submitted with claim {prior_invoices[d.invoice_number]}.",
                extracted_value=d.invoice_number, document_ref=d.filename, confidence=0.9,
                action="Check the earlier claim before processing this one."))


def _missing(documents, policy, out):
    if not policy:
        out.append(Finding(
            code="NO_POLICY", title="No policy document uploaded", severity="policy_review",
            detail="Coverage limits, policy period, exclusions and required documents cannot be checked.",
            confidence=0.9, action="Upload the policy schedule or wording."))
        return
    present = {d.document_type for d in documents}
    for req in policy.required_documents:
        key = " ".join(req.lower().replace("_", " ").split())
        kind = REQUIRED_ALIASES.get(key)
        if kind is None:
            out.append(Finding(
                code=f"REQUIRED_UNKNOWN:{_slug(req)}", title=f"Check manually: {req}", severity="warning",
                detail=f"The policy requires '{req}', which Kaagaz cannot recognise automatically.",
                document_ref=policy.filename, policy_clause=req, confidence=0.5,
                action=f"Confirm that '{req}' is included."))
        elif kind not in present:
            out.append(Finding(
                code=f"MISSING:{kind.upper()}", title=f"Required document missing: {req}",
                severity="action_required",
                detail=f"The policy requires '{req}', but none of the uploaded documents is one.",
                document_ref=policy.filename, policy_clause=req, confidence=0.8,
                action=f"Request the {req} from the claimant."))


def _dates(documents, policy, out):
    for d in documents:
        if d.admission_date and d.discharge_date and d.discharge_date < d.admission_date:
            out.append(Finding(
                code=f"DATE_ORDER:{_slug(d.filename)}", title="Discharge date is before admission",
                severity="warning",
                detail=f"{d.filename}: admitted {d.admission_date}, discharged {d.discharge_date}.",
                document_ref=d.filename, confidence=0.9, action="Verify dates on the discharge summary."))
    if not policy or not (policy.policy_valid_from or policy.policy_valid_to):
        return
    period = f"Policy period {policy.policy_valid_from or '?'} to {policy.policy_valid_to or '?'}"
    for d in documents:
        if d.document_type == "policy":
            continue
        for label, when in (("admission", d.admission_date), ("discharge", d.discharge_date),
                            ("invoice", d.invoice_date)):
            if not when:
                continue
            for kind, bound, outside in (("BEFORE", policy.policy_valid_from, lambda w, b: w < b),
                                         ("AFTER", policy.policy_valid_to, lambda w, b: w > b)):
                if bound and outside(when, bound):
                    out.append(Finding(
                        code=f"DATE_{kind}:{label.upper()}:{_slug(d.filename)}",
                        title=f"{label.capitalize()} date is {'before the policy starts' if kind == 'BEFORE' else 'after the policy ends'}",
                        severity="policy_review",
                        detail=f"{d.filename}: {label} date {when}; {period.lower()}.",
                        extracted_value=when, expected_value=bound, document_ref=d.filename,
                        policy_clause=period, confidence=0.85,
                        action="Confirm the policy period, renewal or grace period with the insurer."))


def _coverage(invoices, policy, out):
    if not policy or not policy.coverage_limit:
        return
    claimed = round(sum(d.total_amount or 0 for d in invoices), 2)
    over = claimed > policy.coverage_limit
    ded = f" A deductible of {_money(policy.deductible)} applies." if policy.deductible else ""
    out.append(Finding(
        code="COVERAGE_EXCEEDED" if over else "COVERAGE_OK",
        title="Claimed amount exceeds the coverage limit" if over else "Claimed amount is within the coverage limit",
        severity="policy_review" if over else "info",
        detail=f"Invoices total {_money(claimed)} against a limit of {_money(policy.coverage_limit)}.{ded}",
        extracted_value=str(claimed), expected_value=str(policy.coverage_limit),
        document_ref=policy.filename, confidence=0.9,
        action="Escalate to a senior reviewer for the payable amount." if over else None))


def _exclusions(documents, policy, out):
    if not policy:
        return
    texts = [(d.filename, t.lower()) for d in documents if d.document_type != "policy"
             for t in [d.diagnosis or ""] + [c.description for c in d.itemized_charges] if t]
    for ex in policy.exclusions:
        # Match the excluded condition itself, not its conditions ("dental treatment unless ...").
        phrase = re.split(r"\b(unless|except|other than|if)\b|[(:;]", ex.lower())[0].strip(" .,-")
        if len(phrase) < 5:
            continue
        hits = sorted({f for f, t in texts if phrase in t})
        if hits:
            out.append(Finding(
                code=f"EXCLUSION:{_slug(phrase)}", title=f"Possible excluded treatment: {phrase}",
                severity="policy_review",
                detail=f"'{phrase}' appears in {', '.join(hits)} and the policy lists it as an exclusion.",
                document_ref=", ".join(hits), policy_clause=ex, confidence=0.7,
                action="Read the exclusion wording and the treatment notes before deciding."))


def _consistency(documents, out):
    ids = sorted({d.claim_id.strip() for d in documents if d.claim_id})
    if len(ids) > 1:
        out.append(Finding(
            code="CLAIM_ID_MISMATCH", title="Documents reference different claim numbers", severity="warning",
            detail=f"Claim numbers found: {', '.join(ids)}. The upload may mix documents from different claims.",
            extracted_value=", ".join(ids),
            document_ref=", ".join(d.filename for d in documents if d.claim_id), confidence=0.9,
            action="Confirm which claim these documents belong to."))
    names = {}
    for d in documents:
        if d.patient_name and _name(d.patient_name):
            names.setdefault(_name(d.patient_name), []).append(d)
    if len(names) > 1:
        out.append(Finding(
            code="PATIENT_MISMATCH", title="Patient name differs across documents", severity="warning",
            detail="; ".join(f"{v[0].patient_name} ({', '.join(x.filename for x in v)})" for v in names.values()),
            extracted_value=", ".join(v[0].patient_name for v in names.values()), confidence=0.8,
            action="Check whether these are spelling variants of one person or different patients."))


def _quality(documents, out):
    for d in documents:
        if d.confidence < LOW_CONFIDENCE or any("skipped" in w for w in d.warnings):
            out.append(Finding(
                code=f"LOW_CONFIDENCE:{_slug(d.filename)}", title="Low-confidence extraction",
                severity="warning",
                detail=f"{d.filename} was read with {round(d.confidence * 100)}% confidence ({d.extraction_method}). "
                       "Values from it may be wrong." + (" " + " ".join(d.warnings) if d.warnings else ""),
                document_ref=d.filename, confidence=d.confidence,
                action="Compare the extracted fields with the original PDF."))


def verify(documents: List[ParsedDocument], prior_invoices: Optional[Dict[str, str]] = None) -> List[Finding]:
    """prior_invoices: invoice number -> claim ref, for invoices in this org's other claims."""
    out: List[Finding] = []
    invoices = [d for d in documents if d.document_type == "invoice"]
    policy = next((d for d in documents if d.document_type == "policy"), None)
    _quality(documents, out)
    _totals(invoices, out)
    _duplicates(invoices, prior_invoices or {}, out)
    _missing(documents, policy, out)
    _dates(documents, policy, out)
    _coverage(invoices, policy, out)
    _exclusions(documents, policy, out)
    _consistency(documents, out)
    seen = Counter()  # codes are unique per claim (DB constraint); suffix any accidental repeat
    for f in out:
        seen[f.code] += 1
        if seen[f.code] > 1:
            f.code = f"{f.code}#{seen[f.code]}"
    return out


def overall_status(findings: List[Finding]) -> str:
    sev = {f.severity for f in findings}
    if "action_required" in sev:
        return "incomplete"
    return "needs_review" if sev & {"warning", "policy_review"} else "consistent"
