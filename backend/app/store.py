"""PostgreSQL audit trail: verifications + reviewer actions (Supabase-ready).

Configure via DATABASE_URL in backend/.env, e.g.
  postgresql://postgres:<PASSWORD>@db.<ref>.supabase.co:5432/postgres?sslmode=require
"""
import time
from typing import List, Dict, Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from .config import settings


def _dsn() -> str:
    url = (settings.database_url or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set — copy backend/.env.example to backend/.env "
            "and paste your Supabase connection string (URI, port 5432)."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Supabase/Postgres requires TLS; psycopg needs sslmode=require (or ssl="require").
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith("supabase.co") and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def _connect():
    return psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=5)


def init_db() -> None:
    con = _connect()
    try:
        with con.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS verifications(
                id BIGSERIAL PRIMARY KEY, claim_id TEXT, ts DOUBLE PRECISION,
                status TEXT, findings_json TEXT, docs_json TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS reviews(
                id BIGSERIAL PRIMARY KEY, audit_id BIGINT REFERENCES verifications(id),
                ts DOUBLE PRECISION, finding_code TEXT, decision TEXT,
                comment TEXT, reviewer TEXT)""")
        con.commit()
    finally:
        con.close()


def _ensure(con) -> None:
    with con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS verifications(
            id BIGSERIAL PRIMARY KEY, claim_id TEXT, ts DOUBLE PRECISION,
            status TEXT, findings_json TEXT, docs_json TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS reviews(
            id BIGSERIAL PRIMARY KEY, audit_id BIGINT REFERENCES verifications(id),
            ts DOUBLE PRECISION, finding_code TEXT, decision TEXT,
            comment TEXT, reviewer TEXT)""")


def ping() -> bool:
    try:
        con = _connect()
        con.close()
        return True
    except Exception:
        return False


def save_verification(claim_id: str, status: str, findings_json: str, docs_json: str) -> int:
    con = _connect()
    try:
        _ensure(con)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO verifications(claim_id,ts,status,findings_json,docs_json)"
                " VALUES(%s,%s,%s,%s,%s) RETURNING id",
                (claim_id, time.time(), status, findings_json, docs_json))
            row = cur.fetchone()
        con.commit()
        return int(row["id"]) if row else 0
    finally:
        con.close()


def save_review(audit_id: int, finding_code: str, decision: str, comment: str, reviewer: str) -> int:
    con = _connect()
    try:
        _ensure(con)
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO reviews(audit_id,ts,finding_code,decision,comment,reviewer)"
                " VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
                (audit_id, time.time(), finding_code, decision, comment, reviewer))
            row = cur.fetchone()
        con.commit()
        return int(row["id"]) if row else 0
    finally:
        con.close()


def list_verifications(limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 200))
    con = _connect()
    try:
        _ensure(con)
        with con.cursor() as cur:
            cur.execute(
                "SELECT id,claim_id,ts,status FROM verifications"
                " ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

