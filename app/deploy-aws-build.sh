#!/usr/bin/env bash
set -euo pipefail

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

usage() {
  cat <<'EOF'
Usage:
  deploy-aws-build.sh --alb-dns-name <dns> --s3-bucket-name <bucket> --redis-endpoint <host> [options]

Required:
  --alb-dns-name <dns>       ALB DNS output from OpenTofu
  --s3-bucket-name <bucket>  S3 bucket output from OpenTofu
  --redis-endpoint <host>    ElastiCache Redis endpoint output from OpenTofu

Optional:
  --aws-region <region>      AWS region (default: us-east-1)
  --app-home <dir>           Deployment home directory (default: /opt/ai-face-swap)
  --git-branch <branch>      Git branch to pull before building (default: version-1.0.30)
EOF
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alb-dns-name)
      ALB_DNS_NAME="$2"
      shift 2
      ;;
    --s3-bucket-name)
      S3_BUCKET_NAME="$2"
      shift 2
      ;;
    --redis-endpoint)
      REDIS_ENDPOINT="$2"
      shift 2
      ;;
    --aws-region)
      AWS_REGION="$2"
      shift 2
      ;;
    --app-home)
      APP_HOME="$2"
      APP_REPO_DIR="${APP_HOME}/app"
      COMPOSE_FILE="${APP_REPO_DIR}/docker-compose.aws-build.yml"
      ENV_FILE="${APP_HOME}/.env.aws"
      shift 2
      ;;
    --git-branch)
      GIT_BRANCH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ALB_DNS_NAME" || -z "$S3_BUCKET_NAME" || -z "$REDIS_ENDPOINT" ]]; then
  usage
  exit 1
fi

require_command aws
require_command docker
require_command git

if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  echo "Docker Compose is not installed." >&2
  exit 1
fi

APP_SHARED_DIR="${APP_HOME}/shared"
mkdir -p "${APP_SHARED_DIR}/uploads" "${APP_SHARED_DIR}/outputs" "${APP_SHARED_DIR}/models"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

cat >"$ENV_FILE" <<EOF
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

echo "Pulling latest repo changes..."
git -C "$APP_REPO_DIR" fetch origin "$GIT_BRANCH"
git -C "$APP_REPO_DIR" checkout "$GIT_BRANCH"
git -C "$APP_REPO_DIR" pull --ff-only origin "$GIT_BRANCH"

echo "Building backend and frontend on the server..."
"${DOCKER_COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend

echo "Starting compose stack..."
"${DOCKER_COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

echo "Deployment status:"
"${DOCKER_COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo
echo "Deployment completed."
echo "Public URL: http://${ALB_DNS_NAME}"
echo "API URL:    http://${ALB_DNS_NAME}/api"
