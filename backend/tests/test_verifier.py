"""Verifier unit tests — pure Python, deterministic, no LLM needed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.models import ParsedDocument, ItemizedCharge
from app.verifier import verify

def inv(total, items=(15000, 45000, 8000, 5000), num="INV-1"):
    return ParsedDocument(filename="inv.pdf", document_type="invoice",
                          invoice_number=num, total_amount=total,
                          itemized_charges=[ItemizedCharge(description=f"item{i}", amount=a)
                                            for i, a in enumerate(items)])

def pol():
    return ParsedDocument(filename="pol.pdf", document_type="policy",
                          policy_valid_from="2026-01-01", policy_valid_to="2026-12-31",
                          coverage_limit=500000,
                          required_documents=["discharge summary", "invoice", "prescription"])

def test_totals_match():
    f = verify([pol(), inv(73000), ParsedDocument(filename="d.pdf", document_type="discharge_summary"),
                ParsedDocument(filename="p.pdf", document_type="prescription")], "T1")
    assert any(x.code.startswith("TOTAL_OK") for x in f), f

def test_mismatch_flagged():
    f = verify([pol(), inv(78000, num="INV-2")], "T2")
    assert any(x.code.startswith("TOTAL_MISMATCH") for x in f), f
    assert any(x.severity == "action_required" for x in f)

def test_missing_docs():
    f = verify([pol(), inv(73000)], "T3")
    assert any(x.code.startswith("MISSING") for x in f), f

def test_duplicates():
    f = verify([inv(100, (100,), "DUP"), inv(100, (100,), "DUP")], "T4")
    assert any(x.code.startswith("DUPLICATE") for x in f), f
