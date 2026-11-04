#!/bin/sh
set -eu
pgrep -u "$(id -u)" -x i3lock >/dev/null && exit 0
/usr/bin/python3 "$HOME/.config/rice/lock-screen/render.py"
locker="$HOME/.local/libexec/i3lock"
if [ ! -x "$locker" ]; then locker=$(command -v i3lock); fi
exec "$locker" --nofork --ignore-empty-password --show-keyboard-layout --color=000000 --image="$HOME/.config/rice/lock-screen/background.png"
