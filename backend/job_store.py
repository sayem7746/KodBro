"""
Job store for app creation pipeline. Uses PostgreSQL when DATABASE_URL is set.
Falls back to in-memory when not configured.
"""
from typing import Optional
from uuid import UUID

from models import AppStatusResponse, JobStatus

# In-memory fallback when DB not configured
_memory_store: dict[str, AppStatusResponse] = {}


def use_db() -> bool:
    try:
        from database import SessionLocal
        return SessionLocal is not None
    except Exception:
        return False


def create_job(
    user_id: UUID,
    app_name: str,
    description: str = "",
    prompt: str = "",
) -> str:
    """Create a new job. Returns job_id."""
    if use_db():
        from database import AppJob, SessionLocal
        db = SessionLocal()
        try:
            job = AppJob(
                user_id=user_id,
                app_name=app_name,
                description=description or None,
                prompt=prompt or None,
                status=JobStatus.PENDING.value,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = str(job.id)
            _memory_store[job_id] = AppStatusResponse(
                job_id=job_id,
                status=JobStatus.PENDING,
                message="Queued",
            )
            return job_id
        finally:
            db.close()
    job_id = str(__import__("uuid").uuid4())
    _memory_store[job_id] = AppStatusResponse(
        job_id=str(job_id),
        status=JobStatus.PENDING,
        message="Queued",
    )
    return job_id


def set_status(
    job_id: str,
    status: JobStatus,
    message: Optional[str] = None,
    repo_url: Optional[str] = None,
    deploy_url: Optional[str] = None,
    error: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    existing = get_status(job_id)
    base = existing.model_dump() if existing else {"job_id": job_id}
    updated = AppStatusResponse(
        job_id=job_id,
        status=status,
        message=message or base.get("message"),
        repo_url=repo_url or base.get("repo_url"),
        deploy_url=deploy_url or base.get("deploy_url"),
        error=error or base.get("error"),
        details=details or base.get("details"),
    )
    _memory_store[job_id] = updated
    if use_db():
        from database import AppJob, SessionLocal
        from uuid import UUID
        db = SessionLocal()
        try:
            try:
                uid = UUID(job_id)
            except ValueError:
                return
            row = db.query(AppJob).filter(AppJob.id == uid).first()
            if row:
                row.status = status.value
                row.repo_url = repo_url
                row.deploy_url = deploy_url
                row.error = error
                row.details = details
                db.commit()
        finally:
            db.close()


def get_status(job_id: str) -> Optional[AppStatusResponse]:
    if job_id in _memory_store:
        return _memory_store[job_id]
    if use_db():
        from database import AppJob, SessionLocal
        from uuid import UUID
        db = SessionLocal()
        try:
            try:
                uid = UUID(job_id)
            except ValueError:
                return None
            row = db.query(AppJob).filter(AppJob.id == uid).first()
            if not row:
                return None
            resp = AppStatusResponse(
                job_id=job_id,
                status=JobStatus(row.status),
                message=row.status.replace("_", " ").title() if row.status else None,
                repo_url=row.repo_url,
                deploy_url=row.deploy_url,
                error=row.error,
                details=row.details,
            )
            _memory_store[job_id] = resp
            return resp
        finally:
            db.close()
    return None
