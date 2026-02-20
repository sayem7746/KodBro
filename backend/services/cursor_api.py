"""
Cursor Cloud Agents API client.
Docs: https://cursor.com/docs/api
"""
import base64
import time
from typing import Any, Optional

import httpx

CURSOR_API_BASE = "https://api.cursor.com"


def _auth_header(api_key: str) -> str:
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {encoded}"


def _request(
    method: str,
    path: str,
    api_key: str,
    body: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    url = f"{CURSOR_API_BASE}{path}"
    headers = {"Authorization": _auth_header(api_key)}
    if body:
        headers["Content-Type"] = "application/json"
    with httpx.Client(timeout=60) as client:
        resp = client.request(
            method,
            url,
            json=body,
            params=params,
            headers=headers,
        )
        if resp.status_code == 204:
            return {}
        if not resp.is_success:
            err = resp.json() if resp.content else {}
            msg = err.get("message") or err.get("error") or resp.text or f"HTTP {resp.status_code}"
            if resp.status_code == 429:
                raise RuntimeError(f"Cursor API rate limit: {msg}")
            if resp.status_code == 401:
                raise ValueError(f"Cursor API auth failed: {msg}")
            raise RuntimeError(f"Cursor API error: {msg}")
        return resp.json() if resp.content else {}


def launch_agent(
    api_key: str,
    repository: str,
    prompt_text: str,
    ref: str = "main",
    model: Optional[str] = None,
    branch_name: str = "agent-output",
    auto_create_pr: bool = False,
) -> dict[str, Any]:
    """Create and start a Cursor cloud agent. Returns agent object with id."""
    body: dict[str, Any] = {
        "prompt": {"text": prompt_text},
        "source": {"repository": repository, "ref": ref},
        "target": {
            "branchName": branch_name,
            "autoCreatePr": auto_create_pr,
        },
    }
    if model:
        body["model"] = model
    return _request("POST", "/v0/agents", api_key, body=body)


def get_agent(api_key: str, agent_id: str) -> dict[str, Any]:
    """Get agent status and details."""
    return _request("GET", f"/v0/agents/{agent_id}", api_key)


def get_agent_conversation(api_key: str, agent_id: str) -> dict[str, Any]:
    """Get agent conversation history."""
    return _request("GET", f"/v0/agents/{agent_id}/conversation", api_key)


def add_followup(api_key: str, agent_id: str, prompt_text: str) -> dict[str, Any]:
    """Send follow-up instructions to an agent."""
    return _request(
        "POST",
        f"/v0/agents/{agent_id}/followup",
        api_key,
        body={"prompt": {"text": prompt_text}},
    )


def poll_agent_until_done(
    api_key: str,
    agent_id: str,
    poll_interval: float = 15.0,
    max_wait_seconds: float = 600.0,
) -> tuple[str, dict[str, Any]]:
    """
    Poll agent until FINISHED, FAILED, or STOPPED.
    Returns (status, agent_data).
    """
    start = time.monotonic()
    while True:
        data = get_agent(api_key, agent_id)
        status = data.get("status", "").upper()
        if status in ("FINISHED", "FAILED", "STOPPED"):
            return status, data
        if time.monotonic() - start > max_wait_seconds:
            raise TimeoutError(f"Cursor agent {agent_id} did not finish within {max_wait_seconds}s")
        time.sleep(poll_interval)
