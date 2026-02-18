"""
App creation API: POST /api/apps/create, GET /api/apps/status/{job_id}
"""
import asyncio
import re
import shutil
import uuid

from fastapi import APIRouter, HTTPException

from models import CreateAppRequest, CreateAppResponse, AppStatusResponse, JobStatus
from job_store import get_status, set_status

router = APIRouter(prefix="/api/apps", tags=["apps"])


def _slug(name: str) -> str:
    """Sanitize app_name for use in paths and repo names."""
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    return s[:80] if s else "app"


def _push_url(repo_url: str, token: str) -> str:
    """Inject token into GitHub HTTPS URL for push."""
    if not token:
        return repo_url
    # Strip any existing token, then add ours
    normalized = re.sub(r"https://(?:x-access-token:[^@]+@)?github\.com/", "https://github.com/", repo_url)
    return normalized.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")


@router.post("/create", response_model=CreateAppResponse)
async def create_app(req: CreateAppRequest) -> CreateAppResponse:
    app_name_slug = _slug(req.app_name)
    if not app_name_slug:
        raise HTTPException(status_code=400, detail="Invalid app name")
    job_id = str(uuid.uuid4())
    set_status(job_id, JobStatus.PENDING, message="Queued")
    asyncio.create_task(_run_pipeline(job_id, req))
    return CreateAppResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=AppStatusResponse)
async def get_app_status(job_id: str) -> AppStatusResponse:
    status = get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


async def _run_pipeline(job_id: str, req: CreateAppRequest) -> None:
    """Background pipeline: Gemini -> write files -> git push -> Vercel deploy."""
    tmpdir = None
    repo_url: str | None = None
    try:
        set_status(job_id, JobStatus.GENERATING, message="Generating app from prompt...")
        from services.gemini_app_gen import generate_app

        tmpdir = await asyncio.to_thread(
            generate_app,
            req.app_name,
            req.description,
            req.prompt,
            api_key=None,
        )
        if not tmpdir:
            raise ValueError("Gemini did not return a directory")

        app_name_slug = _slug(req.app_name)
        set_status(job_id, JobStatus.PUSHING, message="Pushing to Git...")

        from services.git_service import (
            create_github_repo,
            push_directory_to_repo,
        )

        if req.git.create_new or not req.git.repo_url:
            repo_url = await asyncio.to_thread(
                create_github_repo,
                req.git.token,
                app_name_slug,
                req.description or req.app_name,
                private=False,
            )
        else:
            repo_url = req.git.repo_url
        push_url = _push_url(repo_url, req.git.token)

        ok, out = await asyncio.to_thread(
            push_directory_to_repo,
            tmpdir,
            push_url,
            branch="main",
        )
        if not ok:
            raise RuntimeError(f"Git push failed: {out}")

        set_status(job_id, JobStatus.DEPLOYING, message="Creating Vercel project...")
        from services.vercel_service import create_project_from_repo

        vercel_ok, vercel_msg, deploy_url = await asyncio.to_thread(
            create_project_from_repo,
            req.vercel.token,
            app_name_slug,
            repo_url,
            team_id=req.vercel.team_id,
            framework="nextjs",
        )
        if not vercel_ok:
            set_status(
                job_id,
                JobStatus.DONE,
                message="App and repo created; Vercel setup failed",
                repo_url=repo_url,
                deploy_url=None,
                details={"vercel_error": vercel_msg},
            )
        else:
            set_status(
                job_id,
                JobStatus.DONE,
                message="App created and deployed",
                repo_url=repo_url,
                deploy_url=deploy_url,
            )
    except Exception as e:
        set_status(
            job_id,
            JobStatus.FAILED,
            error=str(e),
            message="Creation failed",
        )
    finally:
        if tmpdir:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
