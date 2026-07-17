#!/usr/bin/env sh
set -eu

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="$(id -un)"
PYTHON_BIN="$(command -v python3)"
SERVICE_FILE="/etc/systemd/system/toss-roa.service"

if [ ! -f "$APP_DIR/config.json" ]; then
  echo "config.json not found in $APP_DIR"
  exit 1
fi

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Toss ROA Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_BIN -m toss_roa.telegram_bot --config $APP_DIR/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable toss-roa.service
sudo systemctl restart toss-roa.service
sudo systemctl status toss-roa.service --no-pager

echo
echo "Installed toss-roa.service"
echo "View logs: sudo journalctl -u toss-roa.service -f"
echo "Stop: sudo systemctl stop toss-roa.service"
echo "Start: sudo systemctl start toss-roa.service"
