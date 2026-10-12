"""Pydantic schemas — the structured JSON contract for parsing + verification."""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

DocumentType = Literal[
    "policy", "invoice", "discharge_summary", "prescription",
    "diagnostic_report", "claim_form", "other",
]

FindingSeverity = Literal["info", "warning", "action_required", "policy_review"]


class ItemizedCharge(BaseModel):
    description: str = ""
    amount: float = 0.0


class ParsedDocument(BaseModel):
    filename: str = ""
    document_type: DocumentType = "other"
    # claim / patient / hospital
    claim_id: Optional[str] = None
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None  # YYYY-MM-DD when known
    itemized_charges: List[ItemizedCharge] = Field(default_factory=list)
    total_amount: Optional[float] = None
    currency: str = "INR"
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    # policy fields (populated mainly for policy docs)
    policy_number: Optional[str] = None
    policy_valid_from: Optional[str] = None
    policy_valid_to: Optional[str] = None
    coverage_limit: Optional[float] = None
    deductible: Optional[float] = 0.0
    exclusions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    policy_clauses: List[str] = Field(default_factory=list)
    # extraction meta
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: str = "text+llm"  # text+llm | vlm+llm | regex-fallback | failed
    warnings: List[str] = Field(default_factory=list)
    raw_text_chars: int = 0


class ParseResponse(BaseModel):
    documents: List[ParsedDocument]
    model_used: str = ""
    pipeline: str = "pymupdf+ollama-llm"


class Finding(BaseModel):
    code: str
    title: str
    severity: FindingSeverity
    detail: str
    extracted_value: Optional[str] = None
    expected_value: Optional[str] = None
    document_ref: Optional[str] = None
    policy_clause: Optional[str] = None
    confidence: float = 0.8
    action: Optional[str] = None


class VerificationReport(BaseModel):
    claim_id: str
    status: Literal["consistent", "needs_review", "incomplete"] = "needs_review"
    findings: List[Finding] = Field(default_factory=list)
    documents: List[ParsedDocument] = Field(default_factory=list)
    totals_recalculated: Dict[str, Any] = Field(default_factory=dict)
    audit_id: Optional[int] = None


class ReviewInput(BaseModel):
    audit_id: int
    finding_code: str
    decision: Literal["confirmed", "dismissed", "inconclusive"]
    comment: str = ""
    reviewer: str = "reviewer"
