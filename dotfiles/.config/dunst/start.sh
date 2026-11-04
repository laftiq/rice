#!/bin/sh
set -eu
command -v dunst >/dev/null || { echo 'Dunst не установлен' >&2; exit 1; }
mkdir -p "$HOME/.cache/dunst"
pkill -u "$(id -u)" -f '(^|/)lxqt-notificationd([[:space:]]|$)' 2>/dev/null || true
if pgrep -u "$(id -u)" -x dunst >/dev/null; then
    if ! dunstctl reload; then
        echo 'Dunst запущен, но не отвечает через D-Bus.' >&2
        exit 1
    fi
else
    nohup dunst -config "$HOME/.config/dunst/dunstrc" > "$HOME/.cache/dunst/daemon.log" 2>&1 < /dev/null &
fi
attempt=0
until dunstctl is-paused >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 80 ]; then
        cat "$HOME/.cache/dunst/daemon.log" >&2
        echo 'Не удалось подключиться к службе уведомлений.' >&2
        exit 1
    fi
    sleep 0.1
done
if [ -f "$HOME/.config/dunst/do-not-disturb" ]; then
    dunstctl set-paused true
else
    dunstctl set-paused false
fi
if [ "${1:-}" = '--test' ]; then
    dunstify -a rice-test 'Уведомления работают' 'Telegram и важные системные события разрешены.'
fi
