#!/bin/sh
set -eu
if ! command -v dunst >/dev/null; then
    sudo apt-get install -y dunst
fi
"$HOME/.config/dunst/start.sh"
echo 'Dunst запущен. Разрешены Telegram и важные системные события.'
