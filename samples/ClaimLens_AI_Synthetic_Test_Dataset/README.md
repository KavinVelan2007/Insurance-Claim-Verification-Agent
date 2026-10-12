# ClaimLens AI - Synthetic Health Insurance Claim Dataset

## Contents
- `policy_reference/insurance_policy.pdf`: the supplied one-page SecureHealth Premium Policy.
- `claims/`: 10 fictional multi-document claim packets. Upload these packets to ClaimLens AI as input documents.
- `ground_truth/expected_results.json`: detailed expected flags, calculations, evidence locations, and scope notes.
- `ground_truth/expected_results.csv`: compact case index for quickly seeing expected labels and outcomes.

## Policy rules used
The supplied policy page states:
1. Policy period: 01-Jan-2026 through 31-Dec-2026.
2. Sum insured: INR 10,000,000.
3. Standard Private A/C room rent: maximum INR 5,000 per day.
4. ICU: covered within sum insured; no separate cap listed.
5. Advanced diagnostics (MRI/CT): pre-authorisation is mandatory; maximum INR 15,000 per claim.
6. Cataract surgery: maximum INR 40,000 per eye.
7. Non-network hospital: 10% co-payment on the total allowed bill.

## Recommended test order
- Start with `CLM-1001` and `CLM-1002` as positive controls.
- Use `CLM-1003` through `CLM-1008` to test policy-rule checks and amount calculations.
- Use `CLM-1009` for duplicate invoice / double-count detection.
- Use `CLM-1010` for missing supporting evidence detection.
- `CLM-1005` and `CLM-1009` are rasterized scanned-style PDF packets; OCR is required for their page content. Other packets contain selectable text.

## Ground-truth labels
- `PASS_POLICY_CHECKS`: no inconsistency found against the rules stated in the supplied policy.
- `FLAG_FOR_ADJUSTMENT`: a stated policy cap or co-payment needs a numerical adjustment.
- `FLAG_FOR_MANUAL_REVIEW`: a policy-required pre-authorisation is not evidenced.
- `FLAG_POLICY_PERIOD_MISMATCH`: admission and discharge are outside the policy period.
- `FLAG_AMOUNT_INCONSISTENCY`: submitted amount appears to double-count a duplicate invoice.
- `REVIEW_INCOMPLETE_EVIDENCE`: a supporting document is absent from the packet.

## Important interpretation notes
- These examples support **triage and adjustment recommendations**, not autonomous approval or denial of real claims.
- A flagged issue does not necessarily mean the entire claim must be rejected. The expected calculations separate the potentially non-reimbursable part where the policy gives a clear cap.
- The supplied one-page policy does not state a full document checklist, exclusions, waiting periods, room-category proration formula, or duplicate-invoice procedure. The dataset does not invent those as policy clauses. Duplicate billing and missing discharge documentation are labeled as general document-integrity or operational completeness flags only.
- All names, claim IDs, hospitals, invoice references, and clinical details are fictional. These samples are for software testing only, not medical or insurance advice.
