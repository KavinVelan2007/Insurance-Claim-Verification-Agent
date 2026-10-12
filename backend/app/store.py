"""PostgreSQL access (Supabase-ready). Every tenant query is filtered by org_id.

DATABASE_URL: Supabase -> Project Settings -> Database -> Connection string.
Session pooler (port 5432) or direct connection both work; prepared statements
are disabled so the transaction pooler (6543) works too.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import settings
from .models import Finding

_pool: Optional[ConnectionPool] = None
_fernet: Optional[Fernet] = None


def _dsn() -> str:
    url = settings.database_url.strip()
    if not url or "YOUR-" in url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if "supabase." in url and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def _configure(con) -> None:
    # Every connection works inside the Kaagaz schema (created by init()).
    con.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(settings.db_schema)))
    con.commit()


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(_dsn(), min_size=1, max_size=8, open=True, timeout=10, configure=_configure,
                               kwargs={"row_factory": dict_row, "connect_timeout": 5,
                                       "prepare_threshold": None})
    return _pool


def init() -> None:
    """Create/upgrade tables. The advisory lock stops API + worker racing on DDL."""
    with pool().connection() as con:
        con.execute("SELECT pg_advisory_lock(424242)")
        try:
            con.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(settings.db_schema)))
            con.execute((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
        finally:
            con.execute("SELECT pg_advisory_unlock(424242)")


def close() -> None:
    if _pool:
        _pool.close()


def ping() -> bool:
    try:
        with pool().connection() as con:
            con.execute("SELECT 1")
        return True
    except Exception:
        return False


def _all(sql: str, params=()) -> List[Dict[str, Any]]:
    with pool().connection() as con:
        return con.execute(sql, params).fetchall()


def _one(sql: str, params=()) -> Optional[Dict[str, Any]]:
    with pool().connection() as con:
        return con.execute(sql, params).fetchone()


# ---------- file encryption ----------

def _crypto() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.file_encryption_key:
            raise RuntimeError("FILE_ENCRYPTION_KEY is not set in backend/.env")
        _fernet = Fernet(settings.file_encryption_key.encode())
    return _fernet


def encrypt(b: bytes) -> bytes:
    return _crypto().encrypt(b)


def decrypt(b: bytes) -> bytes:
    try:
        return _crypto().decrypt(b)
    except InvalidToken as e:
        raise RuntimeError("Stored file cannot be decrypted (FILE_ENCRYPTION_KEY changed?)") from e


# ---------- users & orgs ----------

_USER = "u.id, u.org_id, u.email, u.name, u.role, o.name AS org_name"


def create_org_with_admin(org_name: str, name: str, email: str, pw_hash: str) -> Optional[dict]:
    """None if the email is taken."""
    with pool().connection() as con:
        if con.execute("SELECT 1 FROM users WHERE lower(email)=lower(%s)", (email,)).fetchone():
            return None
        org = con.execute("INSERT INTO orgs(name) VALUES(%s) RETURNING id", (org_name,)).fetchone()
        u = con.execute("INSERT INTO users(org_id,email,name,password_hash,role) VALUES(%s,%s,%s,%s,'admin') RETURNING id",
                        (org["id"], email, name, pw_hash)).fetchone()
    return get_user(u["id"])


def get_user(uid: int) -> Optional[dict]:
    return _one(f"SELECT {_USER} FROM users u JOIN orgs o ON o.id=u.org_id WHERE u.id=%s", (uid,))


def get_login(email: str) -> Optional[dict]:
    return _one("SELECT id, password_hash FROM users WHERE lower(email)=lower(%s)", (email,))


def get_password_hash(uid: int) -> Optional[str]:
    r = _one("SELECT password_hash FROM users WHERE id=%s", (uid,))
    return r["password_hash"] if r else None


def set_password(uid: int, pw_hash: str) -> None:
    _all("UPDATE users SET password_hash=%s WHERE id=%s RETURNING id", (pw_hash, uid))


def list_members(org: int) -> List[dict]:
    return _all("SELECT id, name, email, role, created_at FROM users WHERE org_id=%s ORDER BY created_at", (org,))


def add_member(org: int, name: str, email: str, pw_hash: str, role: str) -> Optional[dict]:
    with pool().connection() as con:
        if con.execute("SELECT 1 FROM users WHERE lower(email)=lower(%s)", (email,)).fetchone():
            return None
        return con.execute("INSERT INTO users(org_id,email,name,password_hash,role) VALUES(%s,%s,%s,%s,%s)"
                           " RETURNING id, name, email, role, created_at", (org, email, name, pw_hash, role)).fetchone()


# ---------- claims ----------

def create_claim(org: int, uid: int, claim_ref: Optional[str], files: List[dict]) -> int:
    """files: [{filename, data, sha256, pages}] — stored encrypted, queued for the worker."""
    enc = [(f, encrypt(f["data"])) for f in files]
    with pool().connection() as con:
        cid = con.execute("INSERT INTO claims(org_id,created_by,claim_ref) VALUES(%s,%s,%s) RETURNING id",
                          (org, uid, claim_ref)).fetchone()["id"]
        with con.cursor() as cur:
            cur.executemany(
                "INSERT INTO documents(org_id,claim_id,filename,sha256,size_bytes,pages,file_enc)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s)",
                [(org, cid, f["filename"], f["sha256"], len(f["data"]), f["pages"], e) for f, e in enc])
    return cid


def list_claims(org: int, limit: int, offset: int, q: str = "") -> List[dict]:
    like = f"%{q.strip()}%"
    return _all("""
        SELECT c.id, c.claim_ref, c.state, c.status, c.patient_name, c.hospital_name, c.total_claimed,
               c.created_at, c.finished_at, u.name AS created_by,
               (SELECT count(*) FROM documents d WHERE d.claim_id=c.id) AS doc_count,
               (SELECT count(*) FROM findings f WHERE f.claim_id=c.id AND f.severity <> 'info'
                  AND NOT EXISTS (SELECT 1 FROM reviews r WHERE r.finding_id=f.id)) AS open_findings
        FROM claims c LEFT JOIN users u ON u.id=c.created_by
        WHERE c.org_id=%s AND (%s='' OR c.claim_ref ILIKE %s OR c.patient_name ILIKE %s OR c.hospital_name ILIKE %s)
        ORDER BY c.created_at DESC LIMIT %s OFFSET %s""",
                (org, q.strip(), like, like, like, max(1, min(limit, 100)), max(0, offset)))


def claim_stats(org: int) -> dict:
    return _one("""SELECT count(*) AS total,
        count(*) FILTER (WHERE state IN ('queued','processing')) AS in_progress,
        count(*) FILTER (WHERE status='incomplete') AS incomplete,
        count(*) FILTER (WHERE status='needs_review') AS needs_review,
        count(*) FILTER (WHERE status='consistent') AS consistent,
        count(*) FILTER (WHERE state='failed') AS failed
        FROM claims WHERE org_id=%s""", (org,))


def get_claim(org: int, cid: int) -> Optional[dict]:
    c = _one("""SELECT c.id, c.claim_ref, c.state, c.status, c.error, c.patient_name, c.hospital_name,
                c.total_claimed, c.attempts, c.created_at, c.started_at, c.finished_at, u.name AS created_by
                FROM claims c LEFT JOIN users u ON u.id=c.created_by WHERE c.org_id=%s AND c.id=%s""", (org, cid))
    if not c:
        return None
    c["documents"] = _all("""SELECT id, filename, size_bytes, pages, doc_type, extraction_method, data,
                             (file_enc IS NOT NULL) AS has_file FROM documents WHERE claim_id=%s ORDER BY id""", (cid,))
    c["findings"] = _all("""
        SELECT f.id, f.code, f.severity, f.title, f.detail, f.extracted_value, f.expected_value,
               f.document_ref, f.policy_clause, f.confidence, f.action,
               COALESCE((SELECT json_agg(json_build_object('decision', r.decision, 'comment', r.comment,
                          'reviewer', ru.name, 'at', r.created_at) ORDER BY r.created_at DESC)
                         FROM reviews r LEFT JOIN users ru ON ru.id=r.reviewer_id WHERE r.finding_id=f.id), '[]') AS reviews
        FROM findings f WHERE f.claim_id=%s
        ORDER BY array_position(ARRAY['action_required','policy_review','warning','info'], f.severity), f.id""", (cid,))
    return c


def get_file(org: int, cid: int, doc_id: int) -> Optional[dict]:
    r = _one("SELECT filename, file_enc FROM documents WHERE org_id=%s AND claim_id=%s AND id=%s", (org, cid, doc_id))
    if r and r["file_enc"] is not None:
        r["data"] = decrypt(bytes(r["file_enc"]))
    return r


def delete_claim(org: int, cid: int) -> bool:
    return bool(_all("DELETE FROM claims WHERE org_id=%s AND id=%s RETURNING id", (org, cid)))


def retry_claim(org: int, cid: int) -> bool:
    return bool(_all("""UPDATE claims SET state='queued', error=NULL WHERE org_id=%s AND id=%s AND state='failed'
                        AND EXISTS (SELECT 1 FROM documents WHERE claim_id=%s AND file_enc IS NOT NULL) RETURNING id""",
                     (org, cid, cid)))


def get_finding(org: int, fid: int) -> Optional[dict]:
    return _one("SELECT id, claim_id, policy_clause FROM findings WHERE org_id=%s AND id=%s", (org, fid))


def add_review(org: int, fid: int, uid: int, decision: str, comment: str) -> None:
    _all("INSERT INTO reviews(org_id,finding_id,reviewer_id,decision,comment) VALUES(%s,%s,%s,%s,%s) RETURNING id",
         (org, fid, uid, decision, comment))


def log(org: int, uid: Optional[int], action: str, claim_id: Optional[int] = None,
        detail: str = "", ip: str = "") -> None:
    _all("INSERT INTO access_log(org_id,user_id,action,claim_id,detail,ip) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
         (org, uid, action, claim_id, detail[:500], ip[:64]))


def activity(org: int, limit: int = 50) -> List[dict]:
    return _all("""SELECT a.action, a.claim_id, a.detail, a.created_at, u.name AS user_name
                   FROM access_log a LEFT JOIN users u ON u.id=a.user_id
                   WHERE a.org_id=%s ORDER BY a.created_at DESC LIMIT %s""", (org, max(1, min(limit, 200))))


# ---------- worker ----------

def next_job() -> Optional[dict]:
    """Atomically take the oldest queued claim (safe with several workers)."""
    return _one("""UPDATE claims SET state='processing', started_at=now(), attempts=attempts+1
                   WHERE id=(SELECT id FROM claims WHERE state='queued' ORDER BY created_at
                             FOR UPDATE SKIP LOCKED LIMIT 1)
                   RETURNING id, org_id, claim_ref""")


def job_documents(cid: int) -> List[dict]:
    rows = _all("SELECT id, filename, file_enc FROM documents WHERE claim_id=%s ORDER BY id", (cid,))
    for r in rows:
        r["data"] = decrypt(bytes(r.pop("file_enc")))
    return rows


def prior_invoices(org: int, cid: int, numbers: List[str]) -> Dict[str, str]:
    if not numbers:
        return {}
    rows = _all("""SELECT DISTINCT ON (d.data->>'invoice_number') d.data->>'invoice_number' AS num,
                          COALESCE(c.claim_ref, '#' || c.id) AS ref
                   FROM documents d JOIN claims c ON c.id=d.claim_id
                   WHERE d.org_id=%s AND d.claim_id<>%s AND d.doc_type='invoice'
                     AND d.data->>'invoice_number' = ANY(%s)""", (org, cid, numbers))
    return {r["num"]: r["ref"] for r in rows}


def finish_job(cid: int, status: str, claim_ref: Optional[str], docs: List[tuple], findings: List[Finding],
               patient: Optional[str], hospital: Optional[str], total: Optional[float]) -> None:
    """docs: [(document_id, ParsedDocument)]. One transaction: results appear all at once."""
    with pool().connection() as con:
        org = con.execute("SELECT org_id FROM claims WHERE id=%s", (cid,)).fetchone()["org_id"]
        with con.cursor() as cur:
            cur.executemany("UPDATE documents SET doc_type=%s, extraction_method=%s, data=%s WHERE id=%s",
                            [(d.document_type, d.extraction_method, Jsonb(d.model_dump()), i) for i, d in docs])
            cur.execute("DELETE FROM findings WHERE claim_id=%s", (cid,))
            cur.executemany(
                "INSERT INTO findings(org_id,claim_id,code,severity,title,detail,extracted_value,expected_value,"
                "document_ref,policy_clause,confidence,action) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(org, cid, f.code, f.severity, f.title, f.detail, f.extracted_value, f.expected_value,
                  f.document_ref, f.policy_clause, f.confidence, f.action) for f in findings])
            cur.execute("""UPDATE claims SET state='done', status=%s, claim_ref=%s, patient_name=%s, hospital_name=%s,
                           total_claimed=%s, error=NULL, finished_at=now() WHERE id=%s""",
                        (status, claim_ref, patient, hospital, total, cid))


def fail_job(cid: int, error: str) -> None:
    _all("UPDATE claims SET state='failed', error=%s, finished_at=now() WHERE id=%s RETURNING id", (error[:1000], cid))


def requeue_stale(minutes: int = 30) -> None:
    """Claims stuck in 'processing' (worker crashed) go back to the queue."""
    _all("UPDATE claims SET state='queued' WHERE state='processing' AND started_at < now() - make_interval(mins => %s)"
         " RETURNING id", (minutes,))


def purge_files(days: int) -> int:
    rows = _all("UPDATE documents SET file_enc=NULL WHERE file_enc IS NOT NULL"
                " AND created_at < now() - make_interval(days => %s) RETURNING id", (days,))
    return len(rows)

