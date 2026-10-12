"""Pydantic schemas: extraction contract, findings, API inputs."""
from typing import Annotated, List, Optional, Literal
from pydantic import BaseModel, Field

DocumentType = Literal["policy", "invoice", "discharge_summary", "prescription",
                       "diagnostic_report", "claim_form", "other"]
Severity = Literal["info", "warning", "action_required", "policy_review"]
Decision = Literal["confirmed", "dismissed", "inconclusive"]
Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)]


class ItemizedCharge(BaseModel):
    description: str
    amount: float


class Extraction(BaseModel):
    """What the LLM must return (sent to Ollama as a JSON schema)."""
    document_type: DocumentType
    claim_id: Optional[str]
    patient_name: Optional[str]
    hospital_name: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    itemized_charges: List[ItemizedCharge]
    total_amount: Optional[float]
    admission_date: Optional[str]
    discharge_date: Optional[str]
    diagnosis: Optional[str]
    policy_number: Optional[str]
    policy_valid_from: Optional[str]
    policy_valid_to: Optional[str]
    coverage_limit: Optional[float]
    deductible: Optional[float]
    exclusions: List[str]
    required_documents: List[str]
    policy_clauses: List[str]
    confidence: float


class ParsedDocument(Extraction):
    """Extraction after cleaning, plus pipeline metadata. Stored as documents.data."""
    document_type: DocumentType = "other"
    claim_id: Optional[str] = None
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None       # always YYYY-MM-DD or None
    itemized_charges: List[ItemizedCharge] = Field(default_factory=list)
    total_amount: Optional[float] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    diagnosis: Optional[str] = None
    policy_number: Optional[str] = None
    policy_valid_from: Optional[str] = None
    policy_valid_to: Optional[str] = None
    coverage_limit: Optional[float] = None
    deductible: Optional[float] = None
    exclusions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    policy_clauses: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    filename: str = ""
    extraction_method: str = "text"          # text | ocr | text+ocr
    warnings: List[str] = Field(default_factory=list)


class Finding(BaseModel):
    code: str
    title: str
    severity: Severity
    detail: str
    extracted_value: Optional[str] = None
    expected_value: Optional[str] = None
    document_ref: Optional[str] = None
    policy_clause: Optional[str] = None
    confidence: float = 0.8
    action: Optional[str] = None


class SignupIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: Email
    password: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(max_length=200)


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: Email
    password: str = Field(min_length=10, max_length=200)
    role: Literal["admin", "reviewer"] = "reviewer"


class PasswordIn(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(min_length=10, max_length=200)


class ReviewIn(BaseModel):
    decision: Decision
    comment: str = Field(default="", max_length=1000)
