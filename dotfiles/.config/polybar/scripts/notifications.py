#!/usr/bin/python3
"""Event-driven notification status with serialized, immediate toggles."""
import fcntl
import subprocess
import sys
from pathlib import Path
from gi.repository import Gio, GLib
import notification_data as data

state = Path.home() / '.config/dunst/do-not-disturb'
NAME = 'org.freedesktop.Notifications'
PATH = '/org/freedesktop/Notifications'
IFACE = 'org.dunstproject.cmd0'
PROPS = 'org.freedesktop.DBus.Properties'


def call(interface, method, args=None):
    return bus.call_sync(NAME, PATH, interface, method, args, None,
                         Gio.DBusCallFlags.NONE, 1000, None).unpack()


def paused():
    return call(PROPS, 'Get', GLib.Variant('(ss)', (IFACE, 'paused')))[0]


def set_paused(value):
    call(PROPS, 'Set', GLib.Variant('(ssv)', (IFACE, 'paused', GLib.Variant('b', value))))


previous = None

def render(*_):
    global previous
    try:
        muted = paused()
        label = '%{F#777777}≡%{F-}' if muted else '%{F#D0D0D0}≡%{F-}'
        watermark = data.viewed()
        count = sum(data.timestamp(entry) > watermark for entry in data.history())
        if count:
            label += ' ' + str(count)
    except GLib.Error:
        label = '%{F#777777}—%{F-}'
    if label != previous:
        print(label, flush=True)
        previous = label
    return True


try:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if len(sys.argv) > 1 and sys.argv[1] == 'toggle':
        lock_path = Path.home() / '.cache/rice/notifications.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = paused()
            if current:
                call(IFACE, 'NotificationCloseAll')
            set_paused(not current)
            if current:
                state.unlink(missing_ok=True)
            else:
                state.touch()
    else:
        subprocess.run(['dunstctl', 'reload'], capture_output=True, timeout=3)
        if state.exists():
            set_paused(True)
        bus.signal_subscribe(NAME, PROPS, 'PropertiesChanged', PATH, None,
                             Gio.DBusSignalFlags.NONE, render)
        bus.signal_subscribe(NAME, IFACE, None, PATH, None,
                             Gio.DBusSignalFlags.NONE, render)
        render()
        GLib.timeout_add_seconds(1, render)  # Reconnect/status fallback only.
        GLib.MainLoop().run()
except (GLib.Error, OSError, subprocess.TimeoutExpired):
    raise SystemExit(1)
