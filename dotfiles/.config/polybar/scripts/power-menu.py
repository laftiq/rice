#!/usr/bin/python3
import subprocess
from pathlib import Path
from popup_position import popup_args

root = Path.home() / '.config/rofi'
subprocess.run(['rofi', '-show', 'power', '-modi', 'power:' + str(root / 'powermenu.sh'),
                '-theme', str(root / 'power.rasi')] + popup_args(190), check=False)
