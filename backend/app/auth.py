"""Passwords (scrypt), signed session cookies (HMAC), rate limits. Stdlib only."""
import base64
import hashlib
import hmac
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from . import store
from .config import settings

COOKIE = "kaagaz_session"
_N, _R, _P = 2 ** 14, 8, 1


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_b64(salt)}${_b64(h)}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        return hmac.compare_digest(hashlib.scrypt(pw.encode(), salt=_unb64(salt), n=_N, r=_R, p=_P), _unb64(h))
    except (ValueError, TypeError):
        return False


def _key() -> bytes:
    if len(settings.secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be set (32+ chars) in backend/.env")
    return settings.secret_key.encode()


def make_token(user_id: int, now: float | None = None) -> str:
    # ponytail: stateless tokens can't be revoked before expiry; add a sessions table if needed.
    exp = int((now or time.time()) + settings.session_hours * 3600)
    body = f"{user_id}.{exp}"
    return f"{body}.{_b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())}"


def read_token(token: str, now: float | None = None) -> int | None:
    try:
        uid, exp, sig = token.split(".")
        good = _b64(hmac.new(_key(), f"{uid}.{exp}".encode(), hashlib.sha256).digest())
        if hmac.compare_digest(sig, good) and int(exp) > (now or time.time()):
            return int(uid)
    except (ValueError, AttributeError):
        pass
    return None


def current_user(request: Request) -> dict:
    uid = read_token(request.cookies.get(COOKIE, ""))
    user = store.get_user(uid) if uid else None
    if not user:
        raise HTTPException(401, "Please sign in.")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Only admins can do this.")
    return user


# ponytail: in-process sliding window; move to Redis/Postgres when running several API processes.
_hits: dict = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(bucket: str, key, limit: int, per_s: int) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[(bucket, key)]
        while q and q[0] <= now - per_s:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, f"Too many requests. Try again in {int(q[0] + per_s - now) + 1}s.")
        q.append(now)
