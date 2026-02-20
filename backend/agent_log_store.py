"""
In-memory log queue store for agent session streaming.
Used to stream real-time logs from the agent to the frontend via SSE.
Uses queue.Queue (thread-safe) because the agent runs in a thread pool.
"""
import queue
from typing import Optional

_store: dict[str, queue.Queue] = {}


def create_log_queue(session_id: str) -> queue.Queue:
    """Create a log queue for a session. Returns the queue (thread-safe)."""
    q: queue.Queue = queue.Queue()
    _store[session_id] = q
    return q


def get_log_queue(session_id: str) -> Optional[queue.Queue]:
    """Get the log queue for a session, or None if not found."""
    return _store.get(session_id)


def emit_log(session_id: str, message: str, level: str = "info") -> None:
    """Emit a log event. Non-blocking put. Safe to call from sync/threaded code."""
    q = _store.get(session_id)
    if not q:
        return
    event = {"type": "log", "message": message, "level": level}
    try:
        q.put_nowait(event)
    except queue.Full:
        pass


def emit_done(session_id: str, reply: str, tool_summary: Optional[list[str]] = None) -> None:
    """Emit a done event and mark stream complete. Non-blocking put."""
    q = _store.get(session_id)
    if not q:
        return
    event = {"type": "done", "reply": reply, "tool_summary": tool_summary or []}
    try:
        q.put_nowait(event)
    except queue.Full:
        pass


def emit_error(session_id: str, error: str) -> None:
    """Emit an error event. Non-blocking put."""
    q = _store.get(session_id)
    if not q:
        return
    event = {"type": "error", "error": error}
    try:
        q.put_nowait(event)
    except queue.Full:
        pass


def cleanup_log_queue(session_id: str) -> None:
    """Remove the log queue for a session. Call when stream is closed."""
    _store.pop(session_id, None)
