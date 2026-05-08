import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MACHINE_MONITORING_ENV_KEYS = (
    "MM_DB_URL",
    "MM_DB_USERNAME",
    "MM_DB_PASSWORD",
    "MM_DB_HOST",
    "MM_DB_NAME",
    "MM_MQTT_BROKER",
    "MM_MQTT_PORT",
    "MM_DASH_HOST",
    "MM_DASH_PORT",
    "MM_DASH_DEBUG",
    "MM_GUNICORN_WORKERS",
)


def _looks_like_machine_monitoring_env(env_path):
    if not env_path.is_file():
        return False

    try:
        with env_path.open() as env_file:
            return any(
                line.startswith(
                    (
                        "MM_DB_URL=",
                        "MM_DB_USERNAME=",
                        "MM_DB_PASSWORD=",
                        "MM_DB_HOST=",
                        "MM_DB_NAME=",
                        "MM_MQTT_BROKER=",
                        "MM_MQTT_PORT=",
                    )
                )
                for line in env_file
            )
    except OSError:
        return False


def _load_machine_monitoring_env():
    explicit_env_file = os.getenv("MM_ENV_FILE")
    candidates = []

    if explicit_env_file:
        candidates.append(Path(explicit_env_file).expanduser())

    candidates.extend(
        (
            ROOT_DIR / ".env.local",
            Path("/etc/machine-monitoring.env"),
            ROOT_DIR / ".env.machine-monitoring",
            ROOT_DIR / ".env",
        )
    )

    for candidate in candidates:
        if candidate == ROOT_DIR / ".env" and not _looks_like_machine_monitoring_env(candidate):
            continue

        if not candidate.is_file():
            continue

        try:
            with candidate.open() as env_file:
                for raw_line in env_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    name, value = line.split("=", 1)
                    if name in MACHINE_MONITORING_ENV_KEYS:
                        os.environ.setdefault(name, value)
        except OSError:
            continue

        break


_load_machine_monitoring_env()


def _get_env(name, default=None):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_int_env(name, default):
    raw_value = _get_env(name)
    if raw_value is None:
        return default
    return int(raw_value)


DB_CONFIG = {
    "username": _get_env("MM_DB_USERNAME", ""),
    "password": _get_env("MM_DB_PASSWORD", ""),
    "host": _get_env("MM_DB_HOST", "127.0.0.1"),
    "database": _get_env("MM_DB_NAME", "machine_monitoring"),
}

DB_URL = _get_env("MM_DB_URL")

MQTT_CONFIG = {
    "mqtt_broker": _get_env("MM_MQTT_BROKER", "127.0.0.1"),
    "mqtt_port": _get_int_env("MM_MQTT_PORT", 1883),
}

APP_CONFIG = {
    "dash_host": _get_env("MM_DASH_HOST", "0.0.0.0"),
    "dash_port": _get_int_env("MM_DASH_PORT", 8888),
    "dash_debug": _get_env("MM_DASH_DEBUG", "false").lower() == "true",
    "gunicorn_workers": _get_int_env("MM_GUNICORN_WORKERS", 1),
}
