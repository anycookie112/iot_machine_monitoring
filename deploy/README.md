# Machine Monitoring Deployment

This repo now assumes a split runtime model:

- Dash/Gunicorn serves the web UI only.
- A dedicated MQTT consumer process owns subscriptions and background side effects.
- Mosquitto and Node-RED stay as separate infrastructure services.

## Quick manual start

For a small server or manual testing, you can start both the web UI and MQTT consumer with one command:

```bash
./scripts/start_server.sh
```

Optional modes:

```bash
./scripts/start_server.sh web
./scripts/start_server.sh mqtt
```

The launcher will load the first env file it finds from:

- `.env.local`
- `.env`
- `/etc/machine-monitoring.env`

## Required runtime config

Copy `.env.example` to a real environment file such as `/etc/machine-monitoring.env` and set:

- `MM_DB_USERNAME`
- `MM_DB_PASSWORD`
- `MM_DB_HOST`
- `MM_DB_NAME`
- `MM_MQTT_BROKER`
- `MM_MQTT_PORT`

Optional web settings:

- `MM_DASH_HOST`
- `MM_DASH_PORT`
- `MM_GUNICORN_WORKERS`

Keep `MM_GUNICORN_WORKERS=1` until MQTT remains fully isolated from the web process in production.

## systemd units

Install the units from `deploy/systemd/`:

- `machine-monitoring-web.service`
- `machine-monitoring-mqtt.service`

Suggested commands:

```bash
sudo cp deploy/systemd/machine-monitoring-web.service /etc/systemd/system/
sudo cp deploy/systemd/machine-monitoring-mqtt.service /etc/systemd/system/
sudo cp .env.example /etc/machine-monitoring.env
sudo systemctl daemon-reload
sudo systemctl enable --now machine-monitoring-web.service
sudo systemctl enable --now machine-monitoring-mqtt.service
```

## Operational checks

- `systemctl status machine-monitoring-web.service`
- `systemctl status machine-monitoring-mqtt.service`
- `journalctl -u machine-monitoring-web.service -f`
- `journalctl -u machine-monitoring-mqtt.service -f`

## Network boundary

This deployment is intended to stay LAN-only.

- Restrict `8888`, `1883`, and `1880` to trusted subnets or VLANs.
- Do not expose Dash, Mosquitto, or Node-RED directly to the public internet.
