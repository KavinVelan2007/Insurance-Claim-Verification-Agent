"""Job worker: takes queued claims from Postgres, runs the pipeline, stores results.

Runs as a thread inside the API (WORKER_ENABLED=true) or on its own:
    python -m app.worker
Postgres is the queue (FOR UPDATE SKIP LOCKED), so several workers can run safely.
One claim at a time per worker keeps LLM spend and provider rate limits predictable.
"""
import logging
import threading
import time

from . import llm, pipeline, store
from .config import settings
from .verifier import overall_status, verify

log = logging.getLogger("kaagaz.worker")
IDLE_POLL_S = 2
MAINTENANCE_EVERY_S = 3600


def process(job: dict) -> None:
    cid = job["id"]
    try:
        docs = [(d["id"], pipeline.parse_pdf(d["data"], d["filename"])) for d in store.job_documents(cid)]
        parsed = [p for _, p in docs]
        invoices = [p for p in parsed if p.document_type == "invoice"]
        prior = store.prior_invoices(job["org_id"], cid, [p.invoice_number for p in invoices if p.invoice_number])
        findings = verify(parsed, prior)
        first = lambda attr: next((getattr(p, attr) for p in parsed if getattr(p, attr)), None)
        total = round(sum(p.total_amount or 0 for p in invoices), 2) if invoices else None
        store.finish_job(cid, overall_status(findings), job["claim_ref"] or first("claim_id"), docs, findings,
                         first("patient_name"), first("hospital_name"), total)
        log.info("claim %s done: %d findings", cid, len(findings))
    except Exception as e:
        log.exception("claim %s failed", cid)
        store.fail_job(cid, str(e) if isinstance(e, llm.LLMError) else f"{type(e).__name__}: {e}")


def run(stop: threading.Event) -> None:
    last_maint = 0.0
    while not stop.is_set():
        try:
            if time.time() - last_maint > MAINTENANCE_EVERY_S:
                store.requeue_stale()
                n = store.purge_files(settings.retention_days)
                if n:
                    log.info("retention: purged %d stored PDFs older than %d days", n, settings.retention_days)
                last_maint = time.time()
            job = store.next_job()
        except Exception:
            log.exception("worker cannot reach the database; retrying")
            stop.wait(10)
            continue
        if job:
            process(job)
        else:
            stop.wait(IDLE_POLL_S)


def start_thread() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=run, args=(stop,), name="kaagaz-worker", daemon=True).start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    store.init()
    try:
        run(threading.Event())
    except KeyboardInterrupt:
        pass
