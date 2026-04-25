# EngineLab API

FastAPI server that exposes the Python tournament backend as an HTTP API
with Server-Sent Events (SSE) for tournament progress streaming.

## Setup

```bash
pip install fastapi uvicorn sse-starlette
```

## Start

Run from the project root:

```bash
uvicorn api.server:app --reload --port 8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/features` | List all features |
| GET | `/api/variants` | List supported variants |
| POST | `/api/tournament` | Run tournament (SSE stream) |
