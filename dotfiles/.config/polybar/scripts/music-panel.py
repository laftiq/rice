#!/usr/bin/python3
"""Supervise the embedded panel widgets throughout the desktop session."""
import ctypes
import importlib.util
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).parent
cache = Path.home()/'.cache/rice'
cache.mkdir(parents=True, exist_ok=True)
reconfigure = cache/'openbox-reconfigure-needed'
if reconfigure.exists():
    result = subprocess.run(['openbox', '--reconfigure'], capture_output=True, text=True, timeout=5)
    reconfigure.with_suffix('.log').write_text(str(result.returncode)+'\n'+result.stderr)
    if result.returncode == 0:
        reconfigure.unlink(missing_ok=True)

widget_path = root/'music-widget.py'
spec = importlib.util.spec_from_file_location('music', root/'music.py')
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)
running = True
widget = None


def stop(*_):
    global running
    running = False


def child_setup():
    # Do not leave an orphan overlay holding the application ID after bar reload.
    parent = os.getppid()
    ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0)
    if os.getppid() != parent:
        os._exit(0)


def retire():
    if widget is not None and widget.poll() is None:
        widget.terminate()
        try:
            widget.wait(timeout=3)
        except subprocess.TimeoutExpired:
            widget.kill()
            widget.wait()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
subprocess.run(['pkill', '-u', str(os.getuid()), '-f', '^/usr/bin/python3 '+str(widget_path)+'$'], check=False)
try:
    with (cache/'music-widget.log').open('a') as log:
        mtime = 0
        retry_at = 0
        while running:
            current = widget_path.stat().st_mtime_ns
            if current != mtime:
                retire()
                mtime = current
                retry_at = 0
            if (widget is None or widget.poll() is not None) and time.monotonic() >= retry_at:
                widget = subprocess.Popen(['/usr/bin/python3', str(widget_path)], stdout=log,
                                          stderr=log, preexec_fn=child_setup)
                retry_at = time.monotonic()+3
            if widget is not None and widget.poll() is None:
                print('%{O330}', flush=True)
            else:
                music.main()
                import sys
                sys.stdout.flush()
            # Run an explicit, one-shot audit only when requested.
            request = cache/'startup-audit-request'
            if request.exists():
                exercise = request.read_text().strip() == 'exercise'
                request.unlink()
                command = ['/usr/bin/python3', str(root/'startup-audit.py')]
                if exercise:
                    command.append('--exercise')
                subprocess.Popen(command, stdout=log, stderr=log)
            time.sleep(.5)
except BrokenPipeError:
    pass
finally:
    retire()
