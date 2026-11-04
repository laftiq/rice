"""Shared Dunst history parsing and viewed-history watermark."""
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

SEEN = Path.home()/'.cache/rice/notification-history-seen'


def value(item):
    while isinstance(item, dict) and 'data' in item:
        item = item['data']
    return item


def entries(item):
    if isinstance(item, list):
        return [entry for child in item for entry in entries(child)]
    if isinstance(item, dict):
        return [item] if 'summary' in item else entries(item.get('data', []))
    return []


def history():
    try:
        result = subprocess.run(['dunstctl', 'history'], capture_output=True, text=True, timeout=2)
        return entries(json.loads(result.stdout)) if result.returncode == 0 else []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def timestamp(entry):
    try:
        return int(value(entry.get('timestamp', 0)))
    except (ValueError, TypeError):
        return 0


def viewed():
    try:
        boot, stamp = SEEN.read_text().split()
        if boot == Path('/proc/sys/kernel/random/boot_id').read_text().strip():
            return int(stamp)
    except (OSError, ValueError):
        pass
    return 0


def mark_viewed(items):
    stamp = max((timestamp(entry) for entry in items), default=0)
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    SEEN.write_text(f'{boot} {max(viewed(), stamp)}')


def clock(entry):
    stamp = timestamp(entry)
    if not stamp:
        return ''
    epoch = time.time() - time.monotonic() + stamp / 1000000
    moment = datetime.fromtimestamp(epoch)
    return moment.strftime('%H:%M' if moment.date() == datetime.now().date() else '%d.%m %H:%M')
