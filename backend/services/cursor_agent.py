"""
Agent flow using Cursor Cloud Agents API.
Requires: CURSOR_API_KEY, CURSOR_GITHUB_TOKEN (or AGENT_GITHUB_TOKEN).
Creates a GitHub repo per session, pushes project dir, launches Cursor agent, polls, pulls changes.
"""
import os
import re
import subprocess
import uuid
from typing import Callable, Optional

from services.cursor_api import (
    add_followup,
    get_agent_conversation,
    launch_agent,
    poll_agent_until_done,
)
from services.git_service import create_github_repo, push_directory_to_repo

CURSOR_AGENT_BRANCH = "agent-output"


def _run(cmd: list[str], cwd: str, timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        out = (r.stdout or "").strip() + "\n" + (r.stderr or "").strip()
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def _slug(name: str) -> str:
    """Slugify for repo name: alphanumeric, hyphens only."""
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    return s[:80] if s else "app"


def _ensure_repo_and_push(
    project_dir: str,
    session_id: str,
    github_token: str,
    repo_name: Optional[str] = None,
) -> str:
    """
    Ensure project_dir has git init and is pushed to a GitHub repo.
    Creates minimal content if dir is empty. Returns public repo URL (no token).
    repo_name: optional user-provided name (e.g. "my-todo-app"); else auto-generated.
    """
    # Ensure we have something to commit (git requires at least one file)
    readme = os.path.join(project_dir, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w") as f:
            f.write("# KodBro Agent Project\n\nCreated by KodBro.\n")

    if repo_name and repo_name.strip():
        repo_name = _slug(repo_name.strip())
    else:
        slug = re.sub(r"[^a-zA-Z0-9-]", "-", session_id)[:36]
        repo_name = f"kodbro-agent-{slug}-{uuid.uuid4().hex[:8]}"
    repo_url = create_github_repo(
        github_token,
        repo_name,
        f"KodBro agent session {session_id}",
        private=True,
    )
    push_url = repo_url.replace(
        "https://github.com/",
        f"https://x-access-token:{github_token}@github.com/",
    )
    ok, out = push_directory_to_repo(project_dir, push_url, branch="main")
    if not ok:
        raise RuntimeError(f"Failed to push to GitHub: {out}")
    return repo_url


def _pull_agent_branch(project_dir: str, branch: str) -> None:
    """Fetch and merge the agent's branch into main so deploy works."""
    ok, _ = _run(["git", "fetch", "origin", branch], project_dir)
    if not ok:
        return
    # Merge agent's work into main so deploy (which pushes main) includes it
    ok, _ = _run(["git", "checkout", "main"], project_dir)
    if not ok:
        return
    ok, _ = _run(["git", "merge", f"origin/{branch}", "-m", "Merge Cursor agent output"], project_dir)


def run_cursor_agent(
    project_dir: str,
    messages: list[dict],
    session_id: str,
    get_cursor_state: Callable[[], tuple[Optional[str], Optional[str]]],
    set_cursor_state: Callable[[str, str], None],
    get_user_git: Callable[[], tuple[Optional[str], Optional[str]]],
    github_token: Optional[str] = None,
    repo_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[str]]:
    """
    Run agent using Cursor Cloud API.
    - First message: create repo, push, launch agent, poll, pull.
    - Subsequent messages: add_followup, poll, pull.
    Returns (reply_text, tool_summary).
    """
    api_key = api_key or os.environ.get("CURSOR_API_KEY")
    user_token, user_repo = get_user_git() if get_user_git else (None, None)
    github_token = github_token or user_token or os.environ.get("CURSOR_GITHUB_TOKEN") or os.environ.get("AGENT_GITHUB_TOKEN")
    repo_name = repo_name or user_repo
    if not api_key:
        raise ValueError("CURSOR_API_KEY not set")
    if not github_token:
        raise ValueError(
            "Connect your GitHub account (Personal access token) or set CURSOR_GITHUB_TOKEN. "
            "Required for Cursor agent to create repositories."
        )

    # Get latest user message
    user_content = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            user_content = content if isinstance(content, str) else str(content)
            break
    if not user_content.strip():
        return "No message to send.", []

    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    agent_id, repo_url = get_cursor_state()
    if agent_id and repo_url:
        # Follow-up to existing agent
        log("Sending follow-up to Cursor agent...")
        add_followup(api_key, agent_id, user_content)
    else:
        # New agent: create repo, push, launch
        log("Creating GitHub repository and pushing initial code...")
        repo_url = _ensure_repo_and_push(project_dir, session_id, github_token, repo_name=repo_name)
        push_url = repo_url.replace(
            "https://github.com/",
            f"https://x-access-token:{github_token}@github.com/",
        )
        log("Launching Cursor agent...")
        resp = launch_agent(
            api_key,
            repository=repo_url,
            prompt_text=user_content,
            ref="main",
            model=model,
            branch_name=CURSOR_AGENT_BRANCH,
            auto_create_pr=False,
        )
        agent_id = resp.get("id")
        if not agent_id:
            raise RuntimeError("Cursor API did not return agent id")
        set_cursor_state(agent_id, repo_url)

    # Poll until done
    log("Agent running (polling every 15s)...")
    status, agent_data = poll_agent_until_done(
        api_key,
        agent_id,
        on_poll=lambda s, d: log(f"Poll: status={s}") if on_log else None,
    )
    summary = agent_data.get("summary", "")

    # Pull agent's changes into project_dir
    if status == "FINISHED":
        log("Agent finished. Pulling changes...")
        _pull_agent_branch(project_dir, CURSOR_AGENT_BRANCH)

    # Get conversation for reply text
    conv = get_agent_conversation(api_key, agent_id)
    reply_parts = []
    for msg in conv.get("messages", []) or []:
        if msg.get("type") == "assistant_message":
            reply_parts.append(msg.get("text", ""))
    reply_text = reply_parts[-1] if reply_parts else (summary or f"Agent {status}.")

    tool_summary = [f"Cursor agent {status}: {summary[:80]}" if summary else f"Cursor agent {status}"]
    return reply_text.strip(), tool_summary
