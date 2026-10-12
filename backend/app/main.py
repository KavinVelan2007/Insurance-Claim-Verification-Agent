"""Kaagaz API. Uploads are queued as claims; the worker verifies them; reviewers
record decisions per finding. Every route except auth and health needs a session."""
import hashlib
import logging
import re
from contextlib import asynccontextmanager
from typing import List
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import llm, pipeline, store, worker
from .auth import (COOKIE, admin_user, check_password, current_user, hash_password, make_token,
                   rate_limit)
from .config import settings
from .models import LoginIn, MemberIn, PasswordIn, ReviewIn, SignupIn

log = logging.getLogger("kaagaz")
_DUMMY_HASH = hash_password("timing-equaliser")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        store.init()
    except Exception as e:  # start anyway; /api/system reports the DB as down
        log.error("database init failed: %s", e)
    stop = worker.start_thread() if settings.worker_enabled else None
    yield
    if stop:
        stop.set()
    store.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"], allow_credentials=True)


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _db(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except RuntimeError as e:   # missing config: DATABASE_URL / FILE_ENCRYPTION_KEY
        raise HTTPException(503, str(e))


def _start_session(response: Response, user: dict) -> dict:
    response.set_cookie(COOKIE, make_token(user["id"]), max_age=settings.session_hours * 3600, httponly=True,
                        samesite="lax", secure=settings.cookie_secure, path="/")
    return user


# ---------- auth ----------

@app.post("/api/auth/signup")
def signup(body: SignupIn, request: Request, response: Response):
    rate_limit("signup", _ip(request), 5, 3600)
    user = _db(store.create_org_with_admin, body.org_name.strip(), body.name.strip(), body.email.strip(),
               hash_password(body.password))
    if not user:
        raise HTTPException(409, "An account with this email already exists.")
    store.log(user["org_id"], user["id"], "auth.signup", ip=_ip(request))
    return _start_session(response, user)


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    rate_limit("login-ip", _ip(request), 10, 60)
    rate_limit("login-email", body.email.lower(), 10, 900)
    row = _db(store.get_login, body.email.strip())
    if not check_password(body.password, row["password_hash"] if row else _DUMMY_HASH) or not row:
        raise HTTPException(401, "Email or password is incorrect.")
    user = store.get_user(row["id"])
    store.log(user["org_id"], user["id"], "auth.login", ip=_ip(request))
    return _start_session(response, user)


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


@app.post("/api/me/password")
def change_password(body: PasswordIn, user: dict = Depends(current_user)):
    rate_limit("password", user["id"], 5, 900)
    if not check_password(body.current, store.get_password_hash(user["id"]) or ""):
        raise HTTPException(400, "Current password is incorrect.")
    store.set_password(user["id"], hash_password(body.new))
    store.log(user["org_id"], user["id"], "auth.password_changed")
    return {"ok": True}


# ---------- team ----------

@app.get("/api/team")
def team(user: dict = Depends(current_user)):
    return store.list_members(user["org_id"])


@app.post("/api/team", status_code=201)
def add_member(body: MemberIn, user: dict = Depends(admin_user)):
    m = store.add_member(user["org_id"], body.name.strip(), body.email.strip(), hash_password(body.password), body.role)
    if not m:
        raise HTTPException(409, "An account with this email already exists.")
    store.log(user["org_id"], user["id"], "team.member_added", detail=f"{m['email']} ({m['role']})")
    return m


@app.get("/api/activity")
def activity(limit: int = 50, user: dict = Depends(admin_user)):
    return store.activity(user["org_id"], limit)


# ---------- system ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/system")
def system(user: dict = Depends(current_user)):
    return {"llm": {"model": settings.llm_model, "configured": llm.configured(),
                    "provider": settings.llm_base_url.split("//")[-1].split("/")[0]},
            "db": store.ping(), "worker": settings.worker_enabled, "retention_days": settings.retention_days,
            "max_upload_mb": settings.max_upload_mb, "max_files": settings.max_files}


# ---------- claims ----------

def _safe_name(name: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    return re.sub(r"[\x00-\x1f\"]", "", base).strip()[:200] or "document.pdf"


@app.post("/api/claims", status_code=202)
def create_claim(request: Request, files: List[UploadFile] = File(...), claim_ref: str = Form(""),
                       user: dict = Depends(current_user)):
    rate_limit("claims", user["id"], 30, 3600)
    if not files or len(files) > settings.max_files:
        raise HTTPException(400, f"Upload between 1 and {settings.max_files} PDFs.")
    if len(claim_ref) > 64:
        raise HTTPException(400, "Claim reference is too long (64 characters max).")
    limit = settings.max_upload_mb * 1024 * 1024
    out, seen = [], set()
    for f in files:
        name = _safe_name(f.filename)
        data = f.file.read(limit + 1)   # never buffer more than the cap
        if len(data) > limit:
            raise HTTPException(413, f"{name}: larger than {settings.max_upload_mb} MB.")
        try:
            pages = pipeline.page_count(data)
        except ValueError as e:
            raise HTTPException(400, f"{name}: {e}.")
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen:
            raise HTTPException(400, f"{name}: the same file was added twice.")
        seen.add(sha)
        out.append({"filename": name, "data": data, "sha256": sha, "pages": pages})
    cid = _db(store.create_claim, user["org_id"], user["id"], claim_ref.strip() or None, out)
    store.log(user["org_id"], user["id"], "claim.created", cid, f"{len(out)} documents", _ip(request))
    return {"id": cid, "state": "queued"}


@app.get("/api/claims")
def list_claims(limit: int = 25, offset: int = 0, q: str = "", user: dict = Depends(current_user)):
    return {"items": _db(store.list_claims, user["org_id"], limit, offset, q[:100]),
            "stats": store.claim_stats(user["org_id"])}


def _claim_or_404(user: dict, cid: int) -> dict:
    c = _db(store.get_claim, user["org_id"], cid)
    if not c:
        raise HTTPException(404, "Claim not found.")
    return c


@app.get("/api/claims/{cid}")
def get_claim(cid: int, request: Request, user: dict = Depends(current_user)):
    c = _claim_or_404(user, cid)
    if c["state"] == "done":  # don't log every poll while it's processing
        store.log(user["org_id"], user["id"], "claim.viewed", cid, ip=_ip(request))
    return c


@app.get("/api/claims/{cid}/documents/{doc_id}/file")
def get_file(cid: int, doc_id: int, request: Request, user: dict = Depends(current_user)):
    f = _db(store.get_file, user["org_id"], cid, doc_id)
    if not f:
        raise HTTPException(404, "Document not found.")
    if f.get("data") is None:
        raise HTTPException(410, f"The PDF was deleted after the {settings.retention_days}-day retention period.")
    store.log(user["org_id"], user["id"], "document.opened", cid, f["filename"], _ip(request))
    return Response(f["data"], media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(f['filename'])}", "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"})


@app.post("/api/claims/{cid}/retry")
def retry(cid: int, user: dict = Depends(current_user)):
    if not store.retry_claim(user["org_id"], cid):
        raise HTTPException(409, "Only failed claims whose files are still stored can be retried.")
    store.log(user["org_id"], user["id"], "claim.retried", cid)
    return {"id": cid, "state": "queued"}


@app.delete("/api/claims/{cid}")
def delete_claim(cid: int, request: Request, user: dict = Depends(admin_user)):
    if not store.delete_claim(user["org_id"], cid):
        raise HTTPException(404, "Claim not found.")
    store.log(user["org_id"], user["id"], "claim.deleted", cid, ip=_ip(request))
    return {"ok": True}


# ---------- findings ----------

@app.post("/api/findings/{fid}/reviews", status_code=201)
def review(fid: int, body: ReviewIn, user: dict = Depends(current_user)):
    f = store.get_finding(user["org_id"], fid)
    if not f:
        raise HTTPException(404, "Finding not found.")
    store.add_review(user["org_id"], fid, user["id"], body.decision, body.comment.strip())
    store.log(user["org_id"], user["id"], "finding.reviewed", f["claim_id"], f"{fid}: {body.decision}")
    return {"ok": True}


@app.post("/api/findings/{fid}/explain")
def explain(fid: int, user: dict = Depends(current_user)):
    rate_limit("explain", user["id"], 20, 60)
    f = store.get_finding(user["org_id"], fid)
    if not f or not f["policy_clause"]:
        raise HTTPException(404, "This finding has no policy clause to explain.")
    try:
        return {"explanation": llm.explain_clause(f["policy_clause"])}
    except llm.LLMError as e:
        raise HTTPException(502, str(e))
