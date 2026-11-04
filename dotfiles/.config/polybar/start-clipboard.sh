#!/bin/sh
set -eu
mkdir -p "$HOME/.cache/rice-clipboard"
chmod 700 "$HOME/.cache/rice-clipboard"
if [ "${1:-}" = "--restart" ]; then
    /usr/bin/python3 "$HOME/.config/polybar/scripts/clipboard.py" --stop
fi
nohup /usr/bin/python3 "$HOME/.config/polybar/scripts/clipboard.py" --daemon > "$HOME/.cache/rice-clipboard/daemon.log" 2>&1 < /dev/null &
