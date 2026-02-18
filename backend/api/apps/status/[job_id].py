"""
Vercel serverless: GET /api/apps/status/[job_id]
On serverless there is no job store; returns 404. Use a long-running server for async create + poll.
"""
import json
from http.server import BaseHTTPRequestHandler


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
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

    def do_GET(self):
        body = json.dumps(
            {"error": "Job not found", "message": "Status polling is not available on serverless; app creation runs synchronously."}
        )
        self.send_response(404)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
        return
