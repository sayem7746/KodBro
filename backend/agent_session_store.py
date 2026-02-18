"""
In-memory session store for the app-building agent.
Each session has a project directory and message history.
"""
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Optional, Union

PREFIX = "kodbro_agent_"


@dataclass
class AgentSession:
    session_id: str
    project_dir: str
    messages: list[dict] = field(default_factory=list)


_store: dict[str, AgentSession] = {}


def create_session() -> str:
    """Create a new session with an empty project directory. Returns session_id."""
    session_id = str(uuid.uuid4())
    project_dir = tempfile.mkdtemp(prefix=PREFIX)
    _store[session_id] = AgentSession(
        session_id=session_id,
        project_dir=project_dir,
        messages=[],
    )
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


def delete_session(session_id: str) -> None:
    """Remove session and clean up its project directory."""
    s = _store.pop(session_id, None)
    if s and s.project_dir and os.path.isdir(s.project_dir):
        try:
            shutil.rmtree(s.project_dir, ignore_errors=True)
        except Exception:
            pass
