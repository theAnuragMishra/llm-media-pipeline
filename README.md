# Distributed Course Video Generation Pipeline 🎥⚡

An end-to-end asynchronous media processing microservice in Python that turns topics (like **"Photosynthesis"**) into studio-grade 1080p educational videos using an orchestrated pipeline:
1. **LLM Storyboarding & Scripting** (Structured JSON output / tool-calling)
2. **Neural Text-to-Speech (TTS)** (Edge-TTS high-fidelity neural speech / OpenAI TTS)
3. **High-Resolution Slide Rendering** (Pillow 1920x1080 dynamic cards & typography)
4. **Subtitles & Caption Generation** (SRT millisecond timeline alignment)
5. **FFmpeg Video Composition** (H.264/AAC encoding, faststart web optimization)
6. **Real-time Event Streaming** (Server-Sent Events [SSE] & WebSockets)
7. **Distributed Queue & Worker Topology** (RabbitMQ with DLQ, prefetch=1, & Redis PubSub)

---

## Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │              Client / Web UI                  │
                      └───────┬───────────────────────────────▲───────┘
                              │ POST /generate-course-video   │ SSE / WebSocket
                              ▼                               │
                      ┌───────────────────────┐               │
                      │   FastAPI Web API     │               │
                      └───────┬───────────────┘               │
                              │ Publish Task                  │
                              ▼                               │
                      ┌───────────────────────┐               │
                      │  RabbitMQ Exchange    │               │
                      │ (Topic + DLQ Topology)│               │
                      └───────┬───────────────┘               │
                              │ Prefetch Count = 1            │
                              ▼                               │
                      ┌───────────────────────┐               │
                      │ Async Worker Consumer │               │
                      └───────┬───────────────┘               │
                              │ Pipeline Execution            │
            ┌─────────────────┴─────────────────┐             │
            ▼                                   ▼             │
   ┌──────────────────┐               ┌───────────────────┐   │
   │  Pipeline Stages │               │   Pub/Sub Events  ├───┘
   │  1. LLM Script   │               │   (Redis / Bus)   │
   │  2. Neural TTS   │               └───────────────────┘
   │  3. 1080p Slides │
   │  4. FFmpeg Encode│
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ Storage (Local/S3│
   │ /course_video.mp4│
   └──────────────────┘
```

---

## Quickstart (Using `uv`)

This project is configured out-of-the-box to use Astral's [`uv`](https://docs.astral.sh/uv/) for high-speed dependency management and execution.

### 1. Install Dependencies
```bash
# Install dependencies specified in pyproject.toml
uv pip install -e .
```
*(Or if you use a virtual environment: `uv venv && source .venv/bin/activate && uv pip install -e .`)*

### 2. Standalone Local Run (Zero External Services Needed)
By default, `.env` is set to `BROKER_TYPE=memory`. You don't need Docker, RabbitMQ, or Redis running to immediately test!

```bash
uv run uvicorn app.main:app --reload --port 8000
```
Open your browser at:
👉 **`http://localhost:8000`**

- Type any topic (e.g. `Photosynthesis`, `Distributed Consensus`)
- Click **Dispatch Pipeline**
- Watch the live SSE/WebSocket telemetry terminal and the video player load the finalized 1080p MP4!

---

## Production Distributed Run (Docker & RabbitMQ)

To run the complete distributed cluster with decoupled API, RabbitMQ, Redis, and Worker containers:

```bash
# 1. Start RabbitMQ, Redis, API, and Worker via Docker Compose
docker compose up --build
```

- **API & Studio UI:** `http://localhost:8000`
- **Interactive OpenAPI Docs:** `http://localhost:8000/docs`
- **RabbitMQ Management Dashboard:** `http://localhost:15672` (Username: `guest`, Password: `guest`)

---

## API Specification

### 1. Enqueue Video Generation
`POST /api/v1/generate-course-video`

**Request Body:**
```json
{
  "topic": "Photosynthesis",
  "target_scenes": 3,
  "voice": "en-US-ChristopherNeural",
  "resolution": "1080p",
  "style": "Dark Modern"
}
```

**Response (`202 Accepted`):**
```json
{
  "task_id": "task_48f8a129efb7",
  "topic": "Photosynthesis",
  "status": "ACCEPTED",
  "stage": "QUEUED",
  "sse_url": "/api/v1/tasks/task_48f8a129efb7/events",
  "ws_url": "/ws/tasks/task_48f8a129efb7",
  "poll_url": "/api/v1/tasks/task_48f8a129efb7",
  "created_at": "2026-10-23T12:00:00Z"
}
```

---

### 2. Stream Live Progress (SSE)
`GET /api/v1/tasks/{task_id}/events`

Emits continuous Server-Sent Events with progress milestones:
```
event: progress
data: {"task_id":"task_48f8a129efb7","stage":"AUDIO_SYNTHESIS","progress_percent":45,"message":"Synthesized scene 2/3 narration (5.2s)","video_url":null,"error":null}

event: progress
data: {"task_id":"task_48f8a129efb7","stage":"COMPLETED","progress_percent":100,"message":"Course video generation completed successfully!","video_url":"/storage/task_48f8a129efb7/course_video.mp4","thumbnail_url":"/storage/task_48f8a129efb7/poster.jpg"}
```

---

### 3. Stream Live Progress (WebSocket)
`WS /ws/tasks/{task_id}`

Connect via any WebSocket client to receive streaming JSON frames and send keep-alive pings.

---

### 4. Poll Task Snapshot
`GET /api/v1/tasks/{task_id}`

Returns current task status and metadata snapshot.

---

## Running Automated Tests

Run the test suite using `uv`:
```bash
uv run pytest -v
```
