from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from bigrag.config import settings
from bigrag.database import db

ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hash: str) -> bool:
    try:
        return ph.verify(hash, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def generate_invite_code() -> str:
    return secrets.token_urlsafe(16)


def generate_api_key() -> str:
    return f"br_{secrets.token_urlsafe(32)}"


async def needs_setup() -> bool:
    row = await db.fetchrow("SELECT COUNT(*) as cnt FROM users")
    return row["cnt"] == 0


async def create_user(
    email: str, password: str, display_name: str, role: str = "member"
) -> dict:
    password_hash = hash_password(password)
    row = await db.fetchrow(
        """
        INSERT INTO users (email, password_hash, display_name, role)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, display_name, role, created_at, updated_at
        """,
        email, password_hash, display_name, role,
    )
    return dict(row)


async def authenticate(email: str, password: str) -> dict | None:
    row = await db.fetchrow("SELECT * FROM users WHERE email = $1", email)
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return dict(row)


async def create_session(user_id: UUID) -> str:
    token = generate_token()
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_expiry_hours)
    await db.execute(
        """
        INSERT INTO sessions (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user_id, token_hash, expires_at,
    )
    return token


async def validate_session(token: str) -> dict | None:
    token_hash = hash_token(token)
    row = await db.fetchrow(
        """
        SELECT u.id, u.email, u.display_name, u.role, u.created_at, u.updated_at
        FROM sessions s JOIN users u ON s.user_id = u.id
        WHERE s.token_hash = $1 AND s.expires_at > now()
        """,
        token_hash,
    )
    return dict(row) if row else None


async def cleanup_expired_sessions() -> int:
    """Delete expired sessions. Returns number of rows deleted."""
    result = await db.execute("DELETE FROM sessions WHERE expires_at <= now()")
    count = int(result.split()[-1]) if result else 0
    return count


async def invalidate_session(token: str) -> None:
    token_hash = hash_token(token)
    await db.execute("DELETE FROM sessions WHERE token_hash = $1", token_hash)


async def change_password(user_id: UUID, current_password: str, new_password: str) -> bool:
    row = await db.fetchrow("SELECT password_hash FROM users WHERE id = $1", user_id)
    if not row or not verify_password(current_password, row["password_hash"]):
        return False
    new_hash = hash_password(new_password)
    await db.execute(
        "UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2",
        new_hash, user_id,
    )
    return True


async def get_user_by_id(user_id: UUID) -> dict | None:
    row = await db.fetchrow(
        "SELECT id, email, display_name, role, created_at, updated_at FROM users WHERE id = $1",
        user_id,
    )
    return dict(row) if row else None


async def list_users() -> list[dict]:
    rows = await db.fetch(
        "SELECT id, email, display_name, role, created_at, updated_at FROM users ORDER BY created_at"
    )
    return [dict(r) for r in rows]


async def delete_user(user_id: UUID) -> bool:
    result = await db.execute("DELETE FROM users WHERE id = $1", user_id)
    return result == "DELETE 1"


async def update_user_role(user_id: UUID, role: str) -> bool:
    result = await db.execute(
        "UPDATE users SET role = $1, updated_at = now() WHERE id = $2",
        role, user_id,
    )
    return result == "UPDATE 1"


async def create_invite(created_by: UUID, role: str = "member", expires_in_hours: int = 72) -> dict:
    code = generate_invite_code()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    row = await db.fetchrow(
        """
        INSERT INTO invites (code, role, created_by, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, code, role, created_by, used_by, expires_at, created_at
        """,
        code, role, created_by, expires_at,
    )
    return dict(row)


async def list_invites() -> list[dict]:
    rows = await db.fetch(
        """
        SELECT i.id, i.code, i.role, i.expires_at, i.created_at, i.used_by,
               u.email as created_by_email
        FROM invites i
        LEFT JOIN users u ON i.created_by = u.id
        ORDER BY i.created_at DESC
        """
    )
    return [dict(r) for r in rows]


async def delete_invite(invite_id: UUID) -> bool:
    result = await db.execute("DELETE FROM invites WHERE id = $1", invite_id)
    return result == "DELETE 1"


async def redeem_invite(code: str) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT * FROM invites
        WHERE code = $1 AND used_by IS NULL AND expires_at > now()
        """,
        code,
    )
    return dict(row) if row else None


async def mark_invite_used(invite_id: UUID, user_id: UUID) -> None:
    await db.execute(
        "UPDATE invites SET used_by = $1 WHERE id = $2",
        user_id, invite_id,
    )


async def create_api_key_record(
    user_id: UUID | None, name: str, permissions: dict, expires_at: datetime | None = None
) -> tuple[str, dict]:
    key = generate_api_key()
    key_hash = hash_token(key)
    prefix = key[:10]
    row = await db.fetchrow(
        """
        INSERT INTO api_keys (user_id, name, key_hash, prefix, permissions, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, name, prefix, permissions, created_at, last_used_at, expires_at
        """,
        user_id, name, key_hash, prefix, permissions, expires_at,
    )
    return key, dict(row)


async def validate_api_key(key: str) -> dict | None:
    key_hash = hash_token(key)
    row = await db.fetchrow(
        """
        SELECT ak.*, u.role as user_role
        FROM api_keys ak
        LEFT JOIN users u ON ak.user_id = u.id
        WHERE ak.key_hash = $1 AND (ak.expires_at IS NULL OR ak.expires_at > now())
        """,
        key_hash,
    )
    if row:
        await db.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE id = $1", row["id"]
        )
        return dict(row)
    return None


async def list_api_keys() -> list[dict]:
    rows = await db.fetch(
        """
        SELECT id, name, prefix, permissions, created_at, last_used_at, expires_at
        FROM api_keys ORDER BY created_at DESC
        """
    )
    return [dict(r) for r in rows]


async def delete_api_key(key_id: UUID) -> bool:
    result = await db.execute("DELETE FROM api_keys WHERE id = $1", key_id)
    return result == "DELETE 1"
