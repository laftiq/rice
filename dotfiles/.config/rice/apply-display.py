#!/usr/bin/python3
"""Use the saved monitor mode only when the connected monitor supports it."""
import json
from pathlib import Path
import re
import subprocess


def parse(query):
    displays = {}
    current = None
    for line in query.splitlines():
        match = re.match(r'^(\S+) connected\b', line)
        if match:
            current = match[1]
            displays[current] = {}
        elif line and not line[0].isspace():
            current = None
        elif current:
            mode = re.match(r'\s+(\d+x\d+)\s+(.+)', line)
            if mode:
                displays[current][mode[1]] = [float(rate) for rate in re.findall(r'\d+(?:\.\d+)?', mode[2])]
    return displays


def main():
    settings = json.loads((Path.home()/'.config/rice/display.json').read_text())
    query = subprocess.run(['xrandr','--query'], capture_output=True, text=True, check=True).stdout
    available = parse(query)
    output, mode, rate = settings['output'], settings['mode'], float(settings['rate'])
    if any(abs(candidate-rate)<0.2 for candidate in available.get(output,{}).get(mode,[])):
        subprocess.run(['xrandr','--output',output,'--mode',mode,'--rate',str(rate)],check=True)
    else:
        print('Saved monitor mode unavailable; keeping the display configuration.')


if __name__ == '__main__':
    main()
