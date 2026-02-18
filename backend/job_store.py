"""
In-memory job store for app creation pipeline status.
"""
from typing import Optional

from models import AppStatusResponse, JobStatus


_store: dict[str, AppStatusResponse] = {}


def set_status(
    job_id: str,
    status: JobStatus,
    message: Optional[str] = None,
    repo_url: Optional[str] = None,
    deploy_url: Optional[str] = None,
    error: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    existing = _store.get(job_id)
    base = existing.model_dump() if existing else {"job_id": job_id}
    _store[job_id] = AppStatusResponse(
        job_id=job_id,
        status=status,
        message=message or base.get("message"),
        repo_url=repo_url or base.get("repo_url"),
        deploy_url=deploy_url or base.get("deploy_url"),
        error=error or base.get("error"),
        details=details or base.get("details"),
    )


def get_status(job_id: str) -> Optional[AppStatusResponse]:
    return _store.get(job_id)
