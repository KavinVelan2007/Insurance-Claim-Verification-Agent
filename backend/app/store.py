"""SQLite audit trail: verifications + reviewer actions."""
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Any
from .config import settings


def _db() -> sqlite3.Connection:
    p = Path(settings.sqlite_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS verifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT, ts REAL,
        status TEXT, findings_json TEXT, docs_json TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT, audit_id INTEGER, ts REAL,
        finding_code TEXT, decision TEXT, comment TEXT, reviewer TEXT)""")
    return con


def save_verification(claim_id: str, status: str, findings_json: str, docs_json: str) -> int:
    con = _db()
    cur = con.execute(
        "INSERT INTO verifications(claim_id,ts,status,findings_json,docs_json) VALUES(?,?,?,?,?)",
        (claim_id, time.time(), status, findings_json, docs_json))
    con.commit()
    aid = cur.lastrowid or 0
    con.close()
    return aid


def save_review(audit_id: int, finding_code: str, decision: str, comment: str, reviewer: str) -> int:
    con = _db()
    cur = con.execute(
        "INSERT INTO reviews(audit_id,ts,finding_code,decision,comment,reviewer) VALUES(?,?,?,?,?,?)",
        (audit_id, time.time(), finding_code, decision, comment, reviewer))
    con.commit()
    rid = cur.lastrowid or 0
    con.close()
    return rid


def list_verifications(limit: int = 50) -> List[Dict[str, Any]]:
    con = _db()
    rows = con.execute(
        "SELECT id,claim_id,ts,status FROM verifications ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    con.close()
    return [dict(r) for r in rows]
