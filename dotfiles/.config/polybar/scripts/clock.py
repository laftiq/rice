#!/usr/bin/python3
from datetime import datetime
from pathlib import Path
import sys

state = Path.home()/'.cache/polybar/date-expanded'
if len(sys.argv) > 1 and sys.argv[1] == 'toggle':
    state.parent.mkdir(parents=True, exist_ok=True)
    if state.exists():
        state.unlink()
    else:
        state.touch()
else:
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S' if state.exists() else '%H:%M'))
