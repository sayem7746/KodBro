"""
In-memory session store for the app-building agent.
Each session has a project directory and message history.
Persists metadata to DB when DATABASE_URL is set.
"""
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Optional, Union
from uuid import UUID

PREFIX = "kodbro_agent_"


@dataclass
class AgentSession:
    session_id: str
    project_dir: str
    messages: list[dict] = field(default_factory=list)
    cursor_agent_id: Optional[str] = None
    cursor_repo_url: Optional[str] = None
    user_git_token: Optional[str] = None
    user_repo_name: Optional[str] = None


_store: dict[str, AgentSession] = {}


def _use_db() -> bool:
    try:
        from database import SessionLocal
        return SessionLocal is not None
    except Exception:
        return False


def create_session(user_id: Optional[UUID] = None) -> str:
    """Create a new session with an empty project directory. Returns session_id."""
    session_id = str(uuid.uuid4())
    project_dir = tempfile.mkdtemp(prefix=PREFIX)
    _store[session_id] = AgentSession(
        session_id=session_id,
        project_dir=project_dir,
        messages=[],
    )
    if _use_db() and user_id:
        try:
            from database import AgentSession as AgentSessionModel, SessionLocal
            db = SessionLocal()
            row = AgentSessionModel(user_id=user_id, session_uuid=session_id)
            db.add(row)
            db.commit()
            db.close()
        except Exception:
            pass
    return session_id


def get_session(session_id: str) -> Optional[AgentSession]:
    """Get session by id, or None if not found."""
    return _store.get(session_id)


def get_project_dir(session_id: str) -> Optional[str]:
    """Get project directory for session, or None if not found."""
    s = _store.get(session_id)
    return s.project_dir if s else None


def append_messages(session_id: str, role: str, content: Union[str, list]) -> None:
    """Append a message (user or assistant) to session history."""
    s = _store.get(session_id)
    if not s:
        raise KeyError(f"Session {session_id} not found")
    s.messages.append({"role": role, "content": content})
    if _use_db() and role == "assistant":
        try:
            from database import AgentSession as AgentSessionModel, SessionLocal
            db = SessionLocal()
            row = db.query(AgentSessionModel).filter(AgentSessionModel.session_uuid == session_id).first()
            if row:
                row.message_count = (row.message_count or 0) + 1
                db.commit()
            db.close()
        except Exception:
            pass


def set_cursor_agent(session_id: str, agent_id: str, repo_url: str) -> None:
    """Store Cursor agent id and repo URL for follow-ups."""
    s = _store.get(session_id)
    if not s:
        raise KeyError(f"Session {session_id} not found")
    s.cursor_agent_id = agent_id
    s.cursor_repo_url = repo_url
    if _use_db():
        try:
            from database import AgentSession as AgentSessionModel, SessionLocal
            db = SessionLocal()
            row = db.query(AgentSessionModel).filter(AgentSessionModel.session_uuid == session_id).first()
            if row:
                row.cursor_agent_id = agent_id
                row.cursor_repo_url = repo_url
                db.commit()
            db.close()
        except Exception:
            pass


def set_user_git(session_id: str, token: Optional[str] = None, repo_name: Optional[str] = None) -> None:
    """Store user's GitHub token and repo name for Cursor agent."""
    s = _store.get(session_id)
    if not s:
        raise KeyError(f"Session {session_id} not found")
    if token is not None:
        s.user_git_token = token
    if repo_name is not None:
        s.user_repo_name = repo_name


def delete_session(session_id: str) -> None:
    """Remove session and clean up its project directory."""
    s = _store.pop(session_id, None)
    if s and s.project_dir and os.path.isdir(s.project_dir):
        try:
            shutil.rmtree(s.project_dir, ignore_errors=True)
        except Exception:
            pass
