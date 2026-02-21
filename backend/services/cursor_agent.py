"""
Agent flow using Cursor Cloud Agents API.
Requires: CURSOR_API_KEY, CURSOR_GITHUB_TOKEN (or AGENT_GITHUB_TOKEN).
Creates a GitHub repo per session, pushes project dir, launches Cursor agent, polls, pulls changes.
"""
import os
import re
import subprocess
import time
import uuid
from typing import Callable, Optional

from services.cursor_api import (
    add_followup,
    get_agent_conversation,
    launch_agent,
    poll_agent_until_done,
)
from services.git_service import (
    create_github_repo,
    push_directory_to_repo,
    verify_branch_exists,
)

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

    unique_suffix = uuid.uuid4().hex[:8]
    if repo_name and repo_name.strip():
        base = _slug(repo_name.strip())
        repo_name = f"{base}-{unique_suffix}" if base else f"kodbro-app-{unique_suffix}"
    else:
        slug = re.sub(r"[^a-zA-Z0-9-]", "-", session_id)[:36]
        repo_name = f"kodbro-agent-{slug}-{unique_suffix}"
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

    # Verify branch exists (GitHub may need a moment to propagate)
    for attempt in range(5):
        if verify_branch_exists(github_token, repo_url, "main"):
            break
        if attempt < 4:
            time.sleep(2)
    else:
        raise RuntimeError(
            "Branch 'main' not visible on GitHub yet. The push may have succeeded but GitHub needs more time. "
            "Please try again in a minute."
        )
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
        log("[Step] Sending follow-up to Cursor agent...")
        add_followup(api_key, agent_id, user_content)
    else:
        # New agent: create repo, push, launch
        log("[Step] Creating GitHub repository and pushing initial code...")
        repo_url = _ensure_repo_and_push(project_dir, session_id, github_token, repo_name=repo_name)
        push_url = repo_url.replace(
            "https://github.com/",
            f"https://x-access-token:{github_token}@github.com/",
        )
        log("[Step] Launching Cursor agent...")
        # Cursor expects https://github.com/owner/repo (no .git)
        repo_for_cursor = repo_url.rstrip("/").removesuffix(".git")
        resp = launch_agent(
            api_key,
            repository=repo_for_cursor,
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
    log("[Step] Agent running (polling every 5s)...")

    last_status: Optional[str] = None
    last_msg_count = 0
    last_logged_summary = ""
    poll_count = 0

    def _log_agent_output(text: str, prefix: str = "[Agent]") -> None:
        """Log agent output, splitting long text into lines."""
        if not text or not text.strip():
            return
        lines = text.strip().split("\n")
        for line in lines[:12]:
            if line.strip():
                log(f"{prefix} {line[:250]}{'...' if len(line) > 250 else ''}")
        if len(lines) > 12:
            log(f"{prefix} ... ({len(lines) - 12} more lines)")

    def on_poll(status: str, data: dict, elapsed: float) -> None:
        nonlocal last_status, last_msg_count, last_logged_summary, poll_count
        if not on_log:
            return
        poll_count += 1
        summary = data.get("summary", "")
        elapsed_str = f" ({int(elapsed)}s)"

        # Log status when it changes
        if status != last_status:
            last_status = status
            if summary:
                log(f"[Status] {status}{elapsed_str} | {summary[:150]}{'...' if len(summary) > 150 else ''}")
                last_logged_summary = summary
            else:
                log(f"[Status] {status}{elapsed_str}")

        # When RUNNING: show Cursor's output from every available source
        if status == "RUNNING":
            # 1. Log any output-like fields from agent data (including nested)
            for key in ("output", "result", "message", "current_step", "last_message", "progress", "steps", "events", "activity"):
                val = data.get(key)
                if val is None:
                    continue
                if isinstance(val, str) and len(val.strip()) > 10 and val != last_logged_summary:
                    _log_agent_output(val, "[Cursor]")
                    last_logged_summary = val
                elif isinstance(val, dict):
                    text = val.get("text") or val.get("content") or val.get("message")
                    if isinstance(text, str) and len(text.strip()) > 10:
                        _log_agent_output(text, "[Cursor]")
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            t = item.get("text") or item.get("content") or item.get("message") or item.get("output")
                            cmd = item.get("command") or item.get("cmd")
                            if isinstance(t, str) and len(t.strip()) > 5:
                                _log_agent_output(t, "[Step]")
                            if isinstance(cmd, str) and cmd.strip():
                                log(f"[CLI] $ {cmd[:200]}")

            # 2. Log summary updates
            if summary and summary != last_logged_summary and len(summary) > 15:
                last_logged_summary = summary
                _log_agent_output(summary, "[Progress]")

            # 3. Fetch conversation and log ALL messages (assistant, tool, system, etc.)
            try:
                conv = get_agent_conversation(api_key, agent_id)
                msgs = conv.get("messages", []) or []
                for m in msgs[last_msg_count:]:
                    text = (m.get("text") or m.get("content") or m.get("body") or "").strip()
                    msg_type = str(m.get("type", ""))
                    # Log any message with substantial content (assistant, model, tool, command, etc.)
                    if text and len(text) > 20:
                        if "assistant" in msg_type.lower() or msg_type in ("model", "agent"):
                            _log_agent_output(text, "[Agent]")
                        elif "tool" in msg_type.lower() or "command" in msg_type.lower():
                            log(f"[CLI] {text[:300]}{'...' if len(text) > 300 else ''}")
                        elif "step" in msg_type.lower() or "thought" in msg_type.lower():
                            _log_agent_output(text, "[Step]")
                        else:
                            _log_agent_output(text, "[Cursor]")
                last_msg_count = len(msgs)
            except Exception:
                pass

            # 4. Periodic "working" feedback so user sees activity (every 2 polls)
            if poll_count % 2 == 0 and not summary:
                log(f"[Activity] Agent working...{elapsed_str}")

    status, agent_data = poll_agent_until_done(
        api_key,
        agent_id,
        on_poll=on_poll,
    )
    summary = agent_data.get("summary", "")

    # Pull agent's changes into project_dir
    if status == "FINISHED":
        log("[Step] Agent finished. Pulling changes into project...")
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
