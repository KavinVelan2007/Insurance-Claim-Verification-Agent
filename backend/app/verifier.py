"""Deterministic verification engine — arithmetic & exact checks in Python.

The LLM NEVER decides outcomes. It only extracts data and quotes clauses.
All pass/fail logic here is pure Python: totals, duplicates, dates, coverage.
"""
from collections import Counter
from typing import List
from .models import ParsedDocument, Finding


def _f(code, title, severity, detail, **kw) -> Finding:
    return Finding(code=code, title=title, severity=severity, detail=detail, **kw)


def recalc_invoice(doc: ParsedDocument) -> float:
    return round(sum(c.amount for c in doc.itemized_charges), 2)


def _check_totals(invoices: List[ParsedDocument], out: List[Finding]) -> None:
    for inv in invoices:
        if inv.total_amount is None or not inv.itemized_charges:
            out.append(_f(
                f"TOTAL_UNVERIFIABLE_{(inv.invoice_number or inv.filename)[:30]}",
                "Invoice total could not be recalculated", "warning",
                f"{inv.filename}: total={'missing' if inv.total_amount is None else inv.total_amount}, "
                f"items={len(inv.itemized_charges)}. Needs human check.",
                document_ref=inv.filename, confidence=0.6,
                action="Request itemized bill or re-upload a clearer PDF."))
            continue
        calc = recalc_invoice(inv)
        if abs(calc - inv.total_amount) > 1.0:
            out.append(_f(
                f"TOTAL_MISMATCH_{(inv.invoice_number or inv.filename)[:30]}",
                "Invoice total mismatch", "action_required",
                f"{inv.filename}: stated {inv.total_amount}, items sum to {calc} "
                f"(diff {round(inv.total_amount - calc, 2)}).",
                extracted_value=str(inv.total_amount), expected_value=str(calc),
                document_ref=inv.filename, confidence=0.95,
                action="Ask hospital billing for a corrected invoice; hold payout."))
        else:
            out.append(_f(
                f"TOTAL_OK_{(inv.invoice_number or inv.filename)[:30]}",
                "Invoice total verified", "info",
                f"{inv.filename}: items sum to {calc}, matches stated {inv.total_amount}.",
                extracted_value=str(inv.total_amount), expected_value=str(calc),
                document_ref=inv.filename, confidence=0.95))


def _check_duplicates(invoices: List[ParsedDocument], out: List[Finding]) -> None:
    seen = Counter(d.invoice_number for d in invoices if d.invoice_number)
    for num, n in seen.items():
        if n > 1:
            out.append(_f(
                f"DUPLICATE_{num[:30]}", "Possible duplicate invoice", "action_required",
                f"Invoice number {num} appears {n} times. Possible double claim.",
                extracted_value=num,
                document_ref=", ".join(d.filename for d in invoices if d.invoice_number == num),
                confidence=0.9,
                action="Deduplicate; confirm with hospital which copy is valid."))


def _check_missing(documents, policy, out) -> None:
    if policy and policy.required_documents:
        present = {d.document_type for d in documents}
        known = ["policy", "invoice", "discharge_summary", "prescription",
                 "diagnostic_report", "claim_form", "other"]
        lmap = {t.lower().replace("_", " "): t for t in known}
        for req in policy.required_documents:
            key = req.lower().replace("_", " ")
            mapped = lmap.get(key)
            if mapped is None:
                words = key.split()
                if any(all(w in p.replace("_", " ") for w in words) for p in present):
                    continue
                out.append(_f(
                    "MISSING_DOC", f"Required document may be missing: {req}",
                    "action_required",
                    f"Policy lists '{req}' as required but no matching upload found.",
                    document_ref=policy.filename, policy_clause=req, confidence=0.7,
                    action=f"Request the missing document: {req}."))
            elif mapped not in present:
                out.append(_f(
                    f"MISSING_{mapped.upper()}", f"Required document missing: {mapped}",
                    "action_required",
                    f"Policy requires '{req}' but no {mapped} was uploaded.",
                    document_ref=policy.filename, policy_clause=req, confidence=0.8,
                    action=f"Request the missing document: {req}."))
    elif not policy:
        out.append(_f(
            "NO_POLICY", "No policy document uploaded", "policy_review",
            "Cannot check coverage/dates/exclusions without the policy.",
            confidence=0.9, action="Upload the policy PDF."))


def _check_dates(documents, policy, out) -> None:
    if policy and (policy.policy_valid_from or policy.policy_valid_to):
        period = f"Valid {policy.policy_valid_from} to {policy.policy_valid_to}"
        for d in documents:
            pairs = (("admission", d.admission_date), ("discharge", d.discharge_date),
                     ("invoice", d.invoice_date))
            for label, date in pairs:
                if not date:
                    continue
                if policy.policy_valid_from and date < policy.policy_valid_from:
                    out.append(_f(
                        "DATE_BEFORE", f"{label} date precedes policy start",
                        "policy_review",
                        f"{d.filename}: {label} {date} before start "
                        f"{policy.policy_valid_from}.",
                        extracted_value=date, expected_value=policy.policy_valid_from,
                        document_ref=d.filename, policy_clause=period, confidence=0.85,
                        action="Confirm policy period with insurer."))
                if policy.policy_valid_to and date > policy.policy_valid_to:
                    out.append(_f(
                        "DATE_AFTER", f"{label} date after policy expiry",
                        "policy_review",
                        f"{d.filename}: {label} {date} after end "
                        f"{policy.policy_valid_to}.",
                        extracted_value=date, expected_value=policy.policy_valid_to,
                        document_ref=d.filename, policy_clause=period, confidence=0.85,
                        action="Confirm renewal / grace period with insurer."))
    for d in documents:
        if d.admission_date and d.discharge_date and d.discharge_date < d.admission_date:
            out.append(_f(
                "DATE_ORDER", "Discharge before admission", "warning",
                f"{d.filename}: discharge {d.discharge_date} precedes admission "
                f"{d.admission_date}.",
                document_ref=d.filename, confidence=0.9,
                action="Verify dates on discharge summary."))


def _check_coverage(invoices, policy, out) -> None:
    if policy and policy.coverage_limit:
        claimed = round(sum(d.total_amount or 0 for d in invoices), 2)
        if claimed > policy.coverage_limit:
            out.append(_f(
                "COVERAGE_EXCEEDED", "Claimed amount exceeds coverage limit",
                "policy_review",
                f"Invoices total {claimed} vs limit {policy.coverage_limit}.",
                extracted_value=str(claimed), expected_value=str(policy.coverage_limit),
                document_ref=policy.filename, confidence=0.9,
                action="Apply deductible rules; escalate to senior reviewer."))
        else:
            out.append(_f(
                "COVERAGE_OK", "Within coverage limit", "info",
                f"Invoices total {claimed} within limit {policy.coverage_limit}.",
                extracted_value=str(claimed), expected_value=str(policy.coverage_limit),
                document_ref=policy.filename, confidence=0.9))


def verify(documents, claim_id: str):
    out = []
    invoices = [d for d in documents if d.document_type == "invoice"]
    policies = [d for d in documents if d.document_type == "policy"]
    policy = policies[0] if policies else None
    _check_totals(invoices, out)
    _check_duplicates(invoices, out)
    _check_missing(documents, policy, out)
    _check_dates(documents, policy, out)
    _check_coverage(invoices, policy, out)
    if not out:
        out.append(_f("CONSISTENT", "Documents look consistent", "info",
                       "Arithmetic, duplicates, dates and coverage checks all pass. "
                       "Still requires human review — never auto-approves.",
                       confidence=0.8))
    return out


