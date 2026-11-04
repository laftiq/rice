#!/usr/bin/python3
"""One-shot recovery in the actual desktop session."""
import subprocess
from pathlib import Path

marker = Path.home()/'.cache/rice/panel-repair-needed'
if marker.exists():
    report = []
    subprocess.run(['pkill', '-u', str(__import__('os').getuid()), '-x', 'rofi'], capture_output=True)
    result = subprocess.run(['openbox', '--reconfigure'], capture_output=True, text=True, timeout=5)
    report.append('Openbox reload: ' + str(result.returncode) + '\n' + result.stderr)
    for name in ['audio', 'calendar', 'memory', 'disks', 'power', 'notifications']:
        theme = Path.home()/('.config/rofi/' + name + '.rasi')
        result = subprocess.run(['rofi', '-theme', str(theme), '-dump-theme'], capture_output=True, text=True, timeout=5)
        report.append(name + ': ' + str(result.returncode) + '\n' + result.stderr)
    result = subprocess.run(['rofi', '-dmenu', '-auto-select', '-no-custom', '-kb-custom-1', 'F2', '-kb-custom-2', 'F3', '-theme', str(Path.home()/'.config/rofi/calendar.rasi')], input='check\n', capture_output=True, text=True, timeout=5)
    report.append('Calendar bindings: ' + str(result.returncode) + '\n' + result.stderr)
    (marker.parent/'panel-repair.log').write_text('\n'.join(report))
    marker.unlink(missing_ok=True)
