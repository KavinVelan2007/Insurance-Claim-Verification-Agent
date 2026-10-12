"""Pure-Python tests: verifier, extraction cleaning, auth. No DB or LLM needed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.models import ParsedDocument, ItemizedCharge
from app.verifier import verify, overall_status
from app.pipeline import clean, iso_date
from app import auth
from app.llm import SCHEMA


def inv(total, items=(15000, 45000, 8000, 5000), num="INV-1", fn="inv.pdf", **kw):
    return ParsedDocument(filename=fn, document_type="invoice", invoice_number=num, total_amount=total,
                          itemized_charges=[ItemizedCharge(description=f"item{i}", amount=a) for i, a in enumerate(items)],
                          confidence=0.9, **kw)


def pol(**kw):
    base = dict(filename="pol.pdf", document_type="policy", policy_valid_from="2026-01-01",
                policy_valid_to="2026-12-31", coverage_limit=500000, confidence=0.9,
                required_documents=["discharge summary", "invoice", "prescription"])
    return ParsedDocument(**{**base, **kw})


def doc(t, **kw):
    return ParsedDocument(filename=f"{t}.pdf", document_type=t, confidence=0.9, **kw)


def codes(f):
    return [x.code for x in f]


def test_consistent_claim():
    f = verify([pol(), inv(73000), doc("discharge_summary"), doc("prescription")])
    assert "TOTAL_OK:INV_1" in codes(f) and "COVERAGE_OK" in codes(f)
    assert overall_status(f) == "consistent", f


def test_total_mismatch():
    f = verify([pol(), inv(78000)])
    assert "TOTAL_MISMATCH:INV_1" in codes(f)
    assert overall_status(f) == "incomplete"


def test_missing_and_unknown_required():
    f = verify([pol(required_documents=["discharge summary", "Cancelled cheque"]), inv(73000)])
    assert "MISSING:DISCHARGE_SUMMARY" in codes(f)
    assert "REQUIRED_UNKNOWN:CANCELLED_CHEQUE" in codes(f)


def test_duplicate_and_prior_invoice():
    f = verify([inv(100, (100,), "DUP", "a.pdf"), inv(100, (100,), "DUP", "b.pdf")], {"DUP": "CLM-9"})
    assert "DUPLICATE_INVOICE:DUP" in codes(f) and "PRIOR_INVOICE:DUP" in codes(f)
    assert len(codes(f)) == len(set(codes(f)))


def test_dates_outside_policy():
    f = verify([pol(), inv(73000, admission_date="2025-12-30", discharge_date="2026-01-02")])
    assert "DATE_BEFORE:ADMISSION:INV_PDF" in codes(f)


def test_exclusion_and_patient_mismatch():
    f = verify([pol(exclusions=["Cosmetic surgery unless after an accident"]),
                doc("discharge_summary", diagnosis="Cosmetic surgery of nose", patient_name="Mrs. Asha Verma"),
                inv(73000, patient_name="asha  verma"), doc("prescription", patient_name="Ravi Kumar")])
    assert "EXCLUSION:COSMETIC_SURGERY" in codes(f)
    assert "PATIENT_MISMATCH" in codes(f)
    assert "Asha" in next(x for x in f if x.code == "PATIENT_MISMATCH").detail


def test_codes_stable_across_order():
    a = [pol(), inv(78000), doc("discharge_summary")]
    assert sorted(codes(verify(a))) == sorted(codes(verify(a[::-1])))


def test_iso_date():
    assert iso_date("2026-09-15") == "2026-09-15"
    assert iso_date("15/09/2026") == "2026-09-15"
    assert iso_date("15th Sep 2026") == "2026-09-15"
    assert iso_date("next tuesday") is None


def test_clean_drops_non_invoice_money_and_bad_values():
    d = clean({"document_type": "claim_form", "total_amount": "78,000", "itemized_charges": [{"description": "x", "amount": 1}],
               "admission_date": "15-09-2026", "discharge_date": "garbage", "confidence": "high"}, "c.pdf", "text", [])
    assert d.total_amount is None and d.itemized_charges == []
    assert d.admission_date == "2026-09-15" and d.discharge_date is None
    assert any("discharge date" in w for w in d.warnings)
    i = clean({"document_type": "invoice", "total_amount": "₹78,000.50",
               "itemized_charges": [{"description": "Room", "amount": "1,000"}, {"description": "", "amount": 5}]}, "i.pdf", "ocr", [])
    assert i.total_amount == 78000.5 and [c.amount for c in i.itemized_charges] == [1000.0]


def test_password_and_token():
    settings.secret_key = "x" * 40
    h = auth.hash_password("correct horse battery")
    assert auth.check_password("correct horse battery", h) and not auth.check_password("wrong", h)
    t = auth.make_token(7, now=1000)
    assert auth.read_token(t, now=1001) == 7
    assert auth.read_token(t, now=1000 + settings.session_hours * 3600 + 1) is None
    assert auth.read_token(t[:-2] + "aa", now=1001) is None


def test_llm_schema_is_strict():
    objs = [SCHEMA] + list(SCHEMA.get("$defs", {}).values())
    for o in objs:
        assert o["additionalProperties"] is False and set(o["required"]) == set(o["properties"]), o.get("title")
