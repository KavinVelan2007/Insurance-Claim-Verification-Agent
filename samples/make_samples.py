"""Generate 3 synthetic demo scenarios as PDFs (reportlab). No real PHI."""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pathlib import Path

OUT = Path(__file__).parent
W, H = A4

POLICY = """ACME HEALTH INSURANCE — POLICY SCHEDULE (SYNTHETIC DEMO)
Policy Number: POL-DEMO-2026-001
Policyholder: Demo Patient
Policy Valid From: 2026-01-01
Policy Valid To: 2026-12-31
Coverage Limit (Sum Insured): INR 500000
Deductible: INR 10000
Required Documents: discharge summary, invoice, prescription, diagnostic report, claim form
Exclusions: cosmetic surgery; dental treatment unless due to accident; infertility treatment
Clause 4.2: Hospitalization claims must include itemized invoice, discharge summary and prescription.
Clause 7.1: Claims with treatment dates outside the policy period require renewal proof.
"""

INVOICE_OK = """CITY CARE HOSPITAL — FINAL INVOICE (SYNTHETIC DEMO)
Claim ID: CLM-DEMO-A
Patient: Demo Patient
Invoice Number: INV-2026-1001
Invoice Date: 2026-09-20
Admission Date: 2026-09-15 | Discharge Date: 2026-09-18
Diagnosis: Acute appendicitis
Room Charges: 15000.00
Surgery Charges: 45000.00
Pharmacy: 8000.00
Diagnostics: 5000.00
Total: 73000.00
"""

INVOICE_BAD = """CITY CARE HOSPITAL — FINAL INVOICE (SYNTHETIC DEMO)
Claim ID: CLM-DEMO-B
Patient: Demo Patient
Invoice Number: INV-2026-1002
Invoice Date: 2026-09-20
Admission Date: 2026-09-15 | Discharge Date: 2026-09-18
Diagnosis: Acute appendicitis
Room Charges: 15000.00
Surgery Charges: 45000.00
Pharmacy: 8000.00
Diagnostics: 5000.00
Total: 78000.00
(items sum to 73000.00 — deliberate mismatch for demo B)
"""

DISCHARGE = """CITY CARE HOSPITAL — DISCHARGE SUMMARY (SYNTHETIC DEMO)
Claim ID: CLM-DEMO-A
Patient: Demo Patient | Hospital: City Care Hospital
Admission Date: 2026-09-15 | Discharge Date: 2026-09-18
Diagnosis: Acute appendicitis, laparoscopic appendectomy performed.
Advised: antibiotics, review after 7 days.
"""

PRESCRIPTION = """CITY CARE HOSPITAL — PRESCRIPTION (SYNTHETIC DEMO)
Claim ID: CLM-DEMO-A
Patient: Demo Patient | Date: 2026-09-18
Rx: Amoxicillin 500mg 1-1-1 x 5 days; Paracetamol as needed.
"""

DIAG = """CITY CARE LAB — DIAGNOSTIC REPORT (SYNTHETIC DEMO)
Patient: Demo Patient | Date: 2026-09-15
Test: CBC — WBC elevated, consistent with infection.
"""


def write(name: str, text: str):
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    y = H - 60
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, name.replace(".pdf", "").replace("_", " ").upper())
    y -= 26
    c.setFont("Helvetica", 10.5)
    for line in text.splitlines():
        if y < 60:
            c.showPage(); c.setFont("Helvetica", 10.5); y = H - 60
        c.drawString(50, y, line[:105]); y -= 15
    c.save()
    print("wrote", name)


SCENARIOS = {
    "policy_A.pdf": POLICY,
    "invoice_A.pdf": INVOICE_OK,
    "invoice_B_mismatch.pdf": INVOICE_BAD,
    "discharge_A.pdf": DISCHARGE,
    "prescription_A.pdf": PRESCRIPTION,
    "diagnostic_A.pdf": DIAG,
}
if __name__ == "__main__":
    for n, t in SCENARIOS.items():
        write(n, t)
    print("Scenarios: A=policy_A+invoice_A+discharge_A+prescription_A (+diagnostic_A) consistent; "
          "B=policy_A+invoice_B_mismatch+discharge_A mismatch; C=policy_A+invoice_A missing-docs.")
