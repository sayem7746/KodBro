"""
Generate app source code from user prompt using Gemini.
Output: list of {path, content} written to a temporary directory.
"""
import json
import os
import re
import tempfile
from typing import Optional

GEMINI_MODEL = os.environ.get("GEMINI_APP_MODEL", "gemini-2.0-flash")


def _extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON from model response, optionally inside markdown code block."""
    text = text.strip()
    # Try raw JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try ```json ... ``` or ``` ... ```
    for pattern in (r"```(?:json)?\s*\n([\s\S]*?)\n```", r"```\s*\n([\s\S]*?)\n```"):
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                continue
    return None


def generate_app(
    app_name: str,
    description: str,
    prompt: str,
    api_key: Optional[str] = None,
) -> str:
    """
    Call Gemini to generate app files, write to a temp dir, return the directory path.
    Raises on missing API key or parse failure.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set and no api_key provided")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    system_instruction = """You are an expert web app generator. Given an app name, short description, and a user prompt, you must output a complete, runnable web application.

Output ONLY a single JSON object with this exact structure (no other text before or after):
{"files": [{"path": "relative/file/path", "content": "full file content as string"}]}

Rules:
- Generate a modern React or Next.js app (prefer Next.js for simple deployment).
- Include all required files: package.json, main entry, components, styles if needed.
- path must be relative (e.g. "package.json", "src/app/page.tsx", "README.md").
- Escape JSON correctly in content (newlines as \\n, quotes escaped).
- Keep the app minimal but complete so it runs with npm install && npm run build.
- App name and description should appear in the app (e.g. title, README)."""

    user_content = f"""App name: {app_name}
Description: {description}

User request: {prompt}

Generate the full app as JSON with "files" array of {{"path", "content"}}."""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    if not response or not response.text:
        raise ValueError("Empty response from Gemini")

    data = _extract_json_from_response(response.text)
    if not data or "files" not in data or not isinstance(data["files"], list):
        raise ValueError("Gemini response missing 'files' array")

    tmpdir = tempfile.mkdtemp(prefix="kodbro_app_")
    for item in data["files"]:
        if not isinstance(item, dict) or "path" not in item or "content" not in item:
            continue
        path = item["path"]
        content = item["content"]
        if ".." in path or path.startswith("/"):
            continue
        full_path = os.path.join(tmpdir, path)
        d = os.path.dirname(full_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return tmpdir
