#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
BIN_DIR="${HOME}/.local/bin"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="niri-desktop.service"

mkdir -p "$BIN_DIR" "$SERVICE_DIR"

install -m 0755 "$SCRIPT_DIR/niri-desktop.py"        "$BIN_DIR/niri-desktop.py"
install -m 0755 "$SCRIPT_DIR/niri-desktop-launch.sh" "$BIN_DIR/niri-desktop-launch.sh"
install -m 0644 "$SCRIPT_DIR/$SERVICE_NAME"          "$SERVICE_DIR/$SERVICE_NAME"

echo "Installed:"
echo "  $BIN_DIR/niri-desktop.py"
echo "  $BIN_DIR/niri-desktop-launch.sh"
echo "  $SERVICE_DIR/$SERVICE_NAME"

systemctl --user daemon-reload

if systemctl --user is-enabled --quiet "$SERVICE_NAME"; then
    echo "Service already enabled, restarting..."
    systemctl --user restart "$SERVICE_NAME"
else
    echo "Enabling and starting $SERVICE_NAME..."
    systemctl --user enable --now "$SERVICE_NAME"
fi

echo
systemctl --user --no-pager status "$SERVICE_NAME" | head -15 || true
echo
echo "Done. Logs: journalctl --user -u $SERVICE_NAME -f"
