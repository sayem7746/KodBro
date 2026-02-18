"""
Vercel serverless: POST /api/apps/create
Runs the app-creation pipeline synchronously. May hit timeout on hobby (10s); use Pro for 60s.
Returns 200 with repo_url, deploy_url or 500 with error.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Ensure backend root is on path so we can import services, run_pipeline_sync
_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)


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
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {}

        if not payload.get("app_name") or not payload.get("prompt"):
            body = json.dumps({"error": "app_name and prompt are required"})
            self.send_response(400)
            for k, v in cors_headers().items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        if not payload.get("git") or not payload["git"].get("token"):
            body = json.dumps({"error": "git.token is required"})
            self.send_response(400)
            for k, v in cors_headers().items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        if not payload.get("vercel") or not payload["vercel"].get("token"):
            body = json.dumps({"error": "vercel.token is required"})
            self.send_response(400)
            for k, v in cors_headers().items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        try:
            from run_pipeline_sync import run_pipeline_sync

            repo_url, deploy_url = run_pipeline_sync(payload)
            out = {
                "repo_url": repo_url,
                "deploy_url": deploy_url,
                "message": "App created and deployed" if deploy_url else "App and repo created; Vercel setup failed or skipped.",
            }
            body = json.dumps(out)
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"error": str(e), "message": "Creation failed"})
            self.send_response(500)

        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
        return
