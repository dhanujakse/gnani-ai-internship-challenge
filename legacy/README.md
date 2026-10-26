# BhashaBridge AI

**Speak Tamil. They hear Hindi. Right inside WhatsApp.**

Forward a voice note in Hindi, hear it in Tamil; record your Tamil reply, get a Hindi voice note to send back.
Built on Gnani Prisma (speech-to-text), Evon v3.3 (translation) and Gnani Timbre (text-to-speech).

> Work in progress for the Gnani.ai Great Indian AI Internship Challenge.

## Run locally

```bash
cp .env.example .env          # fill in keys
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -q
```

ffmpeg must be on your PATH (the Docker image includes it).

## Layout

- `backend/` FastAPI service: WhatsApp webhook, web API, STT -> translate -> TTS pipeline
- `web/` share-target web app (Vite + React + TS)
- `eval/` evaluation cases, recordings and results
- `infra/` Evon vLLM launch script, optional Caddy config

## Status

Architecture, evaluation table (with n), privacy notes and team sections will be filled in as the build progresses.
