#!/usr/bin/env bash
# Start/stop the two llama.cpp servers that back LightRAG.
#
#   LLM server      :8080  LFM2.5-1.2B-Thinking  (chat completions, entity extraction)
#   Embedding server:8081  bge-m3                 (/v1/embeddings, 1024-dim)
#
# LightRAG has no native llama.cpp binding, so it talks to these over the
# OpenAI-compatible REST API using the `openai` binding. See .env.example.
#
# Usage:
#   scripts/start_servers.sh [start|stop|status]   (default: start)
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-/opt/homebrew/opt/llama.cpp/bin/llama-server}"
LLM_PORT="${LLM_PORT:-8080}"
EMBED_PORT="${EMBED_PORT:-8081}"
LLM_ALIAS="${LLM_ALIAS:-lfm2.5-1.2b-thinking}"
EMBED_ALIAS="${EMBED_ALIAS:-bge-m3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

LLM_MODEL="${LLM_MODEL:-}"
EMBED_MODEL="${EMBED_MODEL:-}"
if [[ -z "${LLM_MODEL}" ]]; then
  LLM_MODEL="/Users/edis-mac/.cache/huggingface/hub/models--LiquidAI--LFM2.5-1.2B-Thinking-GGUF/snapshots/7cb86bcf8ccd6ef5eae50a9ccbdf690ee2646ee5/LFM2.5-1.2B-Thinking-Q4_K_M.gguf"
fi
if [[ -z "${EMBED_MODEL}" ]]; then
  EMBED_MODEL="/Users/edis-mac/.cache/huggingface/hub/models--gpustack--bge-m3-GGUF/snapshots/2d48f1737679ad900d5c26c5aad5410e9c70fdca/bge-m3-Q8_0.gguf"
fi

# HF hub snapshot symlinks may point at blobs; resolve to a real file so a
# changed snapshot revision can never break the running server.
for var in LLM_MODEL EMBED_MODEL; do
  path="${!var}"
  if [[ -e "${path}" ]]; then
    resolved="$(readlink -f "${path}" 2>/dev/null || echo "${path}")"
    eval "${var}='${resolved}'"
  fi
done

if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "error: llama-server not found at ${LLAMA_SERVER}" >&2
  echo "set LLAMA_SERVER=/path/to/llama-server to override" >&2
  exit 1
fi
for var in LLM_MODEL EMBED_MODEL; do
  if [[ ! -f "${!var}" ]]; then
    echo "error: model file missing: ${!var}" >&2
    exit 1
  fi
done

start_one() {
  local name="$1" port="$2" alias="$3" model="$4" log="$5" pidfile="$6"
  shift 6
  if [[ -f "${pidfile}" ]] && kill -0 "$(cat "${pidfile}")" 2>/dev/null; then
    echo "${name} already running (pid $(cat "${pidfile}"), port ${port})"
    return 0
  fi
  echo "starting ${name} on :${port} (alias=${alias})"
  nohup "${LLAMA_SERVER}" \
    --model "${model}" \
    --alias "${alias}" \
    --host 127.0.0.1 \
    --port "${port}" \
    -ngl 999 \
    "$@" >"${log}" 2>&1 &
  echo $! >"${pidfile}"
}

stop_one() {
  local name="$1" pidfile="$2"
  if [[ -f "${pidfile}" ]] && kill -0 "$(cat "${pidfile}")" 2>/dev/null; then
    kill "$(cat "${pidfile}")" && echo "stopped ${name} (pid $(cat "${pidfile}"))"
    rm -f "${pidfile}"
  else
    echo "${name} not running"
    rm -f "${pidfile}"
  fi
}

status() {
  local pid
  for spec in "llm:${LLM_PORT}:${LOG_DIR}/llm-server.pid" "bge-m3:${EMBED_PORT}:${LOG_DIR}/bge-m3.pid"; do
    IFS=: read -r name port pidfile <<<"${spec}"
    if [[ -f "${pidfile}" ]] && kill -0 "$(cat "${pidfile}")" 2>/dev/null; then
      pid="$(cat "${pidfile}")"
      echo "${name}: running (pid ${pid}, :${port})"
    else
      echo "${name}: not running (:${port})"
    fi
  done
}

case "${1:-start}" in
  start)
    start_one "llm" "${LLM_PORT}" "${LLM_ALIAS}" "${LLM_MODEL}" \
      "${LOG_DIR}/llm-server.log" "${LOG_DIR}/llm-server.pid" \
      --ctx-size 8192
    start_one "bge-m3" "${EMBED_PORT}" "${EMBED_ALIAS}" "${EMBED_MODEL}" \
      "${LOG_DIR}/bge-m3.log" "${LOG_DIR}/bge-m3.pid" \
      --embedding --pooling mean
    echo "waiting for servers to load models..."
    sleep 3
    curl -sf "http://127.0.0.1:${LLM_PORT}/v1/models" >/dev/null \
      && echo "llm OK: http://127.0.0.1:${LLM_PORT}/v1/models" \
      || echo "llm still loading — check ${LOG_DIR}/llm-server.log"
    curl -sf "http://127.0.0.1:${EMBED_PORT}/v1/models" >/dev/null \
      && echo "bge-m3 OK: http://127.0.0.1:${EMBED_PORT}/v1/models" \
      || echo "bge-m3 still loading — check ${LOG_DIR}/bge-m3.log"
    ;;
  stop)
    stop_one "llm" "${LOG_DIR}/llm-server.pid"
    stop_one "bge-m3" "${LOG_DIR}/bge-m3.pid"
    ;;
  status)
    status
    ;;
  *)
    echo "usage: $0 [start|stop|status]" >&2
    exit 1
    ;;
esac
