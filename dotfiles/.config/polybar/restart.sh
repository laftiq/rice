#!/bin/sh
set -eu
pkill -u "$(id -u)" -x polybar || true
attempt=0
while pgrep -u "$(id -u)" -x polybar >/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo 'Polybar не завершилась. Повторный запуск отменён.' >&2
        exit 1
    fi
    sleep 0.1
done
nohup polybar --reload --config="$HOME/.config/polybar/config.ini" example > /tmp/polybar.log 2>&1 < /dev/null &
