"""
User tokens API: GET /api/user/tokens, PUT /api/user/tokens/{provider}
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user_id
from services.token_service import get_token, list_tokens, set_token

router = APIRouter(prefix="/api/user", tags=["user"])


class TokenPutRequest(BaseModel):
    value: str = Field(..., min_length=1)
    team_id: str | None = Field(None)


class TokenResponse(BaseModel):
    provider: str
    team_id: str | None
    has_value: bool


@router.get("/tokens", response_model=list[TokenResponse])
def list_user_tokens(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """List stored token providers (values are never returned)."""
    return list_tokens(db, user_id)


@router.get("/tokens/{provider}")
def get_user_token(
    provider: str,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get decrypted token for a provider. Used by agent/apps when user has stored tokens."""
    value = get_token(db, user_id, provider.lower())
    if value is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"provider": provider, "value": value}


@router.get("/jobs")
def list_user_jobs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """List app jobs for the current user."""
    from database import AppJob
    rows = db.query(AppJob).filter(AppJob.user_id == user_id).order_by(AppJob.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(r.id),
            "app_name": r.app_name,
            "status": r.status,
            "repo_url": r.repo_url,
            "deploy_url": r.deploy_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.put("/tokens/{provider}")
def put_user_token(
    provider: str,
    req: TokenPutRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Store or update token for a provider (github, vercel, railway)."""
    valid = {"github", "vercel", "railway"}
    if provider.lower() not in valid:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {valid}")
    set_token(db, user_id, provider.lower(), req.value, team_id=req.team_id)
    return {"status": "ok", "provider": provider}
