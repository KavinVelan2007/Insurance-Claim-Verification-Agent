"""One-command demo: runs all 3 scenarios through /api/verify (needs backend+Ollama)."""
import json, sys, urllib.request
from pathlib import Path

PORT = 8002
SETS = {
    "A (consistent)": ["samples/policy_A.pdf", "samples/invoice_A.pdf",
                        "samples/discharge_A.pdf", "samples/prescription_A.pdf",
                        "samples/diagnostic_A.pdf", "samples/claimform_A.pdf"],
    "B (total mismatch)": ["samples/policy_A.pdf", "samples/invoice_B_mismatch.pdf",
                            "samples/discharge_A.pdf", "samples/prescription_A.pdf",
                            "samples/diagnostic_A.pdf", "samples/claimform_A.pdf"],
    "C (missing docs)": ["samples/policy_A.pdf", "samples/invoice_A.pdf"],
}

def post(files, claim):
    bnd = "BOUNDARY9"
    body = b""
    for fp in files:
        body += (f"--{bnd}\r\nContent-Disposition: form-data; name=\"files\"; "
                 f"filename=\"{Path(fp).name}\"\r\nContent-Type: application/pdf\r\n\r\n").encode() \
            + Path(fp).read_bytes() + b"\r\n"
    body += f"--{bnd}--\r\n".encode()
    url = f"http://localhost:{PORT}/api/verify?claim_id={claim}"
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

for label, files in SETS.items():
    print("=" * 70 + f"\nSCENARIO {label}")
    try:
        rep = post(files, "CLM-DEMO-" + label[0])
    except Exception as e:
        print(f"  FAILED (is backend up on :{PORT} with Ollama running? {e})")
        sys.exit(1)
    print(f"  claim={rep['claim_id']} status={rep['status']} audit=#{rep['audit_id']}")
    for f in rep["findings"]:
        print(f"  [{f['severity']}] {f['code']}: {f['title']}")
    Path(f"verify_{label[0]}.json").write_text(json.dumps(rep, indent=1))
print("DONE — see verify_A/B/C.json")
