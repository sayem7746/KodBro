"""
Agent API: sessions, messages, files, deploy.
"""
import asyncio
import json
import queue
import re
import shutil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent_log_store import (
    create_log_queue,
    emit_done,
    emit_error,
    emit_log,
    get_log_queue,
    cleanup_log_queue,
)
from agent_session_store import (
    create_session,
    get_session,
    get_project_dir,
    append_messages,
    delete_session,
    set_cursor_agent,
    set_user_git,
    update_session_metadata,
)

# Import for 429 rate limit error handling (Gemini)
try:
    from google.genai.errors import ClientError
except ImportError:
    ClientError = None
from models import (
    CreateSessionRequest,
    CreateSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
    AgentDeployRequest,
    AgentDeployResponse,
    FileEntry,
    FilesResponse,
)
from deps import get_current_user_id
from services.agent_loop import run_agent, read_file as tool_read_file, list_dir as tool_list_dir

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")
    return s[:80] if s else "app"


def _push_url(repo_url: str, token: str) -> str:
    if not token:
        return repo_url
    normalized = re.sub(r"https://(?:x-access-token:[^@]+@)?github\.com/", "https://github.com/", repo_url)
    return normalized.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")


def _run_agent_with_messages(session_id: str, messages: list) -> None:
    """Run agent with given messages; emit logs and done. Used by both create and send_message."""
    project_dir = get_project_dir(session_id)
    if not project_dir:
        emit_error(session_id, "Session has no project dir")
        return
    try:
        def on_log(msg: str) -> None:
            emit_log(session_id, msg)

        def get_state():
            s = get_session(session_id)
            return (s.cursor_agent_id, s.cursor_repo_url) if s else (None, None)

        def get_user_git_state():
            s = get_session(session_id)
            return (s.user_git_token, s.user_repo_name) if s else (None, None)

        reply_text, tool_summary = run_agent(
            project_dir,
            messages,
            session_id,
            get_cursor_state=get_state,
            set_cursor_state=lambda aid, url: set_cursor_agent(session_id, aid, url),
            get_user_git=get_user_git_state,
            on_log=on_log,
        )
        emit_done(session_id, reply_text, tool_summary)
        append_messages(session_id, "assistant", reply_text)
    except Exception as e:
        err_msg = str(e)
        if ClientError and isinstance(e, ClientError) and "429" in str(e):
            err_msg = "AI service is temporarily rate-limited. Please try again in a minute."
        elif isinstance(e, (TimeoutError, RuntimeError)) and ("rate limit" in str(e).lower() or "429" in str(e)):
            err_msg = str(e)
        emit_error(session_id, err_msg)
        emit_done(session_id, f"Error: {err_msg}", [])


async def _run_agent_background(session_id: str, initial_message: str) -> None:
    """Background task: run agent with log streaming, emit_done, append assistant reply."""
    await asyncio.to_thread(
        _run_agent_with_messages,
        session_id,
        [{"role": "user", "content": initial_message}],
    )


async def _run_agent_for_message_background(session_id: str) -> None:
    """Background task for send_message: run agent with full session messages, stream logs."""
    session = get_session(session_id)
    if not session:
        emit_error(session_id, "Session not found")
        return
    await asyncio.to_thread(_run_agent_with_messages, session_id, session.messages)


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_agent_session(
    req: CreateSessionRequest = CreateSessionRequest(),
    user_id: UUID = Depends(get_current_user_id),
):
    """Create a new agent session. Optionally send initial_message to get first reply.
    When initial_message is present, returns session_id immediately and runs agent in background.
    Connect to GET /sessions/{session_id}/stream for real-time logs."""
    session_id = create_session(user_id=user_id)
    reply = None
    history = None

    if req and req.initial_message and req.initial_message.strip():
        project_dir = get_project_dir(session_id)
        if not project_dir:
            raise HTTPException(status_code=500, detail="Session has no project dir")
        if req.git and req.git.token:
            set_user_git(session_id, token=req.git.token, repo_name=req.git.repo_name)
        append_messages(session_id, "user", req.initial_message.strip())

        app_name = (req.initial_message.strip() or "Agent app")[:255]
        update_session_metadata(session_id, app_name=app_name)

        create_log_queue(session_id)
        asyncio.create_task(_run_agent_background(session_id, req.initial_message.strip()))
        return CreateSessionResponse(session_id=session_id, reply=None, message_history=None)

    return CreateSessionResponse(
        session_id=session_id,
        reply=reply,
        message_history=history,
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session_logs(
    session_id: str,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
):
    """SSE stream of agent logs. Connect after create_session (with initial_message) or send_message."""
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    q = get_log_queue(session_id)
    if not q:
        raise HTTPException(status_code=404, detail="No log stream for this session")

    STREAM_TIMEOUT = 300  # 5 minutes without event

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=30)
                    )
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                except Exception:
                    break
                if event.get("type") == "log":
                    yield f"event: log\ndata: {json.dumps(event)}\n\n"
                elif event.get("type") == "done":
                    yield f"event: done\ndata: {json.dumps(event)}\n\n"
                    break
                elif event.get("type") == "error":
                    yield f"event: error\ndata: {json.dumps(event)}\n\n"
                    err_msg = event.get("error", "Unknown")
                    yield f"event: done\ndata: {json.dumps({'type': 'done', 'reply': f'Error: {err_msg}', 'tool_summary': []})}\n\n"
                    break
        finally:
            cleanup_log_queue(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: str,
    req: SendMessageRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """Send a message to the agent. Returns streaming=True; connect to GET /stream for logs and reply."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.git and req.git.token:
        set_user_git(session_id, token=req.git.token, repo_name=req.git.repo_name)
    append_messages(session_id, "user", req.message)

    create_log_queue(session_id)
    asyncio.create_task(_run_agent_for_message_background(session_id))

    return SendMessageResponse(reply=None, tool_summary=None, streaming=True)


@router.get("/sessions/{session_id}/files", response_model=FilesResponse)
async def get_files(
    session_id: str,
    path: str = ".",
    user_id: UUID = Depends(get_current_user_id),
):
    """List files in the session project directory."""
    project_dir = get_project_dir(session_id)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Session not found")

    result = tool_list_dir(project_dir, path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    entries = [FileEntry(name=e["name"], type=e["type"]) for e in result.get("entries", [])]
    return FilesResponse(entries=entries, path=result.get("path", path))


@router.get("/sessions/{session_id}/files/read")
async def read_file_content(
    session_id: str,
    path: str,
    user_id: UUID = Depends(get_current_user_id),
):
    """Read a file's content from the session project."""
    project_dir = get_project_dir(session_id)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Session not found")

    result = tool_read_file(project_dir, path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"content": result["content"]}


@router.post("/sessions/{session_id}/deploy", response_model=AgentDeployResponse)
async def deploy_session(
    session_id: str,
    req: AgentDeployRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """Deploy the session project to GitHub and Vercel."""
    project_dir = get_project_dir(session_id)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Session not found")

    app_name_slug = _slug(req.app_name)
    if not app_name_slug:
        raise HTTPException(status_code=400, detail="Invalid app name")

    from services.git_service import create_github_repo, push_directory_to_repo
    from services.vercel_service import create_project_from_repo

    try:
        if req.git.create_new or not req.git.repo_url:
            repo_url = await asyncio.to_thread(
                create_github_repo,
                req.git.token,
                app_name_slug,
                req.app_name,
                private=False,
            )
        else:
            repo_url = req.git.repo_url

        push_url = _push_url(repo_url, req.git.token)
        ok, out = await asyncio.to_thread(
            push_directory_to_repo,
            project_dir,
            push_url,
            branch="main",
        )
        if not ok:
            return AgentDeployResponse(repo_url="", deploy_url=None, error=f"Git push failed: {out}")

        vercel_ok, vercel_msg, deploy_url = await asyncio.to_thread(
            create_project_from_repo,
            req.vercel.token,
            app_name_slug,
            repo_url,
            team_id=req.vercel.team_id,
            framework="nextjs",
        )

        if vercel_ok and deploy_url:
            update_session_metadata(session_id, deploy_url=deploy_url, repo_url=repo_url)

        return AgentDeployResponse(
            repo_url=repo_url,
            deploy_url=deploy_url,
            error=None if vercel_ok else vercel_msg,
        )
    except Exception as e:
        return AgentDeployResponse(repo_url="", deploy_url=None, error=str(e))
    finally:
        # Optionally keep session for "view files" - for now we don't delete on deploy
        pass


@router.delete("/sessions/{session_id}")
async def delete_agent_session(
    session_id: str,
    user_id: UUID = Depends(get_current_user_id),
):
    """Delete a session and clean up its project directory."""
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"status": "deleted"}
