#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="dev-env-service"
container_project="/home/dev/workspace/RobotOps-AI"

if ! docker inspect -f '{{.State.Running}}' "${container_name}" 2>/dev/null | grep -q true; then
  echo "Docker container ${container_name} is not running."
  exit 1
fi

wait_for_service() {
  local name="$1"
  local url="$2"
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "${name}: ready"
      return 0
    fi
    sleep 0.5
  done
  echo "${name}: failed to start (${url})"
  return 1
}

if ! curl -fsS http://127.0.0.1:9001/health >/dev/null 2>&1; then
  docker exec -d -w "${container_project}" \
    -e ROBOTOPS_LOG_RPC_PORT=9001 \
    "${container_name}" \
    ./build/backend/services/log_service/log_service
fi
wait_for_service "log-service" "http://127.0.0.1:9001/health"

embedding_model="${ROBOTOPS_EMBEDDING_MODEL:-BAAI/bge-small-zh-v1.5}"
if [[ "${ROBOTOPS_EMBEDDING_ENABLED:-true}" != "false" ]]; then
  embedding_env=( -e "ROBOTOPS_EMBEDDING_MODEL=${embedding_model}" )
  if [[ -n "${ROBOTOPS_EMBEDDING_CACHE_DIR:-}" ]]; then
    embedding_env+=( -e "ROBOTOPS_EMBEDDING_CACHE_DIR=${ROBOTOPS_EMBEDDING_CACHE_DIR}" )
  fi
  if ! curl -fsS http://127.0.0.1:9004/health >/dev/null 2>&1; then
    docker exec -d -w "${container_project}" \
      "${embedding_env[@]}" \
      "${container_name}" \
      python3 -m uvicorn embedding_service.app:app --host 0.0.0.0 --port 9004
  fi
  wait_for_service "embedding-service" "http://127.0.0.1:9004/health"
fi

if ! curl -fsS http://127.0.0.1:9003/health >/dev/null 2>&1; then
  agent_env=(
    -e ROBOTOPS_LOG_SERVICE_URL=http://127.0.0.1:9001
    -e ROBOTOPS_SOURCE_SEARCH_ROOTS=/home/dev/workspace/interaction
    -e ROBOTOPS_SOURCE_INDEX_ROOT=/home/dev/workspace/RobotOps-AI/.robotops/source-index
  )
  if [[ "${ROBOTOPS_EMBEDDING_ENABLED:-true}" != "false" ]]; then
    agent_env+=(
      -e ROBOTOPS_RAG_EMBEDDING_URL=http://127.0.0.1:9004/v1
      -e ROBOTOPS_RAG_EMBEDDING_MODEL="${embedding_model}"
      -e ROBOTOPS_RAG_EMBEDDING_DIMENSIONS=512
    )
  fi
  for rag_var in ROBOTOPS_RAG_BACKEND ROBOTOPS_RAG_ELASTICSEARCH_URL ROBOTOPS_RAG_ELASTICSEARCH_USER ROBOTOPS_RAG_ELASTICSEARCH_PASSWORD ROBOTOPS_RAG_INDEX_PREFIX; do
    if [[ -n "${!rag_var:-}" ]]; then
      agent_env+=( -e "${rag_var}=${!rag_var}" )
    fi
  done
  if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
    agent_env+=(
      -e ROBOTOPS_LLM_ENABLED=true
      -e DEEPSEEK_API_KEY
    )
    echo "agent-service: DeepSeek enabled from shell environment"
  else
    agent_env+=( -e ROBOTOPS_LLM_ENABLED=false )
    echo "agent-service: DEEPSEEK_API_KEY is not set, using deterministic fallback"
  fi
  docker exec -d -w "${container_project}" \
    "${agent_env[@]}" \
    "${container_name}" \
    python3 -m uvicorn agent_service.app.main:app --host 0.0.0.0 --port 9003
fi
wait_for_service "agent-service" "http://127.0.0.1:9003/health"

if ! curl -fsS http://127.0.0.1:9002/health >/dev/null 2>&1; then
  docker exec -d -w "${container_project}" \
    -e ROBOTOPS_AGENT_SERVICE_URL=http://127.0.0.1:9003 \
    -e ROBOTOPS_AGENT_HTTP_TIMEOUT_MS=300000 \
    -e ROBOTOPS_TICKET_DIAGNOSIS_RPC_PORT=9002 \
    "${container_name}" \
    ./build/backend/services/ticket_diagnosis_service/ticket_diagnosis_service
fi
wait_for_service "ticket-diagnosis-service" "http://127.0.0.1:9002/health"

curl -fsS -X POST \
  http://127.0.0.1:9001/robotops.log.LogService/ImportLogPackage \
  -H 'Content-Type: application/json' \
  -d '{"bug_id":"bug-frontend-e2e","package_id":"pkg-20260730","package_path":"samples/robot_20260730","robot_type":"ROBOT_TYPE_T"}' \
  >/dev/null
echo "sample logs: pkg-20260730 imported"

if curl -fsS http://127.0.0.1:4173/ >/dev/null 2>&1; then
  echo "web-console: already running at http://127.0.0.1:4173/"
  exit 0
fi

cd "${project_root}/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi

echo "web-console: http://127.0.0.1:4173/"
exec npm run dev -- --host 0.0.0.0
