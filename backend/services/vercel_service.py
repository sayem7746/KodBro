"""
Create a Vercel project linked to a GitHub repo and return deploy URL.
"""
import re
from typing import Optional

import httpx

VERCEL_API = "https://api.vercel.com"


def _repo_slug(repo_url: str) -> Optional[str]:
    """Extract owner/repo from GitHub URL."""
    # https://github.com/owner/repo or https://x-access-token:token@github.com/owner/repo.git
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def create_project_from_repo(
    token: str,
    project_name: str,
    repo_url: str,
    team_id: Optional[str] = None,
    framework: str = "nextjs",
) -> tuple[bool, str, Optional[str]]:
    """
    Create a Vercel project linked to the GitHub repo.
    Returns (success, message, deploy_url).
    Repo must already exist and be pushed; Vercel will trigger first deployment.
    """
    slug = _repo_slug(repo_url)
    if not slug:
        return False, "Invalid GitHub repo URL", None

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{VERCEL_API}/v11/projects"
    payload = {
        "name": project_name,
        "framework": framework,
        "gitRepository": {"type": "github", "repo": slug},
    }
    if team_id:
        payload["teamId"] = team_id

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 201:
                data = resp.json()
                # Project created; first deployment may be triggered automatically
                link = data.get("link") or data.get("project", {}).get("link")
                if link:
                    deploy_url = f"https://{link}" if not link.startswith("http") else link
                else:
                    deploy_url = f"https://{project_name}.vercel.app"
                return True, "Project created", deploy_url
            err = resp.text
            return False, err or f"HTTP {resp.status_code}", None
    except Exception as e:
        return False, str(e), None
