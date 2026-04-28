# AI Face Swap Platform: Full Architecture and Flow Guide

This document explains the current codebase end-to-end in beginner-friendly language:

- What each part of the system does
- Why this architecture was chosen
- How requests move through the system
- How infrastructure, deployment, and monitoring work together

If you are new to DevOps or full-stack systems, read this file from top to bottom once, then use it as a reference.

## 1) Big Picture

The platform has four main layers:

1. `Frontend` (`Next.js`): user uploads images, tracks job progress, and downloads results.
2. `Backend API` (`FastAPI`): validates uploads, creates jobs, stores status, serves output files.
3. `Worker` (`Python`): does CPU-heavy AI face swap processing asynchronously.
4. `Infrastructure` (`OpenTofu` on AWS): networking, load balancing, compute, storage, queue backend, and observability routing.

Monitoring is built into runtime using:

- `Prometheus` for metrics collection
- `Grafana` for dashboards
- `node-exporter` and `cAdvisor` for host/container metrics

## 2) Repository Layout

```text
repo-clean/
|-- app/
|   |-- backend/                      # FastAPI app + worker logic
|   |-- frontend/                     # Next.js UI
|   |-- docker-compose.yml            # Local stack
|   |-- docker-compose.aws.yml        # EC2 runtime stack (ECR images)
|   |-- docker-compose.aws-build.yml  # EC2 build-on-server stack
|   |-- deploy-ec2-single.sh          # Runtime deployment script on EC2
|   `-- monitoring/                   # Prometheus/Grafana config and dashboards
|-- infra/
|   |-- main.tf                       # AWS resources
|   |-- variables.tf                  # Input variables
|   |-- output.tf                     # Infra outputs
|   |-- tofu.auto.tfvars.example      # Example runtime values
|   `-- templates/app_user_data.sh.tftpl
|-- .github/workflows/deploy.yml      # CI/CD pipeline
`-- screenshots/monitoring/           # Monitoring proof screenshots
```

## 3) Why This Architecture

### 3.1 Async job model (API + queue + worker)

Face swap is heavy work. If API handled it inline, users would wait on one long HTTP request and risk timeouts.

Instead:

- API only accepts files and creates a queued job quickly.
- Worker consumes queued jobs and processes them in background.
- Frontend polls status and shows progress.

This gives better reliability and better user experience.

### 3.2 Separation of concerns

- Frontend handles UX only.
- API handles orchestration and validation.
- Worker handles AI compute.
- Redis handles queue and job status state.
- S3 stores durable files in AWS runtime.

Each component has one clear responsibility.

### 3.3 Single-VM runtime with clear upgrade path

Current runtime is EC2 + Docker Compose. It is easier to operate while still using production-like AWS building blocks (ALB, IAM, S3, ElastiCache, CI/CD).

## 4) End-to-End Request Flow

## 4.1 User flow in UI

File: `app/frontend/pages/index.js`

1. User selects source and target images.
2. UI sends `POST /api/create-job` with multipart form data.
3. UI receives `job_id`.
4. UI polls `GET /api/job/{job_id}` every 1200ms.
5. UI shows stage/progress from server.
6. On completion, UI renders output and enables download.

## 4.2 API flow

Files: `app/backend/app/main.py`, `app/backend/app/routes/job.py`

- `POST /api/create-job`
  - validates image MIME types
  - saves uploads using `StorageService`
  - creates job record in Redis with initial status
  - pushes queue payload to Redis list
  - returns `202 Accepted` with `job_id`

- `GET /api/job/{job_id}`
  - returns live job status from Redis

- `GET /outputs/{filename}`
  - if S3 mode: streams object via backend
  - if local mode: serves local file

## 4.3 Queue and job state flow

Files: `queue_service.py`, `job_store.py`

- Queue uses Redis `RPUSH` + blocking `BLPOP`.
- Job state is stored as JSON under key `job:{job_id}` with TTL.
- Job updates include status, stage, progress, message, output URL, and errors.
- Redis operations include retry logic for transient network errors.

## 4.4 Worker processing flow

Files: `worker/worker.py`, `worker/processor.py`

1. Worker warms up AI models.
2. Worker dequeues one job at a time.
3. Processor sets job `processing` and updates progress stages.
4. Face swap pipeline runs in thread pool.
5. Optional enhancement stage runs (GFPGAN).
6. Output is published (local or S3).
7. Job marked `completed` with output URL.
8. On failure/timeout, retries are handled up to configured max retries.

## 5) Infrastructure Flow (OpenTofu)

Main file: `infra/main.tf`

## 5.1 Network and security

- VPC with 2 public + 2 private app + 2 private data subnets
- Internet Gateway + NAT for private outbound
- Security groups:
  - ALB allows `80` (and `443` when HTTPS enabled)
  - App SG allows traffic from ALB to frontend/backend/grafana ports
  - Redis SG allows app tier access to Redis port

## 5.2 Compute and app runtime

- EC2 instance in private app subnet
- IAM role grants:
  - SSM access
  - ECR pull permissions
  - S3 object access
  - CloudWatch agent policy

User data script:

- installs Docker and tools
- creates swap file
- clones app repo
- writes runtime env file (`/opt/ai-face-swap/.env.runtime`)
- runs deploy script

## 5.3 Load balancing and routing

- ALB with frontend target group (`3000`) and backend target group (`8000`)
- Path routing:
  - `/api/*`, `/health`, `/outputs/*` -> backend target group
  - default -> frontend target group
- Grafana target group (`3001`) with ALB route:
  - `/grafana*` -> grafana target group

HTTPS mode:

- optional and controlled by variables
- can use direct ACM ARN or auto-resolve by certificate domain

## 5.4 Data services

- ElastiCache Redis for queue + status
- S3 bucket for uploads/outputs
- encryption enabled on storage components

## 6) Deployment Flow (CI/CD)

Workflow: `.github/workflows/deploy.yml`

Trigger:

- push to `main`
- push to branches matching `v*`

Pipeline steps:

1. Build backend/frontend images
2. Push images to ECR (`sha-<commit>` and `latest`)
3. Find target EC2 by tag
4. Resolve latest OpenTofu-managed S3 bucket
5. Update runtime env values on EC2 via SSM command
6. Sync branch on EC2
7. Run `/opt/scripts/deploy-ec2-single.sh`
8. Enforce `docker compose ... up -d` to ensure monitoring stack is up

This means regular app changes are deployed by push only. You run `tofu apply` only for infrastructure changes.

## 7) Monitoring and Observability Flow

Files:

- `app/monitoring/prometheus/prometheus.yml`
- `app/monitoring/prometheus/alert_rules.yml`
- `app/monitoring/grafana/provisioning/*`
- `app/monitoring/grafana/dashboards/faceswap-observability.json`

Runtime services in compose:

- `prometheus` (`:9090`)
- `grafana` (`:3001`)
- `node-exporter` (`:9100`)
- `cadvisor` (`:8081`)

App metrics:

- backend exposes `/metrics` via `prometheus-fastapi-instrumentator`
- Prometheus scrapes backend, node-exporter, cAdvisor, and itself

Grafana:

- pre-provisioned Prometheus data source
- pre-provisioned dashboard "Face Swap Observability Overview"
- ALB path access at `/grafana`

## 8) What to Run and When

## 8.1 First-time environment setup

1. Configure `infra/tofu.auto.tfvars` (repo URL, branch, image URIs, storage mode values)
2. Run:

```bash
cd infra
tofu init
tofu apply
```

3. Verify outputs:

```bash
tofu output public_base_url
tofu output grafana_url
```

## 8.2 Day-to-day app changes

1. Change code in `app/`
2. Push to `main` or `v*` branch
3. GitHub Actions deploys automatically

No `tofu apply` needed unless infra changed.

## 8.3 Monitoring checks

On EC2:

```bash
cd /opt/ai-face-swap/repo/app
docker compose --env-file /opt/ai-face-swap/.env.runtime -f docker-compose.aws.yml ps
curl -I http://localhost:9090/-/healthy
curl -I http://localhost:3001/login
```

From browser:

- App: `<public_base_url>`
- Grafana: `<public_base_url>/grafana`

## 9) Beginner Mental Model

Think of the system as two tracks:

1. `Control track`: API + Redis status
2. `Compute track`: Worker + AI inference

The browser talks to control track only. The heavy processing happens in compute track. Redis is the handoff point between both tracks.

On deployment side:

1. OpenTofu creates and wires infrastructure
2. CI/CD updates container images and restarts runtime services
3. Monitoring stack shows health and behavior continuously

## 10) Common Failure Points and Fast Fixes

1. `Job stuck queued`:
   - check worker container status and logs
   - verify Redis endpoint connectivity

2. `Output download fails`:
   - check S3 bucket name/prefix in runtime env
   - verify IAM object permissions

3. `Grafana unavailable from browser`:
   - verify ALB listener rule for `/grafana*`
   - verify grafana container healthy and target group healthy

4. `HTTPS not working`:
   - ensure `enable_https=true`
   - provide valid ACM ARN or resolvable cert domain in region

5. `Monitoring has no data`:
   - check Prometheus targets status (`UP`)
   - verify backend `/metrics` endpoint reachable

## 11) Reference File Index

Application:

- `app/frontend/pages/index.js`
- `app/frontend/components/ProgressComponent.js`
- `app/backend/app/main.py`
- `app/backend/app/routes/job.py`
- `app/backend/app/services/job_store.py`
- `app/backend/app/services/queue_service.py`
- `app/backend/app/services/storage_service.py`
- `app/backend/worker/worker.py`
- `app/backend/worker/processor.py`

Infrastructure:

- `infra/main.tf`
- `infra/variables.tf`
- `infra/output.tf`
- `infra/templates/app_user_data.sh.tftpl`

Deployment and monitoring:

- `.github/workflows/deploy.yml`
- `app/docker-compose.aws.yml`
- `app/monitoring/prometheus/prometheus.yml`
- `app/monitoring/prometheus/alert_rules.yml`
- `app/monitoring/grafana/provisioning/datasources/datasource.yml`
- `app/monitoring/grafana/provisioning/dashboards/dashboard.yml`
- `app/monitoring/grafana/dashboards/faceswap-observability.json`
