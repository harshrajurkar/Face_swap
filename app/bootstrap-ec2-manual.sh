#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Manual EC2 bootstrap + app deploy (run on the EC2 instance as root).

Required:
  --alb-dns-name <dns>       ALB DNS (from `tofu output alb_dns_name`)
  --s3-bucket-name <bucket>  S3 bucket (from `tofu output storage_bucket_name`)
  --redis-endpoint <host>    Redis endpoint (from `tofu output redis_primary_endpoint`)

Optional:
  --aws-region <region>      Default: us-east-1
  --app-home <dir>           Default: /opt/ai-face-swap
  --repo-url <url>           Default: https://github.com/harshrajurkar/Face_swap.git
  --repo-branch <branch>     Default: version-1.0.30
  --frontend-image <uri>     Default: 132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:frontend
  --backend-image <uri>      Default: 132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:backend
  --execution-provider <v>   Default: CPUExecutionProvider
  --worker-concurrency <n>   Default: 1
  --worker-timeout <sec>     Default: 900
  --worker-retries <n>       Default: 2

Example:
  sudo bash bootstrap-ec2-manual.sh \
    --alb-dns-name ai-face-swap-dev-alb-xxxx.us-east-1.elb.amazonaws.com \
    --s3-bucket-name ai-face-swap-dev-storage-xxxx \
    --redis-endpoint ai-face-swap-dev-redis.xxxx.use1.cache.amazonaws.com
EOF
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

AWS_REGION="us-east-1"
APP_HOME="/opt/ai-face-swap"
REPO_URL="https://github.com/harshrajurkar/Face_swap.git"
REPO_BRANCH="version-1.0.30"
FRONTEND_IMAGE_URI="132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:frontend"
BACKEND_IMAGE_URI="132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:backend"
EXECUTION_PROVIDER="CPUExecutionProvider"
WORKER_CONCURRENCY="1"
WORKER_TIMEOUT="900"
WORKER_RETRIES="2"

ALB_DNS_NAME=""
S3_BUCKET_NAME=""
REDIS_ENDPOINT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alb-dns-name) ALB_DNS_NAME="$2"; shift 2 ;;
    --s3-bucket-name) S3_BUCKET_NAME="$2"; shift 2 ;;
    --redis-endpoint) REDIS_ENDPOINT="$2"; shift 2 ;;
    --aws-region) AWS_REGION="$2"; shift 2 ;;
    --app-home) APP_HOME="$2"; shift 2 ;;
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --repo-branch) REPO_BRANCH="$2"; shift 2 ;;
    --frontend-image) FRONTEND_IMAGE_URI="$2"; shift 2 ;;
    --backend-image) BACKEND_IMAGE_URI="$2"; shift 2 ;;
    --execution-provider) EXECUTION_PROVIDER="$2"; shift 2 ;;
    --worker-concurrency) WORKER_CONCURRENCY="$2"; shift 2 ;;
    --worker-timeout) WORKER_TIMEOUT="$2"; shift 2 ;;
    --worker-retries) WORKER_RETRIES="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$ALB_DNS_NAME" || -z "$S3_BUCKET_NAME" || -z "$REDIS_ENDPOINT" ]]; then
  usage
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (e.g. sudo bash bootstrap-ec2-manual.sh ...)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "Installing prerequisites..."
for i in 1 2 3; do
  apt-get update -y && apt-get install -y docker.io docker-compose awscli git jq && break
  echo "Retry $i failed. Sleeping 10s..."
  sleep 10
done

require_command docker
require_command aws
require_command git

systemctl enable docker
systemctl start docker

if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
else
  echo "Neither docker-compose nor docker compose is available." >&2
  exit 1
fi

APP_SHARED_DIR="${APP_HOME}/shared"
APP_REPO_DIR="${APP_HOME}/app"
mkdir -p "${APP_SHARED_DIR}/uploads" "${APP_SHARED_DIR}/outputs" "${APP_SHARED_DIR}/models"

if [[ -d "${APP_REPO_DIR}/.git" ]]; then
  echo "Refreshing repository..."
  git -C "${APP_REPO_DIR}" fetch --all --prune || true
  git -C "${APP_REPO_DIR}" checkout "${REPO_BRANCH}" || true
  git -C "${APP_REPO_DIR}" pull --ff-only origin "${REPO_BRANCH}" || true
else
  echo "Cloning repository..."
  git clone --branch "${REPO_BRANCH}" --single-branch "${REPO_URL}" "${APP_REPO_DIR}"
fi

COMPOSE_FILE="${APP_REPO_DIR}/app/docker-compose.aws.yml"
FRONTEND_CONTEXT="${APP_REPO_DIR}/app/frontend"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  COMPOSE_FILE="${APP_REPO_DIR}/docker-compose.aws.yml"
  FRONTEND_CONTEXT="${APP_REPO_DIR}/frontend"
fi
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Could not find docker-compose.aws.yml in cloned repository." >&2
  exit 1
fi

PUBLIC_BASE_URL="http://${ALB_DNS_NAME}"
ENV_FILE="${APP_HOME}/.env.aws"
FRONTEND_RUNTIME_IMAGE="ai-face-swap-frontend:bootstrap"

cat >"${ENV_FILE}" <<EOF
AWS_REGION=${AWS_REGION}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
S3_UPLOADS_PREFIX=uploads
S3_OUTPUTS_PREFIX=outputs
STORAGE_MODE=s3
REDIS_URL=redis://${REDIS_ENDPOINT}:6379/0
PUBLIC_BASE_URL=${PUBLIC_BASE_URL}
FRONTEND_IMAGE_URI=${FRONTEND_IMAGE_URI}
FRONTEND_RUNTIME_IMAGE=${FRONTEND_RUNTIME_IMAGE}
BACKEND_IMAGE_URI=${BACKEND_IMAGE_URI}
EXECUTION_PROVIDER=${EXECUTION_PROVIDER}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY}
WORKER_JOB_TIMEOUT_SECONDS=${WORKER_TIMEOUT}
WORKER_MAX_RETRIES=${WORKER_RETRIES}
APP_SHARED_DIR=${APP_SHARED_DIR}
CORS_ORIGINS=["${PUBLIC_BASE_URL}"]
EOF

echo "Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "132690414014.dkr.ecr.${AWS_REGION}.amazonaws.com"

if [[ -f "${FRONTEND_CONTEXT}/Dockerfile" ]]; then
  echo "Building frontend image with /api base..."
  docker build \
    -t "${FRONTEND_RUNTIME_IMAGE}" \
    --build-arg NEXT_PUBLIC_API_BASE_URL=/api \
    --build-arg NEXT_PUBLIC_BACKEND_ORIGIN="${PUBLIC_BASE_URL}" \
    "${FRONTEND_CONTEXT}"
else
  echo "Frontend Dockerfile not found at ${FRONTEND_CONTEXT}. Falling back to prebuilt frontend image."
  sed -i "s|^FRONTEND_RUNTIME_IMAGE=.*$|FRONTEND_RUNTIME_IMAGE=${FRONTEND_IMAGE_URI}|" "${ENV_FILE}"
fi

echo "Pulling backend image..."
docker pull "${BACKEND_IMAGE_URI}"

echo "Starting stack..."
"${COMPOSE_CMD[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --remove-orphans

echo
echo "Deployment complete."
"${COMPOSE_CMD[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
echo
echo "Open: ${PUBLIC_BASE_URL}"
echo "API : ${PUBLIC_BASE_URL}/api"
