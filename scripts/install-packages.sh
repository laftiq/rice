#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
packages=$(sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "$root/packages/debian.txt")
if ! command -v apt-get >/dev/null; then
    echo 'This package helper supports Debian/Ubuntu apt only. See docs/PORTABILITY.md.' >&2
    exit 1
fi
case "${1:---dry-run}" in
  --dry-run) exec apt-get --simulate install $packages ;;
  --apply) sudo apt-get update; sudo apt-get install $packages ;;
  *) echo 'Usage: scripts/install-packages.sh [--dry-run|--apply]' >&2; exit 2 ;;
esac
