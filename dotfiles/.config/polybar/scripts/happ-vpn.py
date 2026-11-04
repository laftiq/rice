#!/usr/bin/python3
"""Polybar control for Happ's native deep links and its TUN interface."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))


def connected():
    # Happ uses happ-xray / happ-tun. An existing TUN can have operstate
    # 'unknown', so use the kernel's IFF_UP flag rather than operstate.
    for interface in Path('/sys/class/net').glob('happ*'):
        try:
            if int((interface / 'flags').read_text().strip(), 16) & 1:
                return True
        except (OSError, ValueError):
            continue
    return False


def status():
    active = connected()
    color = '#D0D0D0' if active else '#777777'
    print(f'%{{F{color}}}VPN%{{F-}}')


def launch(action):
    if action == 'open':
        # Keep the existing Polybar command so the new menu works immediately,
        # without requiring a bar restart after this script update.
        os.execv('/usr/bin/python3', ['python3', str(Path(__file__).with_name('happ-menu.py'))])
    # Serialize clicks: two quick presses must not undo one another.
    with (RUNTIME / 'polybar-happ.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        lock.seek(0)
        try:
            previous = float(lock.read() or '0')
        except ValueError:
            previous = 0
        now = time.monotonic()
        if action == 'toggle' and 0 <= now - previous < 2:
            return
        if action == 'toggle':
            lock.seek(0)
            lock.truncate()
            lock.write(str(now))
            lock.flush()
        # Native URL handling preserves Happ's selected server and routing.
        # With no URL a second invocation raises the existing Happ window.
        args = ['/opt/happ/bin/Happ']
        if action == 'toggle':
            args.append('happ://toggle')
        try:
            subprocess.Popen(args, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            subprocess.run(['notify-send', 'Happ', 'Не удалось запустить Happ'],
                           check=False)
            raise


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if action == 'status':
        status()
    elif action in ('toggle', 'open'):
        launch(action)
    else:
        raise SystemExit('Usage: happ-vpn.py [status|toggle|open]')
