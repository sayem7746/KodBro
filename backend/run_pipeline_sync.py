"""
Synchronous app-creation pipeline for serverless (e.g. Vercel).
Returns (repo_url, deploy_url) or raises. deploy_url may be None if Vercel step fails.
"""
import re
import shutil
from typing import Any


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    return s[:80] if s else "app"


def _push_url(repo_url: str, token: str) -> str:
    if not token:
        return repo_url
    normalized = re.sub(
        r"https://(?:x-access-token:[^@]+@)?github\.com/", "https://github.com/", repo_url
    )
    return normalized.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")


def run_pipeline_sync(payload: dict[str, Any]) -> tuple[str, str | None]:
    """
    Run the full pipeline synchronously. payload matches CreateAppRequest.
    Returns (repo_url, deploy_url). deploy_url may be None.
    Raises on failure.
    """
    from services.gemini_app_gen import generate_app
    from services.git_service import create_github_repo, push_directory_to_repo
    from services.vercel_service import create_project_from_repo

    app_name = payload["app_name"]
    description = payload.get("description") or ""
    prompt = payload["prompt"]
    git = payload["git"]
    vercel = payload["vercel"]

    tmpdir = generate_app(app_name, description, prompt, api_key=None)
    if not tmpdir:
        raise ValueError("Gemini did not return a directory")

    try:
        app_name_slug = _slug(app_name)
        if git.get("create_new") or not git.get("repo_url"):
            repo_url = create_github_repo(
                git["token"],
                app_name_slug,
                description or app_name,
                private=False,
            )
        else:
            repo_url = git["repo_url"]
        push_url = _push_url(repo_url, git["token"])
        ok, out = push_directory_to_repo(tmpdir, push_url, branch="main")
        if not ok:
            raise RuntimeError(f"Git push failed: {out}")

        vercel_ok, vercel_msg, deploy_url = create_project_from_repo(
            vercel["token"],
            app_name_slug,
            repo_url,
            team_id=vercel.get("team_id"),
            framework="nextjs",
        )
        if not vercel_ok:
            deploy_url = None
        return repo_url, deploy_url
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
