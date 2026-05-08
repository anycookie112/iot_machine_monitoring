#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

looks_like_machine_monitoring_env() {
  local file="$1"
  [[ -f "${file}" ]] || return 1
  grep -Eq '^(MM_DB_URL|MM_DB_USERNAME|MM_DB_PASSWORD|MM_DB_HOST|MM_DB_NAME|MM_MQTT_BROKER|MM_MQTT_PORT|MM_DASH_HOST|MM_DASH_PORT|MM_DASH_DEBUG|MM_GUNICORN_WORKERS)=' "${file}"
}

ENV_FILE="${MM_ENV_FILE:-}"
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
fi

DASH_HOST="${MM_DASH_HOST:-0.0.0.0}"
DASH_PORT="${MM_DASH_PORT:-8888}"
GUNICORN_WORKERS="${MM_GUNICORN_WORKERS:-1}"

exec gunicorn wsgi:server \
  --bind "${DASH_HOST}:${DASH_PORT}" \
  --workers "${GUNICORN_WORKERS}"
