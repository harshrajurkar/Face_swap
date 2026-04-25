#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/ai-face-swap/.env.runtime}"

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root (sudo bash /opt/scripts/deploy-ec2-single.sh)." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Runtime env file not found: ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

require_command docker
require_command aws
require_command git

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is required." >&2
  exit 1
fi

if [[ -z "${APP_REPO_DIR:-}" || -z "${REPO_URL:-}" || -z "${GIT_BRANCH:-}" ]]; then
  echo "APP_REPO_DIR, REPO_URL, and GIT_BRANCH must be set in ${ENV_FILE}." >&2
  exit 1
fi

if [[ -z "${COMPOSE_FILE:-}" ]]; then
  COMPOSE_FILE="${APP_REPO_DIR}/app/docker-compose.aws.yml"
fi

if [[ ! -d "${APP_REPO_DIR}/.git" ]]; then
  git clone --branch "${GIT_BRANCH}" --single-branch "${REPO_URL}" "${APP_REPO_DIR}"
else
  git -C "${APP_REPO_DIR}" fetch origin "${GIT_BRANCH}"
  git -C "${APP_REPO_DIR}" checkout "${GIT_BRANCH}"
  git -C "${APP_REPO_DIR}" pull --ff-only origin "${GIT_BRANCH}"
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

if [[ -z "${BACKEND_IMAGE_URI:-}" || -z "${FRONTEND_RUNTIME_IMAGE:-}" ]]; then
  echo "BACKEND_IMAGE_URI and FRONTEND_RUNTIME_IMAGE must be set in ${ENV_FILE}." >&2
  exit 1
fi

BACKEND_REGISTRY="${BACKEND_IMAGE_URI%%/*}"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${BACKEND_REGISTRY}"

FRONTEND_REGISTRY="${FRONTEND_RUNTIME_IMAGE%%/*}"
if [[ "${FRONTEND_REGISTRY}" != "${BACKEND_REGISTRY}" ]]; then
  aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${FRONTEND_REGISTRY}"
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull backend worker frontend
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --remove-orphans
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

echo "Deployment complete."
echo "UI base URL: ${PUBLIC_BASE_URL}"
echo "API base URL: ${PUBLIC_BASE_URL}/api"

# checking-purpose