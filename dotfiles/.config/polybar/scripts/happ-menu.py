#!/usr/bin/python3
"""Show Happ's native DBusMenu server actions using the rice's Rofi popup."""
import fcntl
import os
from pathlib import Path
import subprocess
import time

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from popup_position import popup_args

HOME = Path.home()
MENU_IFACE = 'com.canonical.dbusmenu'
WATCHER = 'org.kde.StatusNotifierWatcher'


def ensure_watcher(bus):
    owned = call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                 'org.freedesktop.DBus', 'NameHasOwner',
                 GLib.Variant('(s)', (WATCHER,)))[0]
    if owned:
        return
    log = HOME / '.cache/rice/happ-tray-bridge.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a') as output:
        subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('happ-tray-bridge.py'))],
                         stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                         start_new_session=True)
    for _ in range(20):
        time.sleep(.1)
        if call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'NameHasOwner',
                GLib.Variant('(s)', (WATCHER,)))[0]:
            return
    raise RuntimeError('Не запустился обработчик меню Happ. Подробности: '
                       '~/.cache/rice/happ-tray-bridge.log')


def call(bus, service, path, interface, method, args=None):
    return bus.call_sync(service, path, interface, method, args, None,
                         Gio.DBusCallFlags.NONE, 1800, None).unpack()


def happ_menu(bus):
    names = call(bus, 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                 'org.freedesktop.DBus', 'ListNames')[0]
    # Qt's StatusNotifierItem exports the native tray menu, including the
    # live server actions. Never choose a menu belonging to another app.
    candidates = [(name, '/StatusNotifierItem') for name in names
                  if 'StatusNotifierItem' in name]
    try:
        registered = call(bus, WATCHER, '/StatusNotifierWatcher',
                          'org.freedesktop.DBus.Properties', 'Get',
                          GLib.Variant('(ss)', (WATCHER, 'RegisteredStatusNotifierItems')))[0]
        for item in registered:
            service, _, suffix = item.partition('/')
            candidate = (service, '/' + suffix if suffix else '/StatusNotifierItem')
            if candidate not in candidates:
                candidates.append(candidate)
    except GLib.Error:
        pass
    for service, item_path in candidates:
        try:
            props = call(bus, service, item_path,
                         'org.freedesktop.DBus.Properties', 'GetAll',
                         GLib.Variant('(s)', ('org.kde.StatusNotifierItem',)))[0]
            identity = ' '.join(str(props.get(k, '')) for k in ('Id', 'Title'))
            if 'happ' not in identity.casefold():
                continue
            path = str(props.get('Menu', '/MenuBar'))
            if not path.startswith('/'):
                continue
            return service, path
        except GLib.Error:
            continue
    raise RuntimeError('Обработчик трея запущен, но Happ ещё не опубликовал меню. '
                       'Полностью заверши Happ и запусти снова, затем нажми ПКМ на VPN. '
                       'При завершении Happ VPN отключится.')


def server_actions(node, parents=()):
    if isinstance(node, GLib.Variant):
        node = node.unpack()
    item_id, props, children = node
    if not props.get('visible', True):
        return []
    label = str(props.get('label', '')).replace('_', '').replace('\n', ' ').strip()
    path = parents + ((label,) if label else ())
    result = []
    # Server entries are checkable leaf actions in a subscription submenu.
    # Top-level connect/proxy toggles are deliberately excluded.
    if (not children and props.get('enabled', True)
            and props.get('toggle-type') in ('radio', 'checkmark')
            and (parents or props.get('toggle-type') == 'radio')):
        result.append((item_id, ' / '.join(path), props.get('toggle-state') == 1))
    for child in children:
        result.extend(server_actions(child, path))
    return result


def choose(options, anchor):
    rows = [('● ' if active else '  ') + label for _, label, active in options]
    rows.append('Открыть Happ…')
    selected = next((i for i, row in enumerate(options) if row[2]), 0)
    menu = subprocess.run([
        'rofi', '-dmenu', '-i', '-no-custom', '-format', 'i',
        '-selected-row', str(selected), '-p', 'Сервер Happ',
        '-theme', str(HOME / '.config/rofi/audio.rasi'),
        '-theme-str', 'listview { lines: 10; }',
    ] + anchor, input='\n'.join(rows), text=True, capture_output=True)
    if menu.returncode:
        return None
    try:
        index = int(menu.stdout.strip())
    except ValueError:
        return None
    return index if 0 <= index <= len(options) else None


def main():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime / 'polybar-happ-menu.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        anchor = popup_args(420)
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            ensure_watcher(bus)
            for attempt in range(15):
                try:
                    service, path = happ_menu(bus)
                    break
                except RuntimeError:
                    if attempt == 14:
                        raise
                    time.sleep(.15)
            call(bus, service, path, MENU_IFACE, 'AboutToShow', GLib.Variant('(i)', (0,)))
            _, layout = call(bus, service, path, MENU_IFACE, 'GetLayout',
                             GLib.Variant('(iias)', (0, -1, [])))
            # Refresh lazy subscription submenus before reading their actions.
            def refresh(node):
                if isinstance(node, GLib.Variant):
                    node = node.unpack()
                ident, props, children = node
                if ident and props.get('children-display') == 'submenu':
                    call(bus, service, path, MENU_IFACE, 'AboutToShow',
                         GLib.Variant('(i)', (ident,)))
                for child in children:
                    refresh(child)
            refresh(layout)
            _, layout = call(bus, service, path, MENU_IFACE, 'GetLayout',
                             GLib.Variant('(iias)', (0, -1, [])))
            options = server_actions(layout)
            if not options:
                raise RuntimeError('В меню Happ не найден список серверов. '
                                   'Выбор через Rofi для этой версии пока недоступен.')
            selected = choose(options, anchor)
            if selected is None:
                return
            if selected == len(options):
                subprocess.Popen(['/opt/happ/bin/Happ'], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            # Dispatch the original QAction. Happ owns persistence/reconnect.
            call(bus, service, path, MENU_IFACE, 'Event', GLib.Variant(
                '(isvu)', (options[selected][0], 'clicked', GLib.Variant('i', 0),
                           int(time.time() * 1000) & 0xffffffff)))
        except (GLib.Error, RuntimeError) as error:
            subprocess.run(['rofi', '-e', str(error), '-theme',
                            str(HOME / '.config/rofi/audio.rasi')] + anchor,
                           check=False)


if __name__ == '__main__':
    main()
