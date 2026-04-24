# 📚 AI Face Swap - Complete Documentation

**Project Last Updated:** April 19, 2026  
**Version:** 1.0  
**Status:** Production Ready ✅

---

## 📖 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Design](#architecture--design)
3. [Installation & Setup](#installation--setup)
4. [Quick Start Guide](#quick-start-guide)
5. [Real-Time Progress UI](#real-time-progress-ui)
6. [Complete Change Log](#complete-change-log)
7. [Troubleshooting](#troubleshooting)
8. [API Reference](#api-reference)
9. [Development Guide](#development-guide)
10. [Performance Tips](#performance-tips)

---

## 🎯 Project Overview

**AI Face Swap** is a full-stack web application for creating professional face swap content with an intuitive UI and real-time progress tracking.

### What It Does
Users upload:
- **Source face image** - The face to copy
- **Target image** - The image to receive the new face

The system:
1. Saves files locally
2. Creates a unique job ID
3. Queues the job in Redis
4. Processes asynchronously using InsightFace
5. Optionally enhances with GFPGAN
6. Returns results via REST API

### Why This Architecture

| Component | Reason |
|-----------|--------|
| **Next.js Frontend** | Fast, responsive UI with no extra complexity |
| **FastAPI Backend** | Lightweight, async-friendly, perfect for file uploads |
| **Redis Queue** | Decouples uploads from processing; scales better |
| **Python Worker** | Expensive AI operations happen separately; keeps API responsive |
| **InsightFace** | Best local face swap pipeline for identity transfer |
| **GFPGAN** | Post-processing enhancement for detail restoration |
| **Python 3.11** | GFPGAN dependency chain most reliable here |
| **Local Storage** | Simple, built for local/private deployment |

---

## 🏗️ Architecture & Design

### System Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Next.js)                                          │
│  - Upload interface                                         │
│  - Real-time progress tracking (1.2s polling)              │
│  - Result comparison slider                                │
│  - Modern animated UI                                       │
└──────────────┬──────────────────────────────────────────────┘
               │ POST /api/create-job
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                           │
│  - Save uploaded files                                      │
│  - Create job in Redis                                      │
│  - Push job to queue                                        │
│  - Health check endpoint                                    │
│  - Job status polling endpoint                              │
└──────────────┬──────────────────────────────────────────────┘
               │ Job stored in Redis
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Redis (Message Queue)                                       │
│  - Job state storage                                        │
│  - Queue management                                         │
│  - Progress tracking                                        │
└──────────────┬──────────────────────────────────────────────┘
               │ Job dequeued
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Worker (Python Background Process)                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 1: Load Models (5-10%)                        │   │
│  │  - InsightFace detection models                     │   │
│  │  - Face swap model (inswapper_128.onnx)            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 2: Detect Faces (15-25%)                      │   │
│  │  - Find faces in both source and target            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 3: Extract Faces (25-35%)                     │   │
│  │  - Crop face regions from both images              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 4: Swap (40-55%)                              │   │
│  │  - Run InsightFace swap inference                  │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 5: Blend (60-75%)                             │   │
│  │  - Seamless blending into target image             │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 6: Enhance (78-88%)  [OPTIONAL]              │   │
│  │  - Run GFPGAN for detail enhancement               │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Stage 7: Save (95-100%)                             │   │
│  │  - Write final output to disk                       │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────────────┘
               │ Update job status in Redis
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Frontend Polling                                            │
│  - Fetches job status every 1.2 seconds                    │
│  - Updates progress bar                                     │
│  - Shows current stage with description                     │
│  - Displays results when complete                           │
└──────────────────────────────────────────────────────────────┘
```

### Progress Tracking Pipeline

The system tracks progress through 7 distinct stages:

```
model_loading (5-10%)    ⚙️  Indigo    - Loading AI models
        │
        ▼
face_detection (15-25%)  👁️  Amber     - Detecting faces in images
        │
        ▼
face_extraction (25-35%) ✂️  Pink      - Extracting face regions
        │
        ▼
face_swapping (40-55%)   🔄  Purple    - Performing the swap
        │
        ▼
blending (60-75%)        🎨  Emerald   - Blending into target
        │
        ▼
enhancement (78-88%)     ✨  Rose      - Optional GFPGAN enhancement
        │
        ▼
saving (95-100%)         💾  Blue      - Saving final output
        │
        ▼
completed (100%)         ✓   Emerald   - Done!
```

### File Structure

```
ai-face-swap/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── config.py               # Settings & environment variables
│   │   ├── routes/
│   │   │   └── job.py              # Job creation & status endpoints
│   │   └── services/
│   │       ├── enhancement_service.py  # GFPGAN enhancement logic
│   │       ├── face_service.py         # InsightFace swap logic
│   │       ├── job_store.py            # Redis job storage
│   │       ├── queue_service.py        # Redis queue management
│   │       ├── face_region.py          # Face region processing
│   │       └── storage_service.py      # File upload/output handling
│   ├── worker/
│   │   ├── processor.py            # Main job processing pipeline
│   │   └── worker.py               # Worker main loop
│   ├── uploads/                    # User uploads (gitignored)
│   ├── outputs/                    # Final results (gitignored)
│   ├── models/                     # AI model weights (gitignored)
│   ├── Dockerfile                  # Backend container image
│   └── requirements.txt            # Python dependencies
├── frontend/
│   ├── pages/
│   │   ├── _app.js                 # Next.js app wrapper
│   │   └── index.js                # Main upload & result page
│   ├── components/
│   │   └── ProgressComponent.js    # Real-time progress display
│   ├── styles/
│   │   ├── globals.css             # Global styles
│   │   ├── Home.module.css         # Home page styles
│   │   └── Progress.module.css     # Progress component styles
│   ├── public/                     # Static assets
│   ├── Dockerfile                  # Frontend container image
│   ├── next.config.js              # Next.js configuration
│   └── package.json                # Node dependencies
├── docker-compose.yml              # Full stack container orchestration
├── README.md                        # Project overview (this doc)
├── ARCHITECTURE.md                 # Technical architecture
├── QUICK_REFERENCE.md              # Quick start commands
├── REFACTORING_GUIDE.md            # Code organization guide
└── [Other documentation files]
```

---

## 🚀 Installation & Setup

### Prerequisites

- **Docker & Docker Compose** (v2.0+)
- **Windows with WSL2** (optional, but recommended for development)
- **Git**
- **4GB+ RAM** (8GB+ recommended)
- **2GB free disk space** (for models)

### Clone & Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-face-swap.git
cd ai-face-swap

# Start all containers
docker-compose up --build

# Access the app
Frontend:  http://localhost:3000
Backend:   http://localhost:8000
```

### First Run

1. Open http://localhost:3000
2. Upload a source portrait (clear front-facing image)
3. Upload a target image
4. Optionally enable "Detail Enhancement"
5. Click "Start Face Swap"
6. Watch real-time progress (1.2 second updates)
7. View results in comparison slider
8. Download the final image

### Environment Variables

```bash
# Backend (.env or docker-compose.yml)
REDIS_URL=redis://redis:6379/0
EXECUTION_PROVIDER=CPUExecutionProvider  # or CUDAExecutionProvider
WORKER_CONCURRENCY=1
WORKER_JOB_TIMEOUT_SECONDS=900
WORKER_MAX_RETRIES=2

# Frontend (.env.local)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_BACKEND_ORIGIN=http://localhost:8000
```

---

## ⚡ Quick Start Guide

### Start Everything

```bash
# Using provided script (Windows PowerShell)
./start-all.ps1

# Or manually
docker-compose down
docker-compose up --build
```

### Stop Everything

```bash
# Using provided script (Windows PowerShell)
./stop-all.ps1

# Or manually
docker-compose down
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker
```

### Common Commands

```bash
# Rebuild containers (after code changes)
docker-compose down
docker-compose up --build

# Force rebuild frontend only
docker-compose up --build frontend

# Clean everything (containers, volumes, etc)
docker-compose down -v

# Check service health
docker-compose ps
```

---

## 🎨 Real-Time Progress UI

### Features

✅ **7-Stage Progress Pipeline**
- Each stage has unique icon, color, and status message
- Smooth animated progress bar with shimmer effect
- Step indicator showing completion status

✅ **Real-Time Updates**
- Frontend polls backend every 1.2 seconds
- Backend updates progress in Redis
- Worker logs all stage transitions

✅ **Modern Animations**
- Progress bar: 0.6s smooth transition
- Spinner: 0.8s continuous rotation
- Checkmark: 0.4s scale-in animation
- Error shake: 0.5s animation

✅ **Mobile Responsive**
- Desktop (1024px+): Full-size components
- Tablet (768px-1023px): Optimized layout
- Mobile (480px-767px): Touch-friendly
- Extra small (<480px): Minimal design

### Stage Configuration

| Stage | Progress | Icon | Color | Duration |
|-------|----------|------|-------|----------|
| model_loading | 5-10% | ⚙️ | #6366f1 (Indigo) | 2-3s |
| face_detection | 15-25% | 👁️ | #f59e0b (Amber) | 3-5s |
| face_extraction | 25-35% | ✂️ | #ec4899 (Pink) | 2s |
| face_swapping | 40-55% | 🔄 | #8b5cf6 (Purple) | 5-10s |
| blending | 60-75% | 🎨 | #10b981 (Emerald) | 3-5s |
| enhancement | 78-88% | ✨ | #f43f5e (Rose) | 5s |
| saving | 95-99% | 💾 | #3b82f6 (Blue) | 1s |
| completed | 100% | ✓ | #10b981 (Emerald) | - |

### Customization

**Change polling interval** (frontend/pages/index.js):
```javascript
const pollJob = async () => { ... };
window.setInterval(pollJob, 1200);  // Change 1200 to your preferred milliseconds
```

**Modify stage colors** (frontend/components/ProgressComponent.js):
```javascript
const STAGE_CONFIG = {
  model_loading: {
    label: 'Loading Models',
    icon: '⚙️',
    color: '#6366f1',  // Change hex color
  },
  // ... other stages
};
```

**Adjust progress ranges** (backend/worker/processor.py):
```python
await self.job_store.update_job(
    job_id,
    stage="model_loading",
    progress=10,  # Change progress percentage
    status_message="Models loaded successfully...",
)
```

---

## 📝 Complete Change Log

### Session 1: Bug Fixes & Core Enhancements

#### 🔧 Fixed Issues

**1. Worker Container ImportError (CRITICAL)**
- **Problem:** `from turtle import width` in face_region.py was importing unneeded tkinter dependency
- **Solution:** Removed incorrect import line
- **File:** `backend/app/services/face_region.py:4`
- **Result:** Worker container no longer crashes on startup ✅

**2. Async Coroutine Bug (CRITICAL)**
- **Problem:** `_run_face_swap()` was async but called via `asyncio.to_thread()`, returning coroutine object instead of file path
- **Impact:** OpenCV `cv2.imread()` received coroutine instead of string, causing enhancement to fail
- **Solution:** Changed `_run_face_swap()` from `async def` to regular `def`
- **File:** `backend/worker/processor.py:195-205`
- **Result:** Enhancement now works correctly ✅

#### 📊 Added Debug Logging

Implemented comprehensive debug logging across 6 backend files:

**File: `backend/worker/processor.py`**
- Job processing pipeline stages
- Progress updates with percentages
- Exception details with tracebacks
- Pre-fix: Static 18%, 35%, 75% progress

**File: `backend/app/services/face_service.py`**
- Face detection logging
- Face extraction details
- Swap operation progress
- Image dimensions tracking

**File: `backend/app/services/enhancement_service.py`**
- Model loading/caching
- GFPGAN initialization
- Enhancement pipeline steps
- Output file writing

**File: `backend/app/routes/job.py`**
- Job creation endpoint calls
- File upload tracking
- Response generation

**File: `backend/worker/worker.py`**
- Worker startup messages
- Job dequeue logging
- Processing status updates

**File: `backend/app/services/storage_service.py`**
- File upload progress
- Path generation tracking

#### 🎨 Built Real-Time Progress UI

**New File: `frontend/components/ProgressComponent.js`**
- 7-stage progress visualization
- Real-time status updates
- Stage-specific icons and colors
- Error handling with visual feedback
- Step indicator for progress tracking
- Responsive to all screen sizes

**New File: `frontend/styles/Progress.module.css`**
- 400+ lines of advanced CSS
- 7+ animations (shimmer, spin, bounce, shake, scaleIn, slideIn)
- Color gradients and shadows
- Responsive breakpoints (768px, 480px)
- Smooth transitions and keyframes
- Mobile-optimized styling

**Updated: `frontend/pages/index.js`**
- Integrated ProgressComponent
- Updated polling interval: 2500ms → 1200ms (2x faster)
- Added progress state variables (serverProgress, serverStage, serverStatusMessage)
- Conditional rendering for progress display

#### 🔄 Refactored Job Processing Pipeline

**File: `backend/worker/processor.py`**
- Moved from fixed progress values to 7-stage dynamic pipeline
- Real-time progress tracking with meaningful milestones
- Integrated GFPGAN enhancement with progress updates
- Proper async/sync handling for thread pool execution
- Complete error handling with detailed logging

### Session 2: UI Layout Fixes

#### 🖼️ Fixed Image Display Issues

**Problem:** Result review image was showing only middle portion due to `object-fit: cover` cropping

**Solution:** Changed to `object-fit: contain` with proper sizing constraints

**File: `frontend/styles/Home.module.css`**
- `.compareFrame`: Added `max-height: 520px` (desktop), `380px` (mobile)
- `.compareBase`: Changed to block element with proper sizing
- `.compareOverlay`: Absolute positioning with explicit top/left coordinates
- Result: Full image visible with working comparison slider ✅

### Session 3: UI Improvements & Error Handling

#### 🚫 Removed Error Details from UI

**Problem:** Technical error messages (OpenCV errors, tracebacks) displayed to users

**Solution:** Hide error details in UI, show only "An error occurred" message

**File: `frontend/components/ProgressComponent.js`**
- Removed `{error && <p className={styles.errorMessage}>{error}</p>}`
- Backend logs still show full error details for debugging
- User sees clean error status only ✅

---

## 🐛 Troubleshooting

### Container Issues

**Problem: "Port already in use"**
```bash
# Find and kill process using port
# For port 3000 (frontend)
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process

# For port 8000 (backend)
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

**Problem: "Docker daemon not running"**
```bash
# Start Docker Desktop (Windows)
# Or restart Docker service (Linux)
```

**Problem: "Insufficient memory"**
```bash
# Increase Docker memory limit
# Docker Desktop Settings → Resources → Memory: 8GB+
```

### Processing Issues

**Problem: "No face detected"**
- Upload a front-facing, clear portrait (1080p+ recommended)
- Ensure good lighting and even exposure
- Avoid extreme angles or partial faces

**Problem: "Enhancement takes too long"**
- GFPGAN can be slow on CPU (~5 seconds)
- Disable enhancement in UI for faster results
- Consider GPU acceleration if available

**Problem: "Worker not processing jobs"**
```bash
# Check worker logs
docker-compose logs -f worker

# Verify Redis is running
docker-compose logs -f redis

# Restart worker
docker-compose restart worker
```

### Frontend Issues

**Problem: "Progress not updating"**
- Check browser DevTools (F12) for network errors
- Verify backend is running: curl http://localhost:8000/health
- Clear browser cache: Ctrl+Shift+Delete

**Problem: "Images not displaying"**
- Check CORS settings in `backend/app/main.py`
- Verify uploads/outputs paths are accessible
- Check file permissions

---

## 📡 API Reference

### Create Job
```
POST /api/create-job
Content-Type: multipart/form-data

Parameters:
  source_image (file)    - Portrait image (required)
  target_image (file)    - Target image (required)
  enhance_face (boolean) - Enable GFPGAN (default: false)
  prompt (string)        - Session note/description (optional)
  response_base_url      - Backend URL for response (required)

Response (202 Accepted):
{
  "job_id": "248c8b9a-267e-46bf-a9ee-e0a60db04d0e",
  "status": "queued",
  "progress": 5,
  "stage": "model_loading",
  "status_message": "Loading AI models...",
  "enhance_face": true,
  "prompt": "Client preview for review"
}
```

### Get Job Status
```
GET /api/job/{job_id}

Response (200 OK):
{
  "job_id": "248c8b9a-267e-46bf-a9ee-e0a60db04d0e",
  "status": "processing",
  "progress": 45,
  "stage": "face_swapping",
  "status_message": "Swapping faces using InsightFace...",
  "output_url": null,
  "error": null,
  "created_at": "2026-04-19T00:00:00Z",
  "updated_at": "2026-04-19T00:02:30Z"
}
```

### Health Check
```
GET /health

Response (200 OK):
{
  "status": "ok"
}
```

---

## 🔧 Development Guide

### Code Organization

**Backend Architecture**
```
services/
  ├── job_store.py         - Redis persistence layer
  ├── queue_service.py     - Redis queue operations
  ├── storage_service.py   - File handling
  ├── face_service.py      - Core swap logic
  ├── enhancement_service.py - GFPGAN integration
  └── face_region.py       - Region-based processing

worker/
  ├── processor.py         - Main pipeline orchestrator
  └── worker.py            - Job dequeue loop
```

**Frontend Architecture**
```
pages/
  └── index.js            - Main upload & results page
    ├── State management
    ├── Form handling
    ├── Job polling
    └── Results display

components/
  └── ProgressComponent.js - Real-time progress UI
    ├── Stage visualization
    ├── Animation handling
    └── Responsive layout

styles/
  ├── Home.module.css      - Layout & results styles
  ├── Progress.module.css  - Progress animations
  └── globals.css          - Global styling
```

### Key Files & Their Purposes

| File | Purpose | Key Functions |
|------|---------|---|
| `processor.py` | Job orchestration | `process()`, `_run_face_swap()` |
| `face_service.py` | Face swap logic | `swap_faces()`, `swap_faces_region()` |
| `enhancement_service.py` | GFPGAN enhancement | `enhance_image()`, `_get_enhancer()` |
| `job_store.py` | Redis job storage | `create_job()`, `update_job()`, `get_job()` |
| `index.js` | Main frontend | `handleSubmit()`, `pollJob()`, rendering |
| `ProgressComponent.js` | Progress display | `renderStageSteps()`, animations |

### Adding New Features

**To add a new processing stage:**
1. Update `STAGE_CONFIG` in `ProgressComponent.js`
2. Add progress update in `processor.py`
3. Update stage ranges in `renderStageSteps()`
4. Add CSS animations if needed

**To change progress percentages:**
1. Edit progress values in `processor.py`
2. Update stage ranges in `ProgressComponent.js`
3. Test full pipeline

**To add new API endpoints:**
1. Create route in `backend/app/routes/`
2. Include in `app.main.py`
3. Update frontend to call new endpoint

---

## ⚡ Performance Tips

### Optimization Checklist

- ✅ Use portraits (1080p recommended, max 4K)
- ✅ Ensure good lighting in source image
- ✅ Keep target image under 5MB
- ✅ Disable enhancement if speed needed
- ✅ Run on GPU if available (CUDA)
- ✅ Increase Redis timeout for large batches

### Benchmarks (CPU, Python 3.11)

| Component | Duration |
|-----------|----------|
| Model loading | 2-3 seconds |
| Face detection | 3-5 seconds |
| Face swap | 5-10 seconds |
| GFPGAN enhancement | 4-6 seconds |
| **Total (with enhancement)** | **21-31 seconds** |
| **Total (without enhancement)** | **16-25 seconds** |

### Polling Efficiency

- Current interval: **1.2 seconds** (balanced for responsiveness)
- Smaller interval (500ms): More responsive, more API load
- Larger interval (5s): Less responsive, lower API load
- Adjust in `frontend/pages/index.js`: `window.setInterval(pollJob, 1200)`

---

## 📄 Additional Resources

### Files in This Project

- `README.md` - Project overview
- `ARCHITECTURE.md` - Technical architecture details
- `QUICK_REFERENCE.md` - Quick command reference
- `REFACTORING_GUIDE.md` - Code organization guide
- `PROGRESS_UX_GUIDE.md` - Progress UI implementation
- `UX_IMPLEMENTATION_SUMMARY.md` - UI improvements summary
- `PROGRESS_UI_VISUAL_REFERENCE.md` - Visual component guide

### External Resources

- **InsightFace:** https://github.com/deepinsight/insightface
- **GFPGAN:** https://github.com/TencentARC/GFPGAN
- **FastAPI:** https://fastapi.tiangolo.com/
- **Next.js:** https://nextjs.org/
- **Docker:** https://docs.docker.com/

---

## 📞 Support & Contribution

### Reporting Issues

Include:
1. Steps to reproduce
2. Docker logs: `docker-compose logs -f`
3. Screenshots or error messages
4. System info (OS, Docker version, RAM)

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Add tests if applicable
5. Submit pull request with description

---

