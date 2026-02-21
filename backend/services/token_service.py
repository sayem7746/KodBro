"""
Encrypt/decrypt and CRUD for user_tokens.
"""
import base64
import os
from typing import Optional
from uuid import UUID

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy.orm import Session

from database import UserToken


def _get_fernet() -> Fernet:
    key_b64 = os.environ.get("ENCRYPTION_KEY")
    if not key_b64:
        raise RuntimeError("ENCRYPTION_KEY not set")
    # Fernet needs 32 url-safe base64 bytes
    try:
        key = base64.urlsafe_b64decode(key_b64)
    except Exception:
        # If key is not valid base64, derive from it
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kodbro_token_salt",
            iterations=100000,
        )
        key = kdf.derive(key_b64.encode() if isinstance(key_b64, str) else key_b64)
    if len(key) != 32:
        key = key[:32] if len(key) > 32 else key + b"\0" * (32 - len(key))
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_token(plain: str) -> tuple[bytes, bytes]:
    """Encrypt token. Returns (encrypted_bytes, iv). Fernet handles IV internally; we store placeholder."""
    f = _get_fernet()
    encrypted = f.encrypt(plain.encode())
    return encrypted, b"fernet"  # Placeholder; Fernet embeds nonce in ciphertext


def decrypt_token(encrypted: bytes, iv: bytes) -> str:
    """Decrypt token. iv is unused for Fernet."""
    f = _get_fernet()
    return f.decrypt(encrypted).decode()


def get_token(db: Session, user_id: UUID, provider: str) -> Optional[str]:
    """Get decrypted token for user and provider. Returns None if not found."""
    row = db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.provider == provider,
    ).first()
    if not row:
        return None
    return decrypt_token(row.encrypted_value, row.iv or b"")


def set_token(
    db: Session,
    user_id: UUID,
    provider: str,
    value: str,
    team_id: Optional[str] = None,
) -> None:
    """Upsert token for user and provider."""
    encrypted, iv = encrypt_token(value)
    row = db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.provider == provider,
    ).first()
    if row:
        row.encrypted_value = encrypted
        row.iv = iv
        if team_id is not None:
            row.team_id = team_id
    else:
        row = UserToken(
            user_id=user_id,
            provider=provider,
            encrypted_value=encrypted,
            iv=iv,
            team_id=team_id,
        )
        db.add(row)
    db.commit()


def delete_token(db: Session, user_id: UUID, provider: str) -> bool:
    """Delete token. Returns True if deleted."""
    row = db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.provider == provider,
    ).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def list_tokens(db: Session, user_id: UUID) -> list[dict]:
    """List providers and metadata (not values) for user."""
    rows = db.query(UserToken).filter(UserToken.user_id == user_id).all()
    return [
        {"provider": r.provider, "team_id": r.team_id, "has_value": True}
        for r in rows
    ]
