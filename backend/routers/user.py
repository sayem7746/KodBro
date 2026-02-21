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
    """List app jobs and agent sessions for the current user (build history)."""
    from database import AppJob, AgentSession

    items = []

    # App jobs (create-app flow)
    job_rows = db.query(AppJob).filter(AppJob.user_id == user_id).order_by(AppJob.created_at.desc()).limit(50).all()
    for r in job_rows:
        items.append({
            "id": str(r.id),
            "app_name": r.app_name,
            "status": r.status,
            "repo_url": r.repo_url,
            "deploy_url": r.deploy_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "source": "create-app",
        })

    # Agent sessions (agent/home flow)
    try:
        session_rows = (
            db.query(AgentSession)
            .filter(AgentSession.user_id == user_id)
            .order_by(AgentSession.created_at.desc())
            .limit(50)
            .all()
        )
        for r in session_rows:
            if not r.session_uuid:
                continue
            app_name = getattr(r, "app_name", None) or "Agent app"
            repo_url = r.cursor_repo_url
            deploy_url = getattr(r, "deploy_url", None)
            items.append({
                "id": r.session_uuid,
                "app_name": app_name,
                "status": "deployed" if deploy_url else "agent",
                "repo_url": repo_url,
                "deploy_url": deploy_url,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "source": "agent",
            })
    except Exception:
        pass  # AgentSession may lack new columns on older DBs

    # Sort combined by created_at desc
    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return items[:50]


@router.delete("/jobs/{job_id}")
def delete_user_job(
    job_id: str,
    source: str,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete an app from the user's list and its GitHub repo. source must be 'agent' or 'create-app'."""
    from agent_session_store import delete_session
    from database import AppJob, AgentSession
    from services.git_service import delete_github_repo

    repo_url = None
    if source == "agent":
        row = db.query(AgentSession).filter(
            AgentSession.session_uuid == job_id,
            AgentSession.user_id == user_id,
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="App not found")
        repo_url = getattr(row, "cursor_repo_url", None)
        delete_session(job_id)  # Cleans in-memory store, project dir, and DB
    elif source == "create-app":
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job id")
        row = db.query(AppJob).filter(
            AppJob.id == job_uuid,
            AppJob.user_id == user_id,
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="App not found")
        repo_url = getattr(row, "repo_url", None)
        db.delete(row)
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="source must be 'agent' or 'create-app'")

    # Delete GitHub repo if we have URL and token
    if repo_url and repo_url.strip():
        token = get_token(db, user_id, "github")
        if token:
            ok, msg = delete_github_repo(token, repo_url)
            if not ok:
                # Still return deleted - we removed from our list; GitHub failure is non-blocking
                return {"status": "deleted", "github_deleted": False, "github_message": msg}
            return {"status": "deleted", "github_deleted": True}
    return {"status": "deleted"}


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
