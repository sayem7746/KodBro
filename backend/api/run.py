"""
Vercel serverless function: POST /api/run
Run a terminal command and return stdout, stderr, exit_code.
Body: {"command": "ls -la", "timeout_seconds": 10}
"""
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler

# Vercel serverless timeout is 10s (hobby) / 60s (pro) - cap at 10 for portability
MAX_TIMEOUT = 10
SHELL = os.environ.get("SHELL", "sh")


def run_command(command: str, timeout_seconds: int = 10) -> dict:
    if not command or not command.strip():
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Command is empty",
            "exit_code": -1,
            "timed_out": False,
        }
    timeout = min(int(timeout_seconds) if timeout_seconds else MAX_TIMEOUT, MAX_TIMEOUT)
    try:
        result = subprocess.run(
            [SHELL, "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "exit_code": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "ok": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "timed_out": False,
        }


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Content-Type": "application/json",
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        return

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {}
        command = (data.get("command") or "").strip()
        timeout_seconds = data.get("timeout_seconds", MAX_TIMEOUT)
        out = run_command(command, timeout_seconds)
        body = json.dumps(out)
        self.send_response(200)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
        return
