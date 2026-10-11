"""Persistent opaque credentials and transactional sliding-window quotas.

No public signup or token minting endpoint. Random secrets have 256 bits of
entropy; only their SHA256 is stored. CSRF is not an authentication credential.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import secrets
import time
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from .domain import InvalidInput, NotFound, ServiceError

COOKIE = "__Host-bublik_session"
SCOPES = frozenset({"chats:read", "chats:write", "chats:export", "service:read"})
HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)


class AuthError(ServiceError):
    code = "authentication_required"


class Forbidden(ServiceError):
    code = "insufficient_scope"


class RateLimited(ServiceError):
    code = "rate_limit_exceeded"

    def __init__(self, retry_after):
        super().__init__()
        self.retry_after = max(1, math.ceil(retry_after))


def digest(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def credential(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise AuthError()
    return digest(value)


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256 or "\x00" in password:
        raise InvalidInput("invalid_password")
    try:
        if len(password.encode()) > 1024:
            raise InvalidInput("invalid_password")
    except UnicodeError:
        raise InvalidInput("invalid_password") from None
    return HASHER.hash(password)


@dataclass(frozen=True)
class Principal:
    owner: str
    scopes: frozenset
    kind: str
    credential_hash: str


class SecurityStore:
    def __init__(self, repository, *, clock=time.time, generation_limit=10):
        self.repository = repository
        self.database = repository.database
        self.clock = clock
        if type(generation_limit) is not int or generation_limit < 1:
            raise ValueError("positive generation quota required")
        self.generation_limit = generation_limit
        # Same verifier work for unknown and disabled accounts.
        self.dummy = HASHER.hash(secrets.token_urlsafe(32))

    def rate_in_transaction(self, db, bucket, limit, window=60):
        now = self.clock()
        db.execute("DELETE FROM rate_events WHERE occurred_at<=?", (now - 3600,))
        row = db.execute("SELECT count(*),min(occurred_at) FROM rate_events WHERE bucket=? AND occurred_at>?",
                         (bucket, now-window)).fetchone()
        if row[0] >= limit:
            raise RateLimited(row[1]+window-now)
        db.execute("INSERT INTO rate_events VALUES (?,?)", (bucket, now))

    def rate(self, bucket, limit, window=60):
        with self.database.connect(write=True) as db:
            self.rate_in_transaction(db, bucket, limit, window)

    def generation_admission(self, db, owner):
        # Called AFTER replay/capacity/revision checks inside job commit. Rollback
        # refunds rejected admissions, and successful replay never debits a quota.
        self.rate_in_transaction(db, "generation:" + owner, self.generation_limit)

    def new_session(self, owner=None, *, replace=None):
        raw, csrf, now = secrets.token_urlsafe(32), secrets.token_urlsafe(32), self.clock()
        lifetime = 43200 if owner else 900
        with self.database.connect(write=True) as db:
            db.execute("DELETE FROM browser_sessions WHERE expires_at<=?", (now,))
            if replace:
                db.execute("DELETE FROM browser_sessions WHERE secret_hash=?", (credential(replace),))
            if owner:
                self.repository._user(db, owner)
            db.execute("INSERT INTO browser_sessions VALUES (?,?,?,?,?)",
                       (digest(raw), owner, csrf, now, now+lifetime))
        return raw

    def session(self, raw):
        hashed = credential(raw)
        with self.database.connect() as db:
            row = db.execute("SELECT s.*,u.username FROM browser_sessions s LEFT JOIN users u ON u.id=s.owner_id "
                             "WHERE secret_hash=? AND expires_at>?", (hashed, self.clock())).fetchone()
            if row is None:
                raise AuthError()
            return dict(row)

    def browser_principal(self, raw):
        row = self.session(raw)
        if row["owner_id"] is None:
            raise AuthError()
        return Principal(row["owner_id"], SCOPES, "browser", row["secret_hash"])

    def login(self, username, password, bootstrap):
        session = self.session(bootstrap)
        if session["owner_id"] is not None:
            raise Forbidden("logout_required")
        name = username.strip().casefold()
        with self.database.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (name,)).fetchone()
        encoded = row["password_hash"] if row and row["password_hash"].startswith("$argon2id$") else self.dummy
        try:
            valid = HASHER.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid or row is None or encoded == self.dummy:
            raise AuthError("invalid_credentials")
        # Password reset racing verification cannot issue a fresh credential.
        raw, csrf, now = secrets.token_urlsafe(32), secrets.token_urlsafe(32), self.clock()
        with self.database.connect(write=True) as db:
            current = db.execute("SELECT password_hash FROM users WHERE id=?", (row["id"],)).fetchone()
            old = db.execute("SELECT owner_id FROM browser_sessions WHERE secret_hash=? AND expires_at>?",
                             (credential(bootstrap), now)).fetchone()
            if not current or current[0] != encoded or not old or old[0] is not None:
                raise AuthError("invalid_credentials")
            if HASHER.check_needs_rehash(encoded):
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (HASHER.hash(password), row["id"]))
            db.execute("DELETE FROM browser_sessions WHERE secret_hash=?", (credential(bootstrap),))
            db.execute("INSERT INTO browser_sessions VALUES (?,?,?,?,?)", (digest(raw),row["id"],csrf,now,now+43200))
        return raw

    def logout(self, raw):
        with self.database.connect(write=True) as db:
            db.execute("DELETE FROM browser_sessions WHERE secret_hash=?", (credential(raw),))

    def set_password(self, owner, password):
        encoded = password_hash(password)
        with self.database.connect(write=True) as db:
            self.repository._user(db, owner)
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (encoded, owner))
            db.execute("DELETE FROM browser_sessions WHERE owner_id=?", (owner,))
            db.execute("UPDATE api_tokens SET revoked=1 WHERE owner_id=?", (owner,))

    def issue_token(self, owner, label, scopes, *, days=30):
        scopes = frozenset(scopes)
        if not scopes or not scopes <= SCOPES or type(days) is not int or not 1 <= days <= 365:
            raise InvalidInput("invalid_token_options")
        if not isinstance(label, str) or not 1 <= len(label) <= 80 or "\x00" in label:
            raise InvalidInput("invalid_token_label")
        raw, ident, now = secrets.token_urlsafe(32), uuid.uuid4().hex, self.clock()
        with self.database.connect(write=True) as db:
            self.repository._user(db, owner)
            db.execute("INSERT INTO api_tokens(id,owner_id,secret_hash,label,scopes_json,created_at,expires_at) "
                       "VALUES (?,?,?,?,?,?,?)", (ident,owner,digest(raw),label,json.dumps(sorted(scopes)),now,now+days*86400))
        return {"id": ident, "token": raw, "scopes": sorted(scopes), "expires_at": now+days*86400}

    def token_principal(self, raw):
        hashed = credential(raw)
        with self.database.connect() as db:
            row = db.execute("SELECT * FROM api_tokens WHERE secret_hash=? AND revoked=0 AND expires_at>?",
                             (hashed, self.clock())).fetchone()
            if row is None:
                raise AuthError()
            return Principal(row["owner_id"], frozenset(json.loads(row["scopes_json"])), "token", hashed)

    def revalidate(self, principal):
        with self.database.connect() as db:
            table = "browser_sessions" if principal.kind == "browser" else "api_tokens"
            clause = "" if principal.kind == "browser" else " AND revoked=0"
            row = db.execute(f"SELECT owner_id FROM {table} WHERE secret_hash=? AND expires_at>?"+clause,
                             (principal.credential_hash, self.clock())).fetchone()
            if not row or row[0] != principal.owner:
                raise AuthError()

    def list_tokens(self, owner):
        with self.database.connect() as db:
            self.repository._user(db, owner)
            return [dict(r) for r in db.execute("SELECT id,label,scopes_json,created_at,expires_at,revoked "
                                               "FROM api_tokens WHERE owner_id=? ORDER BY created_at,id", (owner,))]

    def revoke_token(self, owner, ident):
        with self.database.connect(write=True) as db:
            if db.execute("UPDATE api_tokens SET revoked=1 WHERE owner_id=? AND id=?", (owner,ident)).rowcount != 1:
                raise NotFound()
