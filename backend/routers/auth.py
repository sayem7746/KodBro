"""
Auth API: signup, login.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth_utils import create_access_token, hash_password, verify_password
from database import User, get_db, init_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Bcrypt limit; reject longer passwords with clear error
PASSWORD_MAX_BYTES = 72


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


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    if len(req.password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Password cannot exceed 72 bytes (use a shorter password)",
        )
    try:
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
        raise HTTPException(status_code=500, detail=str(e))


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
