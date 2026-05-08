#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
export PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

MODE="${1:-all}"
ENV_FILE="${MM_ENV_FILE:-}"

looks_like_machine_monitoring_env() {
  local file="$1"
  [[ -f "${file}" ]] || return 1
  grep -Eq '^(MM_DB_URL|MM_DB_USERNAME|MM_DB_PASSWORD|MM_DB_HOST|MM_DB_NAME|MM_MQTT_BROKER|MM_MQTT_PORT)=' "${file}"
}

validate_runtime_env() {
  local missing=()

  if [[ -z "${MM_DB_URL:-}" ]]; then
    [[ -n "${MM_DB_USERNAME:-}" ]] || missing+=("MM_DB_USERNAME")
    [[ -n "${MM_DB_PASSWORD:-}" ]] || missing+=("MM_DB_PASSWORD")
    [[ -n "${MM_DB_HOST:-}" ]] || missing+=("MM_DB_HOST")
    [[ -n "${MM_DB_NAME:-}" ]] || missing+=("MM_DB_NAME")
  fi

  [[ -n "${MM_MQTT_BROKER:-}" ]] || missing+=("MM_MQTT_BROKER")
  [[ -n "${MM_MQTT_PORT:-}" ]] || missing+=("MM_MQTT_PORT")

  if (( ${#missing[@]} > 0 )); then
    echo "Missing required machine-monitoring env vars: ${missing[*]}" >&2
    echo "Create .env.local from .env.example or set MM_ENV_FILE to a dedicated env file." >&2
    return 1
  fi
}

if [[ -z "${ENV_FILE}" ]]; then
  for candidate in \
    "${ROOT_DIR}/.env.local" \
    "/etc/machine-monitoring.env" \
    "${ROOT_DIR}/.env.machine-monitoring" \
    "${ROOT_DIR}/.env"
  do
    if [[ "${candidate}" == "${ROOT_DIR}/.env" ]]; then
      if looks_like_machine_monitoring_env "${candidate}"; then
        ENV_FILE="${candidate}"
        break
      fi
      continue
    fi

    if [[ -f "${candidate}" ]]; then
      ENV_FILE="${candidate}"
      break
    fi
  done
fi

if [[ -n "${ENV_FILE}" && -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  echo "Loaded environment from ${ENV_FILE}"
  validate_runtime_env
else
  echo "No machine-monitoring env file found. Set MM_ENV_FILE or create .env.local from .env.example." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if [[ "${MODE}" == "all" || "${MODE}" == "web" ]]; then
  if ! command -v gunicorn >/dev/null 2>&1; then
    echo "gunicorn is required for web mode" >&2
    exit 1
  fi
fi

WEB_PID=""
MQTT_PID=""

cleanup() {
  trap - EXIT INT TERM

  if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
    kill "${WEB_PID}" 2>/dev/null || true
    wait "${WEB_PID}" 2>/dev/null || true
  fi

  if [[ -n "${MQTT_PID}" ]] && kill -0 "${MQTT_PID}" 2>/dev/null; then
    kill "${MQTT_PID}" 2>/dev/null || true
    wait "${MQTT_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

start_mqtt() {
  echo "Starting MQTT consumer..."
  python3 "${ROOT_DIR}/scripts/run_mqtt_consumer.py" &
  MQTT_PID=$!
  echo "MQTT consumer PID: ${MQTT_PID}"
}

start_web() {
  echo "Starting web server on ${MM_DASH_HOST:-0.0.0.0}:${MM_DASH_PORT:-8888}..."
  "${ROOT_DIR}/scripts/run_web.sh" &
  WEB_PID=$!
  echo "Web server PID: ${WEB_PID}"
}

case "${MODE}" in
  all)
    start_mqtt
    start_web
    wait -n "${MQTT_PID}" "${WEB_PID}"
    ;;
  mqtt)
    start_mqtt
    wait "${MQTT_PID}"
    ;;
  web)
    start_web
    wait "${WEB_PID}"
    ;;
  *)
    echo "Usage: $0 [all|web|mqtt]" >&2
    exit 1
    ;;
esac
