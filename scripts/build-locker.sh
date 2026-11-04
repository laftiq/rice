#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/.build/i3lock"
mkdir -p "$root/.build"
if [ ! -f "$build/build.ninja" ]; then
    meson setup "$build" "$root/vendor/i3lock" --prefix=/usr --sysconfdir=/etc
fi
ninja -C "$build"
if [ -n "${1:-}" ]; then
    mkdir -p "$(dirname -- "$1")"
    install -m 755 "$build/i3lock" "$1"
fi
printf 'Built locker: %s\n' "$build/i3lock"
