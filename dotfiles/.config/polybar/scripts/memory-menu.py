#!/usr/bin/python3
"""Read-only memory overview; refresh on request, never signal processes."""
import html
import subprocess
from popup_position import popup_args
from pathlib import Path


def snapshot(proc=Path('/proc')):
    memory = {}
    for line in (proc / 'meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.split()[0])
    total = memory['MemTotal']
    used = total - memory.get('MemAvailable', memory.get('MemFree', 0))
    processes = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = {}
            for line in (entry / 'status').read_text().splitlines():
                key, value = line.split(':', 1)
                fields[key] = value.strip()
            rss = int(fields.get('VmRSS', '0').split()[0])
            if rss:
                processes.append((rss, int(entry.name), fields.get('Name', '?')))
        except (OSError, ValueError, ProcessLookupError):
            continue
    return total, used, sorted(processes, reverse=True)[:7]


def size(kib):
    return f'{kib / 1048576:.1f} GiB' if kib >= 1048576 else f'{kib / 1024:.0f} MiB'


def render(total, used, processes):
    percentage = round(100 * used / total)
    filled = min(24, max(0, round(24 * used / total)))
    summary = (f'<span foreground="#D0D0D0" size="large"><b>{size(used)}</b></span>'
               f' <span foreground="#777777">/ {size(total)}   ·   {percentage}%</span>\n'
               f'<span foreground="#B8B8B8">{"━" * filled}</span>'
               f'<span foreground="#454545">{"━" * (24-filled)}</span>')
    rows = []
    for rss, pid, name in processes:
        safe_name = html.escape(f'{name[:18]:<18}')
        text = (f'<span foreground="#D0D0D0">{safe_name}</span>'
                f' <span foreground="#B8B8B8"><b>{size(rss):>8}</b></span>'
                f' <span foreground="#777777">{100*rss/total:4.1f}%</span>')
        rows.append(text + '\0nonselectable\x1ftrue')
    rows.append('<span foreground="#B8B8B8">↻  Обновить</span>')
    return summary, rows


def main():
    while True:
        summary, rows = render(*snapshot())
        result = subprocess.run([
            'rofi', '-dmenu', '-no-custom', '-no-sort', '-markup-rows',
            '-format', 'i', '-selected-row', str(len(rows)-1),
            '-mesg', summary, '-theme', str(Path.home()/'.config/rofi/memory.rasi')
        ] + popup_args(340), input='\n'.join(rows), text=True, capture_output=True)
        if result.returncode or result.stdout.strip() != str(len(rows)-1):
            break


if __name__ == '__main__':
    main()
