#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="us-east-1"
APP_HOME="/opt/ai-face-swap"
APP_REPO_DIR="${APP_HOME}/app"
COMPOSE_FILE="${APP_REPO_DIR}/docker-compose.aws.yml"
ENV_FILE="${APP_HOME}/.env.aws"
ALB_DNS_NAME=""
S3_BUCKET_NAME=""
REDIS_ENDPOINT=""
FRONTEND_IMAGE_URI="132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:frontend"
BACKEND_IMAGE_URI="132690414014.dkr.ecr.us-east-1.amazonaws.com/ai-face-swap:backend"
EXECUTION_PROVIDER="CPUExecutionProvider"
WORKER_CONCURRENCY="1"
WORKER_JOB_TIMEOUT_SECONDS="900"
WORKER_MAX_RETRIES="2"

usage() {
  cat <<'EOF'
Usage:
  deploy-aws-stack.sh --alb-dns-name <dns> --s3-bucket-name <bucket> --redis-endpoint <host> [options]

Required:
  --alb-dns-name <dns>       ALB DNS output from OpenTofu
  --s3-bucket-name <bucket>  S3 bucket output from OpenTofu
  --redis-endpoint <host>    ElastiCache Redis endpoint output from OpenTofu

Optional:
  --aws-region <region>      AWS region (default: us-east-1)
  --app-home <dir>           Deployment home directory (default: /opt/ai-face-swap)
  --frontend-image <uri>     Frontend image URI
  --backend-image <uri>      Backend/worker image URI
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
      COMPOSE_FILE="${APP_REPO_DIR}/docker-compose.aws.yml"
      ENV_FILE="${APP_HOME}/.env.aws"
      shift 2
      ;;
    --frontend-image)
      FRONTEND_IMAGE_URI="$2"
      shift 2
      ;;
    --backend-image)
      BACKEND_IMAGE_URI="$2"
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

echo "Logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "132690414014.dkr.ecr.${AWS_REGION}.amazonaws.com"

cat >"$ENV_FILE" <<EOF
AWS_REGION=${AWS_REGION}
S3_BUCKET_NAME=${S3_BUCKET_NAME}
S3_UPLOADS_PREFIX=uploads
S3_OUTPUTS_PREFIX=outputs
STORAGE_MODE=s3
REDIS_URL=redis://${REDIS_ENDPOINT}:6379/0
PUBLIC_BASE_URL=http://${ALB_DNS_NAME}
FRONTEND_IMAGE_URI=${FRONTEND_IMAGE_URI}
BACKEND_IMAGE_URI=${BACKEND_IMAGE_URI}
EXECUTION_PROVIDER=${EXECUTION_PROVIDER}
WORKER_CONCURRENCY=${WORKER_CONCURRENCY}
WORKER_JOB_TIMEOUT_SECONDS=${WORKER_JOB_TIMEOUT_SECONDS}
WORKER_MAX_RETRIES=${WORKER_MAX_RETRIES}
APP_SHARED_DIR=${APP_SHARED_DIR}
CORS_ORIGINS=["http://${ALB_DNS_NAME}"]
EOF

echo "Pulling latest repo changes..."
git -C "$APP_REPO_DIR" pull --ff-only || true

echo "Pulling images..."
docker pull "$FRONTEND_IMAGE_URI"
docker pull "$BACKEND_IMAGE_URI"

echo "Starting compose stack..."
"${DOCKER_COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

echo "Deployment status:"
"${DOCKER_COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo
echo "Deployment completed."
echo "Public URL: http://${ALB_DNS_NAME}"
echo "API URL:    http://${ALB_DNS_NAME}/api"
