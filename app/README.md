# Face_swap

Face_swap is a full-stack AI face swap web app for creating faceless content, AI model visuals, reels, and image experiments. It combines a simple Next.js frontend with a FastAPI backend, Redis queueing, a Python worker, InsightFace face swapping, and optional GFPGAN face enhancement.

## What this project does

A user uploads:
- a source face image
- a target image

The system then:
- saves both files locally
- creates a job ID
- pushes the job into Redis
- lets a background worker process the face swap asynchronously
- stores the final image locally
- returns the job status and output URL back to the frontend

This makes the app more stable than running the entire AI pipeline inside a single web request.

## Why this setup

### Next.js frontend
We use Next.js because it gives a quick UI for uploads, polling, and result display without adding unnecessary complexity.

### FastAPI backend
We use FastAPI because it is lightweight, fast, and works very well for file upload APIs and async job endpoints.

### Redis queue
We use Redis so uploads and AI processing are decoupled. Face swap jobs can take time, and Redis gives a clean way to queue work instead of blocking the API.

### Background worker
We use a separate Python worker so the expensive AI processing happens outside the API process. That keeps the backend responsive.

### InsightFace + inswapper_128.onnx
We use InsightFace because it is one of the most practical local face swap pipelines for identity transfer.

### GFPGAN enhancement
We use GFPGAN as an optional post-processing step because raw `inswapper_128` outputs can look soft or blurry. GFPGAN helps restore facial detail after the swap.

### Python 3.11
We use Python 3.11 because GFPGAN and its dependency chain are much more reliable there than on Python 3.13 in this setup.

### Local filesystem storage
We store uploads and outputs locally in `backend/uploads` and `backend/outputs` because this project is built for local use and simple deployment.

## Architecture

```text
Frontend (Next.js)
    -> POST upload request
FastAPI backend
    -> save files locally
    -> create job
    -> push job to Redis
Worker
    -> pull job from Redis
    -> run InsightFace swap
    -> optionally run GFPGAN enhancement
    -> save output locally
Frontend
    -> poll job status
    -> display final image
```

## Current working setup

This is the setup that currently works best for this repo:

- Frontend: Next.js
- Backend: FastAPI
- Queue: Redis in Docker
- Worker: Python background worker
- Python env for backend and worker: `backend\.venv311`
- AI swap model: `inswapper_128.onnx`
- Optional enhancer: GFPGAN
- Start script: `start-all.ps1`
- Stop script: `stop-all.ps1`

## Project structure

```text
ai-face-swap/
  backend/
    app/
      main.py
      config.py
      routes/
        job.py
      services/
        enhancement_service.py
        face_service.py
        job_store.py
        queue_service.py
        storage_service.py
    worker/
      processor.py
      worker.py
    uploads/
    outputs/
    models/
    requirements.txt
    Dockerfile
  frontend/
    pages/
      index.js
    package.json
    Dockerfile
  logs/
  start-all.ps1
  stop-all.ps1
  docker-compose.yml
  README.md
```

## Features

- Upload source face image and target image
- Async job creation and polling
- Redis queue-based processing
- Background worker execution
- Static output file serving from FastAPI
- Prompt field for comparison notes
- Optional GFPGAN enhancement toggle
- Local storage for uploads and outputs
- Error handling for missing faces, bad input, and model issues

## Requirements

Before installing, make sure you have:

- Python 3.11
- Node.js
- Docker Desktop running
- Git
- Internet access for first-time model downloads

## Important folders

- Uploads are stored in [uploads](D:\vscode repos\AI swaping tool\ai-face-swap\backend\uploads)
- Generated results are stored in [outputs](D:\vscode repos\AI swaping tool\ai-face-swap\backend\outputs)
- Models are stored in [models](D:\vscode repos\AI swaping tool\ai-face-swap\backend\models)
- Logs are stored in [logs](D:\vscode repos\AI swaping tool\ai-face-swap\logs)

## API routes

### `POST /api/create-job`
Creates a new face swap job from uploaded files.

Form fields:
- `source_image`
- `target_image`
- `prompt`
- `enhance_face`
- `response_base_url`

### `GET /api/job/{job_id}`
Returns:
- job status
- output path
- output URL
- error details if the job failed

## Notes about quality

- `inswapper_128.onnx` is good for identity replacement, but it can still look soft on bad inputs.
- Best results come from sharp, front-facing, high-resolution faces.
- GFPGAN can improve facial detail, but it will not turn the app into a prompt-driven cinematic generator.
- The prompt field is currently stored with the job for comparison and workflow notes. It does not directly control the InsightFace swap result.

## Docker setup

If you want the whole project in containers, the repo is now structured for that flow:

- `redis` runs as a queue service
- `backend` runs FastAPI
- `worker` runs the background face swap processor
- `frontend` builds and serves the Next.js app

### 1. Make sure Docker Desktop is running

On Windows, start Docker Desktop first and wait until it shows as running.

### 2. Start the full stack

From the repo root:

```powershell
docker compose up --build
```

This builds:

- the backend image from `backend/Dockerfile`
- the worker image from the same backend image
- the frontend image from `frontend/Dockerfile`

It also starts Redis automatically.

The backend Docker image installs CPU-only PyTorch wheels so the container matches the current CPU-based ONNX runtime setup.

### 3. Open the app

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Stop the containers

```powershell
docker compose down
```

### 5. Rebuild after code changes

If you changed dependencies or Dockerfiles:

```powershell
docker compose up --build
```
docker compose up -d

docker compose up -d
docker compose logs -f
-d → run in background
logs -f → watch logs anytime

If you only changed source code and want a clean rebuild anyway, the same command is fine.

## Install

### 1. Clone the repo

```powershell
git clone https://github.com/harshrajurkar/Face_swap.git
cd Face_swap
```

### 2. Create the backend Python 3.11 environment

```powershell
cd backend
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd ..\frontend
npm.cmd install
```

## Setup

### 1. Start Redis

If the Redis container already exists:

```powershell
docker start ai-face-swap-redis
```

If it does not exist yet:

```powershell
docker run -d --name ai-face-swap-redis -p 6379:6379 redis:7-alpine
```

### 2. Make sure model folders exist

These are already included in the project layout, but the app will use:

- `backend/models/inswapper_128.onnx`
- `backend/models/GFPGANv1.3.pth`

Some models may download automatically on first run.

## Start

You can start the app in three ways.

### Option 1. Start everything with Docker Compose

From the repo root:

```powershell
docker compose up --build
```

This starts:
- Redis
- FastAPI backend
- worker
- frontend

### Option 2. Start everything with the PowerShell script

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

This starts:
- Redis container
- FastAPI backend
- worker
- frontend

### Option 3. Start each service manually

#### Backend

```powershell
cd backend
.\.venv311\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### Worker

Open another terminal:

```powershell
cd backend
.\.venv311\Scripts\python.exe -m worker.worker
```

#### Frontend

Open another terminal:

```powershell
cd frontend
npm.cmd run dev
```

## Stop

To stop everything started by the PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\stop-all.ps1
```

To stop all Docker containers started with `docker compose up`:

```powershell
docker compose down
```

## Use

### 1. Open the app

Go to:
- [http://localhost:3000](http://localhost:3000)

### 2. Upload images

Choose:
- source face image
- target image

### 3. Optional settings

- enter a comparison prompt
- enable or disable GFPGAN enhancement

### 4. Submit the job

The frontend will call the backend and create a queued job.

### 5. Wait for processing

The UI polls job status automatically:
- `queued`
- `processing`
- `completed`
- `failed`

### 6. View result

When complete, the output image is shown in the browser and also saved locally in:
- `backend/outputs`

## Useful URLs

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Logs

If something fails while using the background startup script, check:

- [backend.log](D:\vscode repos\AI swaping tool\ai-face-swap\logs\backend.log)
- [worker.log](D:\vscode repos\AI swaping tool\ai-face-swap\logs\worker.log)
- [frontend.log](D:\vscode repos\AI swaping tool\ai-face-swap\logs\frontend.log)

## GPU note

The current repo is set up for CPU using `onnxruntime`.

If you want GPU support later, you can switch to a CUDA-compatible ONNX Runtime build and update the execution provider.



powershell -ExecutionPolicy Bypass -File .\stop-all.ps1
powershell -ExecutionPolicy Bypass -File .\start-all.ps1