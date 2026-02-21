"""
Agent loop: Gemini (function calling) or Cursor Cloud API.
When CURSOR_API_KEY is set, uses Cursor. Otherwise uses Gemini.
"""
import os
import subprocess
from typing import Any, Callable, Optional

GEMINI_MODEL = os.environ.get("GEMINI_APP_MODEL", "gemini-2.0-flash")


def use_cursor_api() -> bool:
    """True if Cursor API is configured (CURSOR_API_KEY set). GitHub token can come from env or user."""
    return bool(os.environ.get("CURSOR_API_KEY"))
COMMAND_TIMEOUT = 120

# Paths must be relative, no .., no leading /
def _validate_path(path: str) -> bool:
    if path is None or path.startswith("/") or ".." in path:
        return False
    if path == "":
        return False
    # Normalize and ensure we don't escape project dir
    normalized = os.path.normpath(path)
    return not normalized.startswith("..")


def read_file(project_dir: str, path: str) -> dict[str, Any]:
    """Read file content. Returns {content: str} or {error: str}."""
    if not _validate_path(path):
        return {"error": "Invalid path"}
    full = os.path.join(project_dir, path)
    if not os.path.abspath(full).startswith(os.path.abspath(project_dir)):
        return {"error": "Path escapes project directory"}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return {"content": f.read()}
    except IsADirectoryError:
        return {"error": "Path is a directory, not a file"}
    except FileNotFoundError:
        return {"error": "File not found"}
    except Exception as e:
        return {"error": str(e)}


def write_file(project_dir: str, path: str, content: str) -> dict[str, Any]:
    """Write file. Returns {success: bool, path: str} or {error: str}."""
    if not _validate_path(path):
        return {"error": "Invalid path"}
    full = os.path.join(project_dir, path)
    if not os.path.abspath(full).startswith(os.path.abspath(project_dir)):
        return {"error": "Path escapes project directory"}
    try:
        d = os.path.dirname(full)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path}
    except Exception as e:
        return {"error": str(e)}


def list_dir(project_dir: str, path: str = ".") -> dict[str, Any]:
    """List directory contents. Returns {entries: [{name, type}], path: str} or {error: str}."""
    if not _validate_path(path):
        return {"error": "Invalid path"}
    full = os.path.join(project_dir, path)
    if not os.path.abspath(full).startswith(os.path.abspath(project_dir)):
        return {"error": "Path escapes project directory"}
    try:
        if not os.path.isdir(full):
            return {"error": "Not a directory"}
        entries = []
        for name in sorted(os.listdir(full)):
            p = os.path.join(full, name)
            entries.append({
                "name": name,
                "type": "directory" if os.path.isdir(p) else "file",
            })
        return {"entries": entries, "path": path}
    except Exception as e:
        return {"error": str(e)}


def run_command(project_dir: str, command: str) -> dict[str, Any]:
    """Run shell command in project directory. Returns {ok, stdout, stderr, exit_code} or {error}."""
    if not command or not command.strip():
        return {"error": "Empty command"}
    try:
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            cwd=project_dir,
            env=os.environ.copy(),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "ok": False}
    except Exception as e:
        return {"error": str(e), "ok": False}


def _format_result_preview(result: dict[str, Any], name: str, max_len: int = 300) -> str:
    """Format tool result for logging. Show more detail for read_file and run_command."""
    if name == "read_file":
        if "error" in result:
            return str(result)
        content = result.get("content", "")
        if content:
            lines = content.split("\n")[:5]
            preview = "\n".join(lines)
            if len(content) > len(preview):
                preview += "\n..."
            return preview[:max_len] + ("..." if len(preview) > max_len else "")
        return str(result)[:max_len]
    if name == "run_command":
        if "error" in result:
            return str(result)
        out = result.get("stdout", "") or ""
        err = result.get("stderr", "") or ""
        exit_code = result.get("exit_code", "")
        parts = []
        if out:
            parts.append(f"stdout: {out[:150]}{'...' if len(out) > 150 else ''}")
        if err:
            parts.append(f"stderr: {err[:150]}{'...' if len(err) > 150 else ''}")
        if exit_code is not None:
            parts.append(f"exit_code={exit_code}")
        return " | ".join(parts) if parts else str(result)[:max_len]
    s = str(result)
    return s[:max_len] + ("..." if len(s) > max_len else "")


def _execute_tool(project_dir: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name and return result dict."""
    if name == "read_file":
        return read_file(project_dir, args.get("path", ""))
    if name == "write_file":
        return write_file(project_dir, args.get("path", ""), args.get("content", ""))
    if name == "list_dir":
        return list_dir(project_dir, args.get("path", "."))
    if name == "run_command":
        return run_command(project_dir, args.get("command", ""))
    return {"error": f"Unknown tool: {name}"}


def _get_tool_declarations() -> list:
    """Return Gemini function declarations for our tools."""
    from google.genai import types

    return [
        types.FunctionDeclaration(
            name="read_file",
            description="Read the contents of a file in the project. Use relative path (e.g. 'src/app/page.tsx').",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative file path"}},
                "required": ["path"],
            },
        ),
        types.FunctionDeclaration(
            name="write_file",
            description="Create or overwrite a file with the given content. Use relative path. Creates parent directories if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
        ),
        types.FunctionDeclaration(
            name="list_dir",
            description="List files and directories in a path. Use '.' for project root.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path, default '.'"}},
                "required": [],
            },
        ),
        types.FunctionDeclaration(
            name="run_command",
            description="Run a shell command in the project directory (e.g. npm install, npm run build). Use for installing deps and building.",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command to run"}},
                "required": ["command"],
            },
        ),
    ]


SYSTEM_INSTRUCTION = """You are an expert app-building agent. You help users create web applications by creating files and running commands in a project directory.

You have access to:
- read_file(path): read a file
- write_file(path, content): create or overwrite a file
- list_dir(path): list directory contents (use "." for project root)
- run_command(command): run shell commands (e.g. npm install, npm run build)

Rules:
- Prefer Next.js or React for web apps. Create package.json, source files, and ensure the app builds.
- After creating files, run npm install and npm run build to verify. If build fails, read the error and fix the code.
- Use relative paths only. Start with list_dir(".") to see the project structure.
- Be concise in replies. After completing a task, summarize what you did.
- If the user asks for an app, create a complete runnable project."""


def run_agent_loop(
    project_dir: str,
    messages: list[dict],
    api_key: Optional[str] = None,
    max_tool_rounds: int = 15,
    on_log: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[str]]:
    """
    Run the agent loop: send messages to Gemini, execute tool calls, repeat until done.
    Returns (final_reply_text, tool_summary_list).
    on_log: optional callback for progress logging (message: str).
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    log("[Step] Starting Gemini agent...")

    from google import genai
    from google.genai import types

    # Retry on 429 RESOURCE_EXHAUSTED with exponential backoff
    http_options = types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=5,
            initial_delay=2.0,
            max_delay=60.0,
            exp_base=2.0,
            http_status_codes=[429, 503],  # Rate limit and service unavailable
        )
    )
    client = genai.Client(api_key=api_key, http_options=http_options)
    tools = types.Tool(function_declarations=_get_tool_declarations())

    # Convert messages to Content format
    def to_content(msg: dict) -> types.Content:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    if "function_call" in p:
                        fc = p["function_call"]
                        parts.append(types.Part.from_function_call(name=fc["name"], args=fc.get("args", {})))
                    elif "function_response" in p:
                        fr = p["function_response"]
                        parts.append(types.Part.from_function_response(name=fr["name"], response=fr["response"]))
                    elif "text" in p:
                        parts.append(types.Part.from_text(text=p["text"]))
                else:
                    parts.append(types.Part.from_text(text=str(p)))
            return types.Content(role=role, parts=parts)
        return types.Content(role=role, parts=[types.Part.from_text(text=str(content))])

    contents = [to_content(m) for m in messages]
    tool_summary: list[str] = []
    rounds = 0

    while rounds < max_tool_rounds:
        rounds += 1
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[tools],
                temperature=0.2,
            ),
        )

        function_calls = response.function_calls if hasattr(response, "function_calls") else None
        if not function_calls:
            text = response.text if hasattr(response, "text") else ""
            log("[Step] Agent finished.")
            return (text or "Done.").strip(), tool_summary

        # Extract and log model reasoning/thinking from text parts
        content = response.candidates[0].content
        if hasattr(content, "parts") and content.parts:
            for part in content.parts:
                if hasattr(part, "text") and part.text and part.text.strip():
                    for line in part.text.strip().split("\n"):
                        log(f"[Thinking] {line}")

        # Add model response (with function calls) to contents
        contents.append(content)

        # Execute tools and build function responses
        user_parts = []
        for fc in function_calls:
            name = fc.name or ""
            args = fc.args or {}
            # Full args for paths and commands (no truncation)
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
            log(f"[Tool] {name}({args_str})")
            result = _execute_tool(project_dir, name, args)
            result_preview = _format_result_preview(result, name)
            log(f"[Result] {result_preview}")
            tool_summary.append(f"{name}({args_str}) -> {result_preview}")
            user_parts.append(types.Part.from_function_response(name=name, response=result))

        log(f"[Round] {rounds}/{max_tool_rounds}")
        contents.append(types.Content(role="user", parts=user_parts))

    return "Reached maximum tool rounds. Please try a simpler request.", tool_summary


def run_agent(
    project_dir: str,
    messages: list[dict],
    session_id: str,
    get_cursor_state,
    set_cursor_state,
    get_user_git=None,
    api_key: Optional[str] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> tuple[str, list[str]]:
    """
    Run agent: uses Cursor API if configured (and GitHub token available), else Gemini.
    get_cursor_state: () -> (agent_id, repo_url)
    set_cursor_state: (agent_id, repo_url) -> None
    get_user_git: () -> (token, repo_name) for user's GitHub connection
    on_log: optional callback for progress logging.
    """
    if use_cursor_api():
        # Cursor API requires GitHub token to create repos; fall back to Gemini if missing
        user_token, _ = get_user_git() if get_user_git else (None, None)
        github_token = (
            user_token
            or os.environ.get("CURSOR_GITHUB_TOKEN")
            or os.environ.get("AGENT_GITHUB_TOKEN")
        )
        if github_token:
            from services.cursor_agent import run_cursor_agent
            return run_cursor_agent(
                project_dir,
                messages,
                session_id,
                get_cursor_state=get_cursor_state,
                set_cursor_state=set_cursor_state,
                get_user_git=get_user_git,
                github_token=github_token,
                api_key=api_key or os.environ.get("CURSOR_API_KEY"),
                on_log=on_log,
            )
        # No GitHub token: use Gemini, inform user they can connect GitHub for Cursor
        def _log(msg: str) -> None:
            if on_log:
                on_log(msg)
        _log("Connect your GitHub account in the app to use Cursor agent. Using Gemini for now.")
    return run_agent_loop(project_dir, messages, api_key, on_log=on_log)
