# Deploy KodBro Backend to Railway

This guide covers deploying the KodBro backend (FastAPI + WebSocket + Agent API) to Railway.

## Prerequisites

- GitHub account with this repo
- [Railway](https://railway.app) account
- API keys for the backend (set as env vars in Railway)

## Quick Deploy

### 1. Connect to Railway

1. Go to [railway.app](https://railway.app) and sign in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select the `KodBro-app` repository
4. Railway will detect the `Dockerfile` and `railway.json` and start building

### 2. Configure Environment Variables

In your Railway service → **Variables**, add:

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key (for agent) | Yes (or use Cursor) |
| `CURSOR_API_KEY` | Cursor API key (optional, for Cursor agent) | No |
| `CURSOR_GITHUB_TOKEN` | GitHub token for Cursor agent | No |
| `PORT` | Set by Railway automatically | No |

### 3. Generate Domain

1. Go to your service → **Settings** → **Networking**
2. Click **Generate Domain**
3. Copy the URL (e.g. `https://your-app.up.railway.app`)

### 4. Update Frontend API Base

In the Ionic app, set the agent API base to your Railway URL. The default is `https://agent.kodbro.com`. Update `src/app/services/agent.service.ts` or configure the app to use your Railway domain.

## Alternative: Deploy Backend Only (Nixpacks)

If you prefer not to use Docker:

1. In Railway project settings, set **Root Directory** to `backend`
2. Railway will use `backend/railway.json` and Nixpacks to build
3. Ensure `backend/requirements.txt` is present

## Endpoints

Once deployed:

- `GET /api/health` – Health check
- `POST /api/run` – Run a command
- `WebSocket /ws` – Interactive terminal
- `POST /api/agent/sessions` – Create agent session
- `GET /api/agent/sessions/{id}/stream` – SSE log stream
- `POST /api/apps/create` – Create app pipeline

## Troubleshooting

- **Build fails**: Ensure `backend/requirements.txt` and all Python files are committed
- **App crashes**: Check Railway logs; verify `GEMINI_API_KEY` (or `CURSOR_API_KEY`) is set
- **CORS errors**: The backend allows all origins (`allow_origins=["*"]`); if issues persist, add your frontend origin explicitly
