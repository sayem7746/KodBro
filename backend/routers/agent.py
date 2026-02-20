"""
Agent API: sessions, messages, files, deploy.
"""
import asyncio
import re
import shutil

from fastapi import APIRouter, HTTPException

from agent_session_store import (
    create_session,
    get_session,
    get_project_dir,
    append_messages,
    delete_session,
    set_cursor_agent,
    set_user_git,
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


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_agent_session(req: CreateSessionRequest = CreateSessionRequest()):
    """Create a new agent session. Optionally send initial_message to get first reply."""
    session_id = create_session()
    reply = None
    history = None

    if req and req.initial_message and req.initial_message.strip():
        project_dir = get_project_dir(session_id)
        if not project_dir:
            raise HTTPException(status_code=500, detail="Session has no project dir")
        if req.git and req.git.token:
            set_user_git(session_id, token=req.git.token, repo_name=req.git.repo_name)
        append_messages(session_id, "user", req.initial_message.strip())
        try:
            def get_state():
                s = get_session(session_id)
                return (s.cursor_agent_id, s.cursor_repo_url) if s else (None, None)

            def get_user_git_state():
                s = get_session(session_id)
                return (s.user_git_token, s.user_repo_name) if s else (None, None)

            reply_text, tool_summary = await asyncio.to_thread(
                run_agent,
                project_dir,
                [{"role": "user", "content": req.initial_message.strip()}],
                session_id,
                get_cursor_state=get_state,
                set_cursor_state=lambda aid, url: set_cursor_agent(session_id, aid, url),
                get_user_git=get_user_git_state,
            )
        except Exception as e:
            if ClientError and isinstance(e, ClientError) and "429" in str(e):
                raise HTTPException(
                    status_code=503,
                    detail="AI service is temporarily rate-limited. Please try again in a minute.",
                ) from e
            if isinstance(e, (TimeoutError, RuntimeError)) and ("rate limit" in str(e).lower() or "429" in str(e)):
                raise HTTPException(status_code=503, detail=str(e)) from e
            raise
        append_messages(session_id, "assistant", reply_text)
        reply = reply_text
        s = get_session(session_id)
        history = s.messages if s else None

    return CreateSessionResponse(
        session_id=session_id,
        reply=reply,
        message_history=history,
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: str, req: SendMessageRequest):
    """Send a message to the agent and get a reply."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if req.git and req.git.token:
        set_user_git(session_id, token=req.git.token, repo_name=req.git.repo_name)
    append_messages(session_id, "user", req.message)
    messages = session.messages

    try:
        def get_state():
            s = get_session(session_id)
            return (s.cursor_agent_id, s.cursor_repo_url) if s else (None, None)

        def get_user_git_state():
            s = get_session(session_id)
            return (s.user_git_token, s.user_repo_name) if s else (None, None)

        reply_text, tool_summary = await asyncio.to_thread(
            run_agent,
            session.project_dir,
            messages,
            session_id,
            get_cursor_state=get_state,
            set_cursor_state=lambda aid, url: set_cursor_agent(session_id, aid, url),
            get_user_git=get_user_git_state,
        )
    except Exception as e:
        if ClientError and isinstance(e, ClientError) and "429" in str(e):
            raise HTTPException(
                status_code=503,
                detail="AI service is temporarily rate-limited. Please try again in a minute.",
            ) from e
        if isinstance(e, (TimeoutError, RuntimeError)) and ("rate limit" in str(e).lower() or "429" in str(e)):
            raise HTTPException(status_code=503, detail=str(e)) from e
        raise
    append_messages(session_id, "assistant", reply_text)

    return SendMessageResponse(reply=reply_text, tool_summary=tool_summary)


@router.get("/sessions/{session_id}/files", response_model=FilesResponse)
async def get_files(session_id: str, path: str = "."):
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
async def read_file_content(session_id: str, path: str):
    """Read a file's content from the session project."""
    project_dir = get_project_dir(session_id)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Session not found")

    result = tool_read_file(project_dir, path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"content": result["content"]}


@router.post("/sessions/{session_id}/deploy", response_model=AgentDeployResponse)
async def deploy_session(session_id: str, req: AgentDeployRequest):
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
async def delete_agent_session(session_id: str):
    """Delete a session and clean up its project directory."""
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"status": "deleted"}
