#!/bin/sh
set -eu
mkdir -p "$HOME/.cache/rice"
nohup /usr/bin/python3 "$HOME/.config/rice/app-layouts.py" >> "$HOME/.cache/rice/app-layouts.log" 2>&1 < /dev/null &
