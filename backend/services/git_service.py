"""
Push a local directory to a Git remote (GitHub) using user token.
Supports existing repo URL or create-new via GitHub API.
"""
import os
import subprocess
from typing import Optional

import httpx


def _run(cmd: list[str], cwd: str, env: Optional[dict] = None) -> tuple[bool, str]:
    env = {**os.environ, **(env or {})}
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        out = (r.stdout or "").strip() + "\n" + (r.stderr or "").strip()
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def create_github_repo(token: str, name: str, description: str, private: bool = False) -> str:
    """Create a GitHub repo and return public clone URL (no token). Use push_url with token for push."""
    url = "https://api.github.com/user/repos"
    payload = {"name": name, "description": description, "private": private}
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github.v3+json",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload, headers=headers)
        err_body = resp.json() if resp.content and resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 403:
            msg = err_body.get("message", "Forbidden")
            hint = "Check that your token has the 'repo' scope (classic) or 'Contents' + 'Metadata' write (fine-grained). Token may be expired."
            raise RuntimeError(f"GitHub API 403: {msg}. {hint}")
        if resp.status_code == 422:
            msg = err_body.get("message", "Validation failed")
            errors = err_body.get("errors", [])
            details = "; ".join(e.get("message", str(e)) for e in errors) if errors else msg
            raise RuntimeError(f"GitHub API 422: {details}. Common causes: repository name already exists, or invalid name format.")
        resp.raise_for_status()
        data = resp.json()
        return data.get("clone_url") or (data.get("html_url", "") + ".git")


def push_directory_to_repo(
    local_dir: str,
    repo_url: str,
    branch: str = "main",
    git_user_name: str = "KodBro",
    git_user_email: str = "noreply@kodbro.com",
) -> tuple[bool, str]:
    """
    Initialize git in local_dir, add all, commit, add remote, push to repo_url.
    repo_url should be HTTPS (can include token for auth).
    """
    ok, out = _run(["git", "init", "-b", branch], local_dir)
    if not ok:
        return False, out
    ok, out = _run(
        ["git", "config", "user.name", git_user_name],
        local_dir,
    )
    if not ok:
        return False, out
    ok, out = _run(
        ["git", "config", "user.email", git_user_email],
        local_dir,
    )
    if not ok:
        return False, out
    ok, out = _run(["git", "add", "-A"], local_dir)
    if not ok:
        return False, out
    ok, out = _run(["git", "commit", "-m", "Initial commit from KodBro"], local_dir)
    if not ok:
        # Maybe nothing to commit (empty repo?)
        if "nothing to commit" in out.lower():
            pass
        else:
            return False, out
    ok, out = _run(["git", "remote", "add", "origin", repo_url], local_dir)
    if not ok and "already exists" not in out:
        return False, out
    if "already exists" in out:
        _run(["git", "remote", "set-url", "origin", repo_url], local_dir)
    ok, out = _run(["git", "push", "-u", "origin", branch, "--force"], local_dir)
    return ok, out
