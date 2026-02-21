"""
Auth API: signup, login.
"""
import sys
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth_utils import create_access_token, hash_password, verify_password
from database import User, get_db, init_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.get("/debug")
def auth_debug():
    """Debug endpoint: hash scheme, bcrypt version, test hash. No auth required."""
    info = {
        "hash_scheme": "bcrypt_sha256",
        "note": "bcrypt_sha256 pre-hashes with SHA-256, avoiding bcrypt 72-byte limit",
    }
    try:
        import passlib
        info["passlib_version"] = getattr(passlib, "__version__", "unknown")
    except Exception as e:
        info["passlib_error"] = str(e)
    try:
        import bcrypt
        info["bcrypt_version"] = getattr(bcrypt, "__version__", "unknown")
    except Exception as e:
        info["bcrypt_error"] = str(e)
    try:
        # Test hash a 100-byte password to verify no 72-byte error
        test_pw = "a" * 100
        hashed = hash_password(test_pw)
        ok = verify_password(test_pw, hashed)
        info["test_100_char_password"] = "ok" if ok else "verify_failed"
        info["test_hash_prefix"] = hashed[:30] + "..." if len(hashed) > 30 else hashed
    except Exception as e:
        info["test_100_char_password"] = f"error: {type(e).__name__}: {str(e)}"
        print(f"auth_debug test hash failed: {e}", file=sys.stderr)
    return info


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    try:
        # Debug: log password length (bytes) - helps diagnose 72-byte issues
        pw_bytes = len(req.password.encode("utf-8"))
        if pw_bytes > 72:
            print(f"signup: password {pw_bytes} bytes (bcrypt_sha256 handles this)", file=sys.stderr)
        existing = db.query(User).filter(User.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            display_name=req.display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.email)
        return AuthResponse(
            access_token=token,
            user_id=str(user.id),
            email=user.email,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        db.rollback()
        err_msg = f"{type(e).__name__}: {str(e)}"
        print(f"signup error: {err_msg}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=err_msg)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Sign in and get JWT."""
    try:
        user = db.query(User).filter(User.email == req.email).first()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = create_access_token(user.id, user.email)
        return AuthResponse(
            access_token=token,
            user_id=str(user.id),
            email=user.email,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
