# Face Swap App

This folder contains the runtime app stack:

- `frontend/` (Next.js)
- `backend/` (FastAPI)
- `worker/` (background processing in the backend image)
- compose files for local and AWS runtime

## Runtime Modes

1. Local development (`docker-compose.yml`)
- Runs Redis locally in Docker.
- Builds backend/frontend images from source.
- Uses local filesystem storage.

2. AWS runtime (`docker-compose.aws.yml`)
- Uses ElastiCache via `REDIS_URL`.
- Uses S3 via `STORAGE_MODE=s3` and bucket/prefix variables.
- Pulls prebuilt images from ECR (`BACKEND_IMAGE_URI`, `FRONTEND_RUNTIME_IMAGE`).

## Local Run

From `app/`:

```bash
docker compose up --build
```

## AWS EC2 Deploy

Deployment is driven by `/opt/scripts/deploy-ec2-single.sh` and `/opt/ai-face-swap/.env.runtime`.

The script:
- syncs the repo branch defined in env
- logs into ECR based on image URIs in env
- runs `docker compose --env-file ... -f docker-compose.aws.yml pull`
- runs `docker compose --env-file ... -f docker-compose.aws.yml up -d`

## Required AWS Runtime Variables

- `AWS_REGION`
- `APP_REPO_DIR`
- `REPO_URL`
- `GIT_BRANCH`
- `COMPOSE_FILE`
- `BACKEND_IMAGE_URI`
- `FRONTEND_RUNTIME_IMAGE`
- `REDIS_URL`
- `STORAGE_MODE` (must be `s3` for AWS runtime)
- `S3_BUCKET_NAME`
- `S3_UPLOADS_PREFIX`
- `S3_OUTPUTS_PREFIX`
- `PUBLIC_BASE_URL`
- `CORS_ORIGINS`
- `EXECUTION_PROVIDER`
- `WORKER_CONCURRENCY`
- `WORKER_JOB_TIMEOUT_SECONDS`
- `WORKER_MAX_RETRIES`
