#!/usr/bin/env python3
"""
Terminal backend: WebSocket (interactive PTY) + HTTP API for running commands.
- WebSocket at /ws  -> interactive shell (connect from app)
- POST /api/run     -> run a single command, get stdout/stderr/exit_code
Run: uvicorn server:app --host 0.0.0.0 --port 8765
"""

import asyncio
import os
import sys
import fcntl
import signal
import subprocess
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.websockets import WebSocket

try:
    import uvicorn
except ImportError:
    uvicorn = None

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8765))
SHELL = os.environ.get("SHELL", "/bin/bash")

# ----- HTTP API -----


class RunCommandRequest(BaseModel):
    command: str
    timeout_seconds: Optional[int] = 30
    cwd: Optional[str] = None


class RunCommandResponse(BaseModel):
    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def run_command(command: str, timeout_seconds: int = 30, cwd: Optional[str] = None) -> RunCommandResponse:
    """Run a single command in a subprocess and return output."""
    if not command or not command.strip():
        return RunCommandResponse(ok=False, stdout="", stderr="Command is empty", exit_code=-1)
    try:
        result = subprocess.run(
            [SHELL, "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd or None,
            env=os.environ.copy(),
        )
        return RunCommandResponse(
            ok=result.returncode == 0,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return RunCommandResponse(
            ok=False,
            stdout="",
            stderr="",
            exit_code=-1,
            timed_out=True,
        )
    except Exception as e:
        return RunCommandResponse(
            ok=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
        )


app = FastAPI(title="KodBro Terminal API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/run", response_model=RunCommandResponse)
async def api_run(req: RunCommandRequest) -> RunCommandResponse:
    """Run a terminal command and return stdout, stderr, and exit code."""
    return run_command(
        req.command,
        timeout_seconds=req.timeout_seconds or 30,
        cwd=req.cwd,
    )


@app.get("/api/health")
async def health() -> dict:
    # Temporary debug output for agent endpoint troubleshooting
    debug: dict = {}
    try:
        debug["gemini_api_key_set"] = bool(os.environ.get("GEMINI_API_KEY"))
        debug["cursor_api_key_set"] = bool(os.environ.get("CURSOR_API_KEY"))
        debug["cursor_github_token_set"] = bool(
            os.environ.get("CURSOR_GITHUB_TOKEN") or os.environ.get("AGENT_GITHUB_TOKEN")
        )
        try:
            from services.agent_loop import run_agent, use_cursor_api
            debug["agent_loop_import"] = "ok"
            debug["agent_backend"] = "cursor" if use_cursor_api() else "gemini"
        except Exception as e:
            debug["agent_loop_import"] = f"error: {type(e).__name__}: {str(e)}"
        try:
            from google import genai
            debug["google_genai_import"] = "ok"
        except Exception as e:
            debug["google_genai_import"] = f"error: {type(e).__name__}: {str(e)}"
        try:
            from agent_session_store import create_session, get_project_dir
            debug["session_store_import"] = "ok"
        except Exception as e:
            debug["session_store_import"] = f"error: {type(e).__name__}: {str(e)}"
    except Exception as e:
        debug["debug_error"] = f"{type(e).__name__}: {str(e)}"
    return {"status": "ok", "service": "terminal-api", "debug": debug}


# ----- App creation API -----
from routers.apps import router as apps_router
app.include_router(apps_router)

# ----- Agent API -----
from routers.agent import router as agent_router
app.include_router(agent_router)


# ----- WebSocket PTY (interactive terminal) -----


def set_fd_nonblocking(fd: int) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def spawn_pty() -> tuple[int, int]:
    """Spawn a shell in a PTY. Returns (master_fd, pid)."""
    master, slave = os.openpty()
    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        if slave > 2:
            os.close(slave)
        os.execv(SHELL, [SHELL, "-l", "-i"])
        os._exit(127)
    os.close(slave)
    set_fd_nonblocking(master)
    return master, pid


async def bridge_pty_ws(master_fd: int, ws: WebSocket) -> None:
    loop = asyncio.get_event_loop()

    def read_from_pty() -> Optional[str]:
        try:
            data = os.read(master_fd, 4096)
            if data:
                return data.decode("utf-8", errors="replace")
        except (OSError, BlockingIOError):
            pass
        return None

    async def send_pty_output():
        def on_readable():
            text = read_from_pty()
            if text:
                asyncio.create_task(ws.send_text(text))

        loop.add_reader(master_fd, on_readable)
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.receive":
                    if "text" in msg:
                        os.write(master_fd, msg["text"].encode("utf-8"))
                    elif "bytes" in msg:
                        os.write(master_fd, msg["bytes"])
                elif msg["type"] == "websocket.disconnect":
                    break
        except Exception:
            pass
        finally:
            loop.remove_reader(master_fd)
            try:
                os.close(master_fd)
            except OSError:
                pass


@app.websocket("/ws")
async def websocket_terminal(websocket: WebSocket) -> None:
    """Interactive PTY over WebSocket (same as before)."""
    await websocket.accept()
    master_fd, pid = spawn_pty()
    try:
        await bridge_pty_ws(master_fd, websocket)
    finally:
        try:
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        except (OSError, ChildProcessError):
            pass


# ----- Entrypoint -----


def main() -> None:
    if sys.platform == "win32":
        print("This server requires a Unix-like system (PTY). Use WSL or Linux/macOS.", file=sys.stderr)
        sys.exit(1)
    if uvicorn is None:
        print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    print(f"Terminal API: http://{HOST}:{PORT}")
    print("  POST /api/run  - run a command (JSON: {{\"command\": \"ls\"}})")
    print("  WebSocket /ws  - interactive terminal")
    print("Ctrl+C to stop.")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
