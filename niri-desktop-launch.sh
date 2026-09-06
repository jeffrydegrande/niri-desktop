#!/usr/bin/env bash
# niri-desktop launcher
# Ensures gtk4-layer-shell is loaded before libwayland-client

LAYERSHELL=$(find /usr -name "libgtk4-layer-shell.so*" 2>/dev/null | head -1)

if [ -z "$LAYERSHELL" ]; then
    echo "Could not find libgtk4-layer-shell.so" >&2
    exit 1
fi

exec env LD_PRELOAD="$LAYERSHELL" /usr/bin/python3 "$(dirname "$0")/niri-desktop.py" "$@"
