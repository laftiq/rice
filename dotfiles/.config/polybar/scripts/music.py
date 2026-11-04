#!/usr/bin/python3
"""MPRIS controls and track information for Polybar."""
import sys
import subprocess
from gi.repository import Gio, GLib

PATH = '/org/mpris/MediaPlayer2'
PLAYER = 'org.mpris.MediaPlayer2.Player'
COMMAND = '/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/music.py'


def call(bus, name, interface, method, parameters=None):
    return bus.call_sync(name, PATH, interface, method, parameters, None,
                         Gio.DBusCallFlags.NONE, 700, None).unpack()


def players(bus):
    names = bus.call_sync(
        'org.freedesktop.DBus', '/org/freedesktop/DBus',
        'org.freedesktop.DBus', 'ListNames', None, None,
        Gio.DBusCallFlags.NONE, 700, None).unpack()[0]
    found = []
    for name in names:
        if name.startswith('org.mpris.MediaPlayer2.'):
            try:
                props = call(bus, name, 'org.freedesktop.DBus.Properties',
                             'GetAll', GLib.Variant('(s)', (PLAYER,)))[0]
                found.append((name, props))
            except GLib.Error:
                pass
    return sorted(found, key=lambda p: (
        p[1].get('PlaybackStatus') != 'Playing',
        'yandex' not in p[0].lower(), p[0]))


def open_yandex(bus=None):
    if bus is not None:
        try:
            for name, _ in players(bus):
                if 'yandex' in name.lower():
                    try:
                        call(bus, name, 'org.mpris.MediaPlayer2', 'Raise')
                        return
                    except GLib.Error:
                        break
        except GLib.Error:
            pass
    subprocess.Popen(['/usr/bin/yandexmusic'], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def placeholder():
    return button('♪ Яндекс Музыка', 'OpenYandex')


def button(symbol, action, enabled=True):
    if not enabled:
        return '%{F#777777}' + symbol + '%{F-}'
    return '%{A1:' + COMMAND + ' ' + action + ':}' + symbol + '%{A}'


def render(name, props):
    metadata = props.get('Metadata', {})
    title = metadata.get('xesam:title', 'Музыка')
    artist = ', '.join(metadata.get('xesam:artist', []))
    track = (artist + ' — ' if artist else '') + title
    track = ' '.join(track.split()).replace('%', '％')
    if len(track) > 36:
        track = track[:35] + '…'
    playing = props.get('PlaybackStatus') == 'Playing'
    controls = '  '.join([
        button('⏮', 'Previous', props.get('CanGoPrevious', False)),
        button('⏸' if playing else '▶', 'PlayPause',
               props.get('CanPause' if playing else 'CanPlay', False)),
        button('⏭', 'Next', props.get('CanGoNext', False))])
    return button('♪ ' + track, 'OpenYandex') + '  ' + controls


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if action == 'OpenYandex':
            open_yandex(bus)
            return
        available = players(bus)
        if not available:
            if not action:
                print(placeholder())
            return
        name, props = available[0]
        if action in ('Previous', 'PlayPause', 'Next', 'Raise'):
            call(bus, name, 'org.mpris.MediaPlayer2' if action == 'Raise' else PLAYER, action)
        elif not action:
            print(render(name, props))
    except GLib.Error:
        if action == 'OpenYandex':
            open_yandex()
        elif not action:
            print(placeholder())


if __name__ == '__main__':
    main()
