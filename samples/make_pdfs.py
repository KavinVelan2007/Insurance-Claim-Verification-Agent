"""Generate synthetic demo PDFs WITHOUT reportlab (minimal raw-PDF writer).

Reason: reportlab's wheel is slow to fetch here; this writer has zero deps and
PyMuPDF reads its output fine. Produces the 3 demo scenarios.
"""
from pathlib import Path

OUT = Path(__file__).parent

POLICY = ["ACME HEALTH INSURANCE - POLICY SCHEDULE (SYNTHETIC DEMO)",
 "Policy Number: POL-DEMO-2026-001", "Policyholder: Demo Patient",
 "Policy Valid From: 2026-01-01", "Policy Valid To: 2026-12-31",
 "Coverage Limit (Sum Insured): INR 500000", "Deductible: INR 10000",
 "Required Documents: discharge summary, invoice, prescription, diagnostic report, claim form",
 "Exclusions: cosmetic surgery; dental treatment unless due to accident; infertility treatment",
 "Clause 4.2: Hospitalization claims must include itemized invoice, discharge summary and prescription.",
 "Clause 7.1: Claims with treatment dates outside the policy period require renewal proof."]

INVOICE_OK = ["CITY CARE HOSPITAL - FINAL INVOICE (SYNTHETIC DEMO)", "Claim ID: CLM-DEMO-A",
 "Patient: Demo Patient", "Invoice Number: INV-2026-1001", "Invoice Date: 2026-09-20",
 "Admission Date: 2026-09-15 | Discharge Date: 2026-09-18", "Diagnosis: Acute appendicitis",
 "Room Charges: 15000.00", "Surgery Charges: 45000.00", "Pharmacy: 8000.00",
 "Diagnostics: 5000.00", "Total: 73000.00"]

INVOICE_BAD = ["CITY CARE HOSPITAL - FINAL INVOICE (SYNTHETIC DEMO)", "Claim ID: CLM-DEMO-B",
 "Patient: Demo Patient", "Invoice Number: INV-2026-1002", "Invoice Date: 2026-09-20",
 "Admission Date: 2026-09-15 | Discharge Date: 2026-09-18", "Diagnosis: Acute appendicitis",
 "Room Charges: 15000.00", "Surgery Charges: 45000.00", "Pharmacy: 8000.00",
 "Diagnostics: 5000.00", "Total: 78000.00",
 "(items sum to 73000.00 - deliberate mismatch for demo B)"]

DISCHARGE = ["CITY CARE HOSPITAL - DISCHARGE SUMMARY (SYNTHETIC DEMO)", "Claim ID: CLM-DEMO-A",
 "Patient: Demo Patient | Hospital: City Care Hospital",
 "Admission Date: 2026-09-15 | Discharge Date: 2026-09-18",
 "Diagnosis: Acute appendicitis, laparoscopic appendectomy performed.",
 "Advised: antibiotics, review after 7 days."]

PRESCRIPTION = ["CITY CARE HOSPITAL - PRESCRIPTION (SYNTHETIC DEMO)", "Claim ID: CLM-DEMO-A",
 "Patient: Demo Patient | Date: 2026-09-18",
 "Rx: Amoxicillin 500mg 1-1-1 x 5 days; Paracetamol as needed."]

DIAG = ["CITY CARE LAB - DIAGNOSTIC REPORT (SYNTHETIC DEMO)",
 "Patient: Demo Patient | Date: 2026-09-15",
 "Test: CBC - WBC elevated, consistent with infection."]

CLAIMFORM = ["ACME HEALTH INSURANCE - CLAIM FORM (SYNTHETIC DEMO)",
 "Claim ID: CLM-DEMO-A", "Patient: Demo Patient",
 "Hospital: City Care Hospital", "Treatment Dates: 2026-09-15 to 2026-09-18",
 "Claimed Amount: INR 73000", "Signature: Demo Patient"]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, title: str, lines):
    content = [f"BT /F1 13 Tf 50 800 Td ({_esc(title)}) Tj ET"]
    y = 775
    ops = [f"BT /F1 13 Tf 50 800 Td ({_esc(title)}) Tj ET"]
    for ln in lines:
        y -= 18
        if y < 50:
            break
        ops.append(f"BT /F1 10 Tf 50 {y} Td ({_esc(ln)[:110]}) Tj ET")
    stream = "\n".join(ops).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    pdf = [b"%PDF-1.4"]
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(sum(len(x) + 1 for x in pdf))
        pdf.append(b"%d 0 obj\n" % i + body + b"\nendobj")
    xref = sum(len(x) + 1 for x in pdf)
    pdf.append(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) +
               b"".join(b"%010d 00000 n \n" % o for o in offsets))
    pdf.append(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref))
    path.write_bytes(b"\n".join(pdf))
    print("wrote", path.name, len(path.read_bytes()), "bytes")


SCEN = {"policy_A.pdf": ("POLICY SCHEDULE", POLICY),
        "invoice_A.pdf": ("INVOICE INV-2026-1001", INVOICE_OK),
        "invoice_B_mismatch.pdf": ("INVOICE INV-2026-1002", INVOICE_BAD),
        "discharge_A.pdf": ("DISCHARGE SUMMARY", DISCHARGE),
        "prescription_A.pdf": ("PRESCRIPTION", PRESCRIPTION),
        "diagnostic_A.pdf": ("DIAGNOSTIC REPORT", DIAG),
        "claimform_A.pdf": ("CLAIM FORM", CLAIMFORM)}
if __name__ == "__main__":
    for n, (t, lines) in SCEN.items():
        write_pdf(OUT / n, t, lines)
    print("OK: A=policy_A+invoice_A+discharge_A+prescription_A consistent; "
          "B=policy_A+invoice_B_mismatch+discharge_A mismatch; C=policy_A+invoice_A missing-docs.")
