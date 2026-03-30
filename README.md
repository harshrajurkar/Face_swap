# Face_swap

i made this tool to make reels and pics to make and groww faceless or AI model instagram page

## AI Face Swap App

A full-stack async face swap application using Next.js on the frontend and FastAPI + Redis + a Python worker on the backend. Users upload a source face image and a target image, the backend stores them on disk, pushes a job into Redis, and the worker performs the face swap with InsightFace `inswapper_128.onnx`.

## Project Structure

```text
ai-face-swap/
  backend/
    app/
      main.py
      config.py
      routes/
        job.py
      services/
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
  docker-compose.yml
  README.md
```

## Features

- Upload source face and target image
- FastAPI endpoint to create jobs
- Redis-backed queue
- Background worker for face swap processing
- Redis job status store with polling
- Static output serving from FastAPI
- Local filesystem storage in `uploads/` and `outputs/`
- Optional GFPGAN face enhancement
- Graceful error handling for invalid files and missing faces

## Prerequisites

### Local run

- Python 3.11 recommended for GFPGAN support
- Node.js 20+
- Redis 7+
- Internet access on first run to download:
  - `inswapper_128.onnx`
  - InsightFace analysis models (`buffalo_l`)
  - `GFPGANv1.3.pth` if enhancement is enabled

### Docker run

- Docker
- Docker Compose

## Backend Setup

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap\backend"
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
.\.venv311\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Worker Setup

Open a second terminal in `backend` and run:

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap\backend"
.\.venv311\Scripts\python.exe -m worker.worker
```

## Redis Setup

If you prefer Docker for Redis:

```powershell
docker start ai-face-swap-redis
```

If the container does not exist yet:

```powershell
docker run -d --name ai-face-swap-redis -p 6379:6379 redis:7-alpine
```

## Frontend Setup

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap\frontend"
npm.cmd install
npm.cmd run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000).

## Full Docker Compose Run

From the repo root:

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap"
docker compose up --build
```

## API Endpoints

### `POST /api/create-job`

Accepts multipart form data:

- `source_image`: source face image file
- `target_image`: target image file
- `prompt`: stored comparison prompt text
- `enhance_face`: `true` or `false`
- `response_base_url`: optional base URL used to return an absolute output URL

### `GET /api/job/{job_id}`

Returns job state, errors, and output URL when ready.

## Browser Testing

1. Open [http://localhost:3000](http://localhost:3000).
2. Upload a source face image with a clear, front-facing face.
3. Upload a target image that also contains a face.
4. Keep enhancement enabled for sharper output.
5. Submit the form.
6. Wait for the polling status to move from `queued` to `processing` to `completed`.

## Static Output Serving

Completed images are served by FastAPI from:

- [http://127.0.0.1:8000/outputs](http://127.0.0.1:8000/outputs)

## CPU vs GPU Notes

### CPU

- The included `requirements.txt` uses `onnxruntime`, which runs on CPU.
- This is the easiest setup and works on most machines.
- Processing will be slower for large images.

### GPU

To use NVIDIA GPU acceleration:

1. Replace `onnxruntime` with `onnxruntime-gpu` in `backend/requirements.txt`.
2. Set `EXECUTION_PROVIDER=CUDAExecutionProvider`.
3. Make sure CUDA and cuDNN are installed and compatible with your ONNX Runtime build.

## Notes

- The worker loads the InsightFace models on startup, so the first run can take a bit longer.
- The backend stores job metadata in Redis with a 24 hour TTL.
- Output images are written as PNG files.
- The swap uses the largest detected face in the source and target images.
- GFPGAN support works best from the Python 3.11 environment at `backend\.venv311`.

## Background Scripts

Start everything in background:

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap"
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

Stop everything:

```powershell
cd "D:\vscode repos\AI swaping tool\ai-face-swap"
powershell -ExecutionPolicy Bypass -File .\stop-all.ps1
```
