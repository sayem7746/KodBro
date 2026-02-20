# Terminal backend

WebSocket (interactive PTY) + **HTTP API** for running terminal commands. The KodBro app can use the WebSocket for a live shell or call the API for one-off commands.

## Requirements

- Python 3.8+
- Unix-like OS (macOS, Linux, WSL) for PTY/WebSocket. The **HTTP API** works on any platform.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

## Run

**App creation** and **Build with Agent** require an AI backend. Choose one:

- **Gemini** (default): Set `GEMINI_API_KEY` (get one at https://aistudio.google.com/apikey)
- **Cursor API**: Set `CURSOR_API_KEY` and `CURSOR_GITHUB_TOKEN` (or `AGENT_GITHUB_TOKEN`). Get API key from Cursor Dashboard → Integrations. The GitHub token must have repo create/push access; your Cursor account must have access to those repos.

```bash
export GEMINI_API_KEY=your_key   # or use Cursor (see above)
python server.py
```

Or copy `.env.example` to `.env`, add your keys there, and load it (e.g. `set -a && source .env && set +a` before `python server.py`). Never commit `.env` or your real keys.

```bash
python server.py
# or: uvicorn server:app --host 0.0.0.0 --port 8765
```

Listens on `http://0.0.0.0:8765`.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| **POST /api/run** | Run a single command. Body: `{"command": "ls -la", "timeout_seconds": 30, "cwd": null}`. Returns `{ "ok", "stdout", "stderr", "exit_code", "timed_out" }`. |
| **GET /api/health** | Health check. |
| **WebSocket /ws** | Interactive PTY shell (connect from app for live terminal). |

### HTTP API example

```bash
# Run a command
curl -X POST http://localhost:8765/api/run \
  -H "Content-Type: application/json" \
  -d '{"command": "whoami"}'

# Response
{"ok":true,"stdout":"youruser\n","stderr":"","exit_code":0,"timed_out":false}
```

### App connection

- **WebSocket (interactive):** `ws://localhost:8765/ws` (or `ws://<host>:8765/ws` from device).
- **HTTP API:** from scripts or the app use `POST http://<host>:8765/api/run` with JSON body.

## Deploy backend to Vercel

From the **backend** directory:

1. Install Vercel CLI (if needed): `npm i -g vercel`
2. Log in: `vercel login`
3. Deploy:
   ```bash
   cd backend
   vercel
   ```
   Follow prompts (link existing project or create new). For production: `vercel --prod`.
4. Set environment variables in the [Vercel dashboard](https://vercel.com/dashboard) → your project → Settings → Environment Variables:
   - **GEMINI_API_KEY** (required for app creation): get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
5. Your API base URL will be `https://<your-project>.vercel.app`. Use that in the mobile app (e.g. home terminal URL or Create app API base).

**Endpoints on Vercel:**

| Endpoint | Description |
|----------|-------------|
| **GET /api/health** | Health check. |
| **POST /api/run** | Run a single command (timeout 10s on Hobby). |
| **POST /api/apps/create** | Create app from prompt (runs synchronously; 60s timeout on Pro, 10s on Hobby – may not finish on Hobby). |
| **GET /api/apps/status/[job_id]** | Returns 404 on Vercel (no job store); use when backend runs as long-lived server for async create + poll. |

**Note:** WebSocket (`/ws`) and async app creation with job polling do not run on Vercel; use a long-running server (e.g. Railway, Render) for those.

**Usage after deploy:**
```bash
curl https://<your-project>.vercel.app/api/health
curl -X POST https://<your-project>.vercel.app/api/run \
  -H "Content-Type: application/json" \
  -d '{"command": "echo hello"}'
```

- Timeout: 10s on Hobby, 60s on Pro (for `/api/apps/create`).
- For production, add authentication (e.g. API key in header) in the API handlers.

## Deploy to Railway

Railway supports long-running servers, so you get the full API, WebSocket terminal, app creation with job polling, and the **Build with Agent** feature.

1. Create a [Railway](https://railway.app) account and install the CLI: `npm i -g @railway/cli`
2. Log in: `railway login`
3. From the **backend** directory:
   ```bash
   cd backend
   railway init   # create new project or link existing
   railway up --service KodBro_api   # deploy (or just railway up if service is linked)
   ```
4. In the Railway dashboard → your service → **Settings** → **Networking** → **Generate Domain** to get a public URL.
5. Set **Root Directory** to `backend` if deploying from the monorepo root (or run `railway up` from inside `backend`).
6. Add environment variables in **Variables**:
   - `GEMINI_API_KEY` (for Create app and Build with Agent when not using Cursor)
   - Or `CURSOR_API_KEY` + `CURSOR_GITHUB_TOKEN` (to use Cursor Cloud API instead of Gemini)

Your API URL will be `https://<your-service>.railway.app`. Use it in the app for the terminal, Create app, and Build with Agent.

## Deploy elsewhere (full server + WebSocket)

Run `python server.py` behind a reverse proxy (nginx, Caddy) with TLS for the full API and interactive WebSocket terminal.
