# KodBro backend - FastAPI + WebSocket terminal + Agent API
FROM python:3.12-slim

WORKDIR /app

# Install git (required for Cursor agent: create repo, push, pull)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy backend files
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Railway sets PORT at runtime
ENV PORT=8765
EXPOSE 8765

CMD ["/bin/sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8765}"]
