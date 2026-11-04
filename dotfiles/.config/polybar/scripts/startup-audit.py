#!/usr/bin/python3
"""Check the Openbox rice in its real graphical session; never restart the WM."""
import importlib.util
import json
import os
import socket
import signal
import subprocess
import sys
import time
from pathlib import Path
import xml.etree.ElementTree as ET

HOME = Path.home()
CACHE = HOME/'.cache/rice'
CACHE.mkdir(parents=True, exist_ok=True)
checks = []

# Explicitly requested, read-only network diagnostic in the desktop session.
network_request = CACHE/'network-diagnostic-request'
if network_request.exists():
    network_request.unlink()
    subprocess.run(['/usr/bin/python3', str(HOME/'.config/polybar/scripts/network-diagnostic.py')], timeout=45)
    sys.exit(0)


def check(name, good, detail=''):
    checks.append({'check': name, 'ok': bool(good), 'detail': detail})


def command(args, timeout=10):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': str(error)})()


def processes():
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == os.getuid():
                args = (entry/'cmdline').read_bytes().split(b'\0')
                found.append([(arg.decode(errors='replace')) for arg in args if arg])
        except OSError:
            pass
    return found


if '--exercise' in sys.argv:
    # The same idempotent initializers used at login, twice to expose duplicates.
    for _ in range(2):
        for relative in ['.config/dunst/start.sh', '.config/polybar/start-clipboard.sh', '.config/rice/start-locker.sh']:
            result = command([str(HOME/relative)])
            check('initializer: '+relative, result.returncode == 0, result.stderr.strip()[:200])
    time.sleep(1)
    pattern = '^/usr/bin/python3 ' + str(HOME/'.config/polybar/scripts/music-widget.py') + '$'
    before = command(['pgrep', '-u', str(os.getuid()), '-f', pattern])
    old_pids = {int(pid) for pid in before.stdout.split()}
    if len(old_pids) == 1:
        try:
            os.kill(next(iter(old_pids)), signal.SIGTERM)
            recovered = False
            for _ in range(30):
                time.sleep(.2)
                after = command(['pgrep', '-u', str(os.getuid()), '-f', pattern])
                new_pids = {int(pid) for pid in after.stdout.split()}
                if len(new_pids) == 1 and not new_pids.intersection(old_pids):
                    recovered = True
                    time.sleep(.8)
                    break
            check('automatic recovery of panel widgets', recovered)
        except ProcessLookupError:
            check('automatic recovery of panel widgets', False, 'process exited before the check')
    else:
        check('automatic recovery of panel widgets', False, 'expected exactly one widget process')

for name, snippet in [
    ('GTK/MPRIS', 'from gi.repository import Gio,GLib; import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk,GdkPixbuf,GdkX11'),
    ('Qt clipboard/switcher', 'from PyQt6.QtWidgets import QApplication; from PyQt6.QtNetwork import QLocalServer'),
]:
    result = command(['/usr/bin/python3', '-c', snippet])
    check(name, result.returncode == 0, result.stderr.strip()[:200])

for relative in ['.config/openbox/autostart', '.config/openbox/environment', '.config/dunst/start.sh', '.config/polybar/restart.sh', '.config/polybar/start-clipboard.sh']:
    result = command(['sh', '-n', str(HOME/relative)])
    check('shell: '+relative, result.returncode == 0, result.stderr.strip()[:200])

try:
    ET.parse(HOME/'.config/openbox/rc.xml')
    check('Openbox XML', True)
except (ET.ParseError, OSError) as error:
    check('Openbox XML', False, str(error))

for relative in ['.config/autostart/lxqt-policykit-agent.desktop', '.local/share/applications/pcmanfm-qt.desktop']:
    result = command(['desktop-file-validate', str(HOME/relative)])
    check('launcher: '+relative, result.returncode == 0, (result.stdout + result.stderr).strip()[:200])

for name in ['audio','calendar','memory','disks','power','notifications']:
    result = command(['rofi', '-theme', str(HOME/f'.config/rofi/{name}.rasi'), '-dump-theme'])
    check('menu: '+name, result.returncode == 0, result.stderr.strip()[:200])

result = command(['/usr/bin/python3', str(HOME/'.config/polybar/scripts/window-switcher.py'), '--check'])
check('Alt+Tab construction and icons', result.returncode == 0, result.stderr.strip()[:200])
for script in ['file-search.py']:
    result = command(['/usr/bin/python3', str(HOME/'.config/polybar/scripts'/script), '--self-test' if script=='microphone.py' else '--check'])
    check('feature startup: '+script, result.returncode == 0, (result.stdout+result.stderr).strip()[:1500] if script=='microphone.py' else result.stderr.strip()[:200])

result = command(['dunstctl','is-paused'])
expected = (HOME/'.config/dunst/do-not-disturb').exists()
check('notification service and saved quiet mode', result.returncode == 0 and (result.stdout.strip() == 'true') == expected)
try:
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(HOME/'.cache/rice-clipboard/clipboard.sock'))
        client.sendall(b'{"ping":true}\n')
        reply = client.recv(4096)
        check('clipboard service responds', json.loads(reply).get('ok',False))
except (OSError, ValueError) as error:
    check('clipboard service responds', False, str(error))

check('screenshot editor installed', Path('/usr/bin/ksnip').is_file())

found = processes()
for name in ['openbox','polybar','dunst','picom','xss-lock','lxqt-policykit-agent']:
    count = sum(bool(args) and Path(args[0]).name == name for args in found)
    check('single running '+name, count == 1, str(count))
for script, argument in [('clipboard.py','--daemon'),('music-panel.py',None),('music-widget.py',None)]:
    count = sum(str(HOME/'.config/polybar/scripts'/script) in args and (argument is None or argument in args) for args in found)
    check('single running '+script, count == 1, str(count))

preview = CACHE/'panel-preview-request'
if preview.exists():
    try:
        import gi
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk
        Gdk.init([])
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        rect = monitor.get_geometry()
        command(['scrot', '-a', f'{rect.x},{rect.y},{rect.width},32', str(CACHE/'panel-preview.png')])
    finally:
        preview.unlink(missing_ok=True)

report = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'passed': sum(c['ok'] for c in checks),
          'total': len(checks), 'checks': checks}
(CACHE/'startup-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(f"Startup audit: {report['passed']}/{report['total']} checks passed", flush=True)
for item in checks:
    if not item['ok']:
        print('FAIL:',item['check'],item['detail'],flush=True)
sys.exit(0 if all(item['ok'] for item in checks) else 1)
