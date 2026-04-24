#!/usr/bin/env bash
set -euo pipefail

# Fixed deployment configuration (as requested)
AWS_REGION="us-east-1"
APP_HOME="/opt/ai-face-swap"
APP_REPO_DIR="${APP_HOME}/app"
COMPOSE_FILE="${APP_REPO_DIR}/docker-compose.aws-build.yml"
ENV_FILE="${APP_HOME}/.env.aws"
ALB_DNS_NAME="ai-face-swap-dev-alb-1017164692.us-east-1.elb.amazonaws.com"
S3_BUCKET_NAME="ai-face-swap-dev-storage-b9797269"
REDIS_ENDPOINT="ai-face-swap-dev-redis.whxz4z.ng.0001.use1.cache.amazonaws.com"
EXECUTION_PROVIDER="CPUExecutionProvider"
WORKER_CONCURRENCY="1"
WORKER_JOB_TIMEOUT_SECONDS="900"
WORKER_MAX_RETRIES="2"
GIT_BRANCH="version-1.0.30"
REPO_URL="https://github.com/harshrajurkar/Face_swap.git"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root (sudo su - then bash deploy-ec2-single.sh)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "Installing Docker, Compose, AWS CLI, and Git..."
for i in 1 2 3; do
  if apt-get update -y && apt-get install -y docker.io docker-compose awscli git jq; then
    break
  fi
  echo "Install attempt $i failed. Retrying in 10 seconds..."
  sleep 10
done

require_command docker
require_command aws
require_command git

if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
else
  echo "Neither docker-compose nor docker compose is available." >&2
  exit 1
fi

systemctl enable docker
systemctl start docker

APP_SHARED_DIR="${APP_HOME}/shared"
mkdir -p "${APP_SHARED_DIR}/uploads" "${APP_SHARED_DIR}/outputs" "${APP_SHARED_DIR}/models"
mkdir -p "${APP_HOME}"

if [[ -d "${APP_REPO_DIR}/.git" ]]; then
  echo "Updating repository..."
  git -C "${APP_REPO_DIR}" fetch origin "${GIT_BRANCH}"
  git -C "${APP_REPO_DIR}" checkout "${GIT_BRANCH}"
  git -C "${APP_REPO_DIR}" pull --ff-only origin "${GIT_BRANCH}"
else
  echo "Cloning repository..."
  git clone --branch "${GIT_BRANCH}" --single-branch "${REPO_URL}" "${APP_REPO_DIR}"
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  if [[ -f "${APP_REPO_DIR}/app/docker-compose.aws-build.yml" ]]; then
    COMPOSE_FILE="${APP_REPO_DIR}/app/docker-compose.aws-build.yml"
  else
    echo "Compose file not found at ${COMPOSE_FILE} or ${APP_REPO_DIR}/app/docker-compose.aws-build.yml" >&2
    exit 1
  fi
fi

cat >"${ENV_FILE}" <<EOF
AWS_REGION=${AWS_REGION}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
S3_UPLOADS_PREFIX=uploads
S3_OUTPUTS_PREFIX=outputs
STORAGE_MODE=s3
REDIS_URL=redis://${REDIS_ENDPOINT}:6379/0
PUBLIC_BASE_URL=http://${ALB_DNS_NAME}
EXECUTION_PROVIDER=${EXECUTION_PROVIDER}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY}
WORKER_JOB_TIMEOUT_SECONDS=${WORKER_JOB_TIMEOUT_SECONDS}
WORKER_MAX_RETRIES=${WORKER_MAX_RETRIES}
APP_SHARED_DIR=${APP_SHARED_DIR}
CORS_ORIGINS=["http://${ALB_DNS_NAME}"]
EOF

echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "132690414014.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Building backend and frontend images from Dockerfiles..."
"${COMPOSE_CMD[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" build backend frontend

echo "Starting backend, worker, and frontend with ElastiCache + S3 config..."
"${COMPOSE_CMD[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "Deployment complete. Service status:"
"${COMPOSE_CMD[@]}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

echo
echo "UI is running on http://${ALB_DNS_NAME}"
echo "API base URL:      http://${ALB_DNS_NAME}/api"
