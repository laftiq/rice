#!/bin/sh
set -eu
# Remove the previous idle locker only after the new one is installed and themed.
if pgrep -u "$(id -u)" -x xscreensaver >/dev/null; then
    xscreensaver-command -exit
fi
xset s 900 900
if ! pgrep -u "$(id -u)" -x xss-lock >/dev/null; then
    mkdir -p "$HOME/.cache/rice"
    nohup xss-lock --transfer-sleep-lock -- "$HOME/.config/rice/lock-screen/lock.sh" > "$HOME/.cache/rice/locker.log" 2>&1 < /dev/null &
fi
