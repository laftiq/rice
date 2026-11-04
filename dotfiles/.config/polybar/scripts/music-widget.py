#!/usr/bin/python3
"""Small centered MPRIS widget matching the Polybar theme."""
import importlib.util
import os
import json
import threading
import subprocess
import re
import ctypes
import ctypes.util
import urllib.request
from pathlib import Path
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GdkX11, GdkPixbuf, GLib, Gio, Pango

spec = importlib.util.spec_from_file_location('music', Path(__file__).with_name('music.py'))
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class Widget(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title('Panel Music')
        self.set_wmclass('panel-music', 'PanelMusic')
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
        self.set_default_size(-1, 32)
        self.name = None
        self.art = None
        self.loading = False
        self.can_seek = False
        self.track_length = 0
        self.track_id = None
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        css = Gtk.CssProvider()
        css.load_from_data(b'window, box {background:#242424;color:#d0d0d0;} label {font:13px "DejaVu Sans Mono";} button {background:transparent; border:0; box-shadow:none; color:#d0d0d0; padding:0 4px; min-height:24px; min-width:18px; border-radius:4px;} button:hover, button:active, button:focus {background:transparent; box-shadow:none; outline:none;} button:disabled {color:#777777;} progressbar trough {min-height:2px; background:transparent; border:0;} progressbar progress {min-height:2px; background:#858585; border:0;}')
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        box = Gtk.Box(spacing=5)
        box.set_margin_start(9)
        box.set_margin_end(9)
        overlay = Gtk.Overlay()
        overlay.add(box)
        self.progress = Gtk.ProgressBar()
        self.progress.set_valign(Gtk.Align.END)
        self.progress.set_halign(Gtk.Align.FILL)
        self.progress.set_margin_start(9)
        self.progress.set_margin_end(9)
        self.seek_target = Gtk.EventBox()
        self.seek_target.set_visible_window(False)
        self.seek_target.set_valign(Gtk.Align.END)
        self.seek_target.set_halign(Gtk.Align.FILL)
        self.seek_target.set_size_request(-1, 7)
        self.seek_target.add(self.progress)
        self.seek_target.connect('button-press-event', self.seek)
        self.seek_target.set_no_show_all(True)
        overlay.add_overlay(self.seek_target)
        self.add(overlay)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect('scroll-event', self.scroll_volume)
        self.cover = Gtk.Image()
        self.cover.set_no_show_all(True)
        box.pack_start(self.cover, False, False, 0)
        title = Gtk.Button()
        self.label = Gtk.Label(label='♪ Яндекс Музыка')
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(30)
        title.add(self.label)
        title.connect('clicked', lambda *_: self.action('Raise'))
        box.pack_start(title, False, False, 0)
        self.buttons = {}
        for symbol, action in [('⏮', 'Previous'), ('▶', 'PlayPause'), ('⏭', 'Next')]:
            button = Gtk.Button()
            icon = Gtk.Image()
            icon.set_from_pixbuf(self.control_icon(action, False))
            button.add(icon)
            button.connect('clicked', lambda _, a=action: self.action(a))
            box.pack_start(button, False, False, 0)
            self.buttons[action] = button
        self.playing = False
        self.connect('size-allocate', lambda *_: self.position())
        self.show_all()
        self.position()
        self.get_screen().connect('monitors-changed', lambda *_: self.position())
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    def position(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        rect = monitor.get_geometry()
        self.move(rect.x + (rect.width - self.get_allocated_width()) // 2, rect.y)

    def control_icon(self, action, playing):
        if action == 'PlayPause' and playing:
            shape = '<path d="M3 3h3v8H3zM8 3h3v8H8z"/>'
        elif action == 'PlayPause':
            shape = '<path d="M4 3l7 4-7 4z"/>'
        else:
            shape = '<path d="M3 3l6 4-6 4zM10 3h1.5v8H10z"/>'
            if action == 'Previous':
                shape = '<g transform="translate(14 0) scale(-1 1)">' + shape + '</g>'
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><g fill="#d0d0d0">' + shape + '</g></svg>'
        loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
        loader.write(svg.encode())
        loader.close()
        return loader.get_pixbuf()

    def action(self, action):
        if action == 'Raise':
            music.open_yandex(self.bus)
            return
        if self.name:
            try:
                music.call(self.bus, self.name, 'org.mpris.MediaPlayer2' if action == 'Raise' else music.PLAYER, action)
            except GLib.Error:
                pass
        self.refresh()

    def seek(self, widget, event):
        if event.button != 1 or not self.name or not self.can_seek or not self.track_id or self.track_length <= 0:
            return False
        width = max(1, widget.get_allocated_width() - 18)
        fraction = max(0., min(1., (event.x - 9) / width))
        position = min(self.track_length - 1, int(fraction * self.track_length))
        name, track_id = self.name, self.track_id
        def work():
            try:
                music.call(self.bus, name, music.PLAYER, 'SetPosition',
                           GLib.Variant('(ox)', (track_id, position)))
                GLib.idle_add(self.refresh)
            except GLib.Error:
                pass
        self.progress.set_fraction(fraction)
        threading.Thread(target=work, daemon=True).start()
        return True

    def scroll_volume(self, widget, event):
        if not self.name:
            return False
        if event.direction == Gdk.ScrollDirection.UP:
            delta = .03
        elif event.direction == Gdk.ScrollDirection.DOWN:
            delta = -.03
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            _, dx, dy = event.get_scroll_deltas()
            delta = -.03 * dy
        else:
            return False
        if not delta:
            return False
        name = self.name
        def adjust():
            try:
                current = music.call(self.bus, name, 'org.freedesktop.DBus.Properties',
                                     'Get', GLib.Variant('(ss)', (music.PLAYER, 'Volume')))[0]
                volume = max(0., min(1., float(current) + delta))
                music.call(self.bus, name, 'org.freedesktop.DBus.Properties', 'Set',
                           GLib.Variant('(ssv)', (music.PLAYER, 'Volume', GLib.Variant('d', volume))))
            except (GLib.Error, ValueError, TypeError):
                pass
        threading.Thread(target=adjust, daemon=True).start()
        return True

    def refresh(self):
        if self.loading:
            return True
        self.loading = True
        def work():
            try:
                found = music.players(self.bus)
                if found:
                    try:
                        found[0][1]['Position'] = music.call(self.bus, found[0][0],
                            'org.freedesktop.DBus.Properties', 'Get',
                            GLib.Variant('(ss)', (music.PLAYER, 'Position')))[0]
                    except GLib.Error:
                        pass
            except GLib.Error:
                found = []
            GLib.idle_add(self.update, found)
        threading.Thread(target=work, daemon=True).start()
        return True

    def update(self, found):
        self.loading = False
        self.name, props = found[0] if found else (None, {})
        meta = props.get('Metadata', {})
        artist = ', '.join(meta.get('xesam:artist', []))
        title = meta.get('xesam:title')
        text = ((artist + ' — ' if artist else '') + title) if title else '♪ Яндекс Музыка'
        self.label.set_text(text)
        length = meta.get('mpris:length', 0)
        self.track_length = length
        self.track_id = meta.get('mpris:trackid')
        self.can_seek = props.get('CanSeek', False)
        self.seek_target.set_visible(bool(title and length > 0))
        position = props.get('Position', 0)
        self.progress.set_visible(bool(title and length > 0))
        self.progress.set_fraction(max(0., min(1., position / length)) if length > 0 else 0.)
        playing = props.get('PlaybackStatus') == 'Playing'
        self.playing = playing
        self.buttons['PlayPause'].get_child().set_from_pixbuf(self.control_icon('PlayPause', playing))
        self.resize(1, 32)
        for action, capability in [('Previous', 'CanGoPrevious'), ('Next', 'CanGoNext'), ('PlayPause', 'CanPause' if playing else 'CanPlay')]:
            self.buttons[action].set_visible(bool(title))
            self.buttons[action].set_sensitive(bool(props.get(capability, False)))
        art = meta.get('mpris:artUrl', '')
        if art != self.art:
            self.art = art
            self.cover.hide()
            if art:
                threading.Thread(target=self.fetch_cover, args=(art,), daemon=True).start()
        return False

    def fetch_cover(self, art):
        try:
            if art.startswith('file://'):
                data = Path(Gio.File.new_for_uri(art).get_path()).read_bytes()
            elif art.startswith(('https://', 'http://')):
                with urllib.request.urlopen(art, timeout=5) as response:
                    data = response.read(5 * 1024 * 1024 + 1)
            else:
                return
            if len(data) > 5 * 1024 * 1024:
                return
            loader = GdkPixbuf.PixbufLoader()
            loader.set_size(22, 22)
            loader.write(data)
            loader.close()
            GLib.idle_add(self.show_cover, art, loader.get_pixbuf())
        except Exception:
            pass

    def show_cover(self, art, pixbuf):
        if art == self.art and pixbuf:
            self.cover.set_from_pixbuf(pixbuf)
            self.cover.show()
        return False


class PanelLogo(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title('Panel Logo')
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
        image = Gtk.Image.new_from_file(str(Path(__file__).parent.parent / 'assets/logo.svg'))
        target = Gtk.EventBox()
        target.add(image)
        target.connect('button-press-event', self.clicked)
        self.add(target)
        self.set_default_size(24, 32)
        self.get_screen().connect('monitors-changed', lambda *_: self.position())
        self.show_all()
        self.position()

    def clicked(self, widget, event):
        if event.button == 1:
            command = ['/usr/bin/python3', str(Path(__file__).with_name('file-search.py'))]
        elif event.button == 3:
            command = ['pcmanfm-qt', str(Path.home())]
        else:
            return False
        log = Path.home()/'.cache/rice/logo-launch.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a') as output:
            print('Logo click:', event.button, flush=True, file=output)
            subprocess.Popen(command, stdout=output, stderr=output)
        return True

    def position(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        rect = monitor.get_geometry()
        self.move(rect.x + 12, rect.y)


class AppIcon(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title('Panel App Icon')
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
        self.image = Gtk.Image()
        self.add(self.image)
        self.set_default_size(22, 32)
        self.active = None
        self.busy = False
        self.show_all()
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        rect = monitor.get_geometry()
        self.move(rect.x + 62, rect.y)
        self.icon_watch = None
        self.watched_active = None
        self.ayu_settings = Path.home()/'.var/app/com.ayugram.desktop/data/AyuGramDesktop/tdata/ayu_settings.json'
        self.ayu_monitor = Gio.File.new_for_path(str(self.ayu_settings.parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.ayu_monitor.connect('changed', self.ayu_settings_changed)
        self.root_watch = self.watch_properties(['-root', '_NET_ACTIVE_WINDOW'])
        self.connect('destroy', self.stop_watches)
        self.refresh()

    def ayu_settings_changed(self, monitor, file, other_file, event):
        if any(item and item.get_basename() == 'ayu_settings.json' for item in (file, other_file)):
            self.active = None
            self.refresh()

    def watch_properties(self, arguments):
        process = subprocess.Popen(['xprop', '-spy', *arguments],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        os.set_blocking(process.stdout.fileno(), False)
        source = GLib.io_add_watch(process.stdout.fileno(),
                                  GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                                  self.property_changed, process)
        return process, source

    def property_changed(self, fd, condition, process):
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            return False
        try:
            data = os.read(fd, 65536)
        except BlockingIOError:
            return True
        if not data:
            return False
        self.active = None
        self.refresh()
        return True

    def stop_watches(self, *_):
        for watch in (self.root_watch, self.icon_watch):
            if watch:
                process, source = watch
                if GLib.MainContext.default().find_source_by_id(source):
                    GLib.source_remove(source)
                process.terminate()
                process.wait(timeout=2)
                process.stdout.close()

    def refresh(self):
        if self.busy:
            return True
        self.busy = True
        threading.Thread(target=self.fetch, daemon=True).start()
        return True

    def fetch(self):
        pixbuf = None
        changed = False
        try:
            result = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True, timeout=1)
            match = re.search(r'0x[0-9a-fA-F]+', result)
            active = match.group() if match else None
            if active != self.active:
                changed = True
                self.active = active
                self.dynamic_icon = False
                if active and active != '0x0':
                    wm_class = subprocess.check_output(
                        ['xprop', '-id', active, 'WM_CLASS'], text=True, timeout=1).lower()
                    self.dynamic_icon = any('ayugram' in name for name in re.findall(r'"([^"]+)"', wm_class))
                    if 'yandexmusic' in wm_class:
                        icon = Path.home()/'.local/share/icons/yandexmusic.png'
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), 18, 18, True)
                    elif 'happ' in re.findall(r'"([^"]+)"', wm_class):
                        icon = Path.home()/'.local/share/icons/happ.png'
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), 18, 18, True)
                    else:
                        result = subprocess.check_output(['xprop', '-id', active, '-notype', '-f', '_NET_WM_ICON', '32c', '_NET_WM_ICON'], text=True, timeout=1)
                        values = [int(n) for n in re.findall(r'\d+', result.partition('=')[2])]
                        candidates = []
                        offset = 0
                        while offset + 2 <= len(values):
                            width, height = values[offset:offset + 2]
                            count = width * height
                            if not width or not height or count > 4000000 or offset + 2 + count > len(values):
                                break
                            candidates.append((width, height, offset + 2))
                            offset += count + 2
                        if candidates:
                            width, height, start = min(candidates, key=lambda item: abs(max(item[:2]) - 22))
                            data = bytearray()
                            for pixel in values[start:start + width * height]:
                                data.extend(((pixel >> 16) & 255, (pixel >> 8) & 255, pixel & 255, (pixel >> 24) & 255))
                            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)
                            pixbuf = pixbuf.scale_simple(18, 18, GdkPixbuf.InterpType.BILINEAR)
                    if self.dynamic_icon:
                        try:
                            name = json.loads(self.ayu_settings.read_text()).get('appIcon', '')
                            # Only use known assets extracted from the installed application.
                            if name in ('chibi', 'chibi2'):
                                icon = Path.home()/'.local/share/icons/ayugram'/f'{name}.png'
                                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), 18, 18, True)
                        except (OSError, ValueError):
                            pass
                    if pixbuf is None and self.dynamic_icon:
                        icon = Path.home()/'.local/share/icons/ayugram.png'
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), 18, 18, True)
        except (subprocess.SubprocessError, OSError, ValueError, GLib.Error):
            pass
        GLib.idle_add(self.update_icon, changed, pixbuf)

    def update_icon(self, changed, pixbuf):
        self.busy = False
        if self.active != self.watched_active:
            if self.icon_watch:
                process, source = self.icon_watch
                if GLib.MainContext.default().find_source_by_id(source):
                    GLib.source_remove(source)
                process.terminate()
                process.wait(timeout=2)
                process.stdout.close()
                self.icon_watch = None
            self.watched_active = self.active
            if self.active and self.active != '0x0':
                self.icon_watch = self.watch_properties(['-id', self.active, '_NET_WM_ICON'])
        if changed:
            if pixbuf:
                self.image.set_from_pixbuf(pixbuf)
            else:
                self.image.set_from_icon_name('application-x-executable-symbolic', Gtk.IconSize.MENU)
        return False


def attach_widgets(application):
    """Make overlays children of Polybar so clicks cannot change their stacking."""
    try:
        tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True, timeout=1)
        parent = None
        for line in tree.splitlines():
            if '"polybar-' in line or '"Polybar"' in line or '"polybar"' in line:
                match = re.search(r'0x[0-9a-fA-F]+', line)
                if match:
                    parent = int(match.group(), 16)
                    break
        if not parent:
            return True
        xlib = ctypes.CDLL(ctypes.util.find_library('X11'))
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XReparentWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
        xlib.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XFlush.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        connection = xlib.XOpenDisplay(None)
        if not connection:
            return True
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        rect = monitor.get_geometry()
        for widget in application.get_windows():
            native = widget.get_window()
            if native:
                x, y = widget.get_position()
                xid = GdkX11.X11Window.get_xid(native)
                xlib.XReparentWindow(connection, xid, parent, x - rect.x, y - rect.y)
                xlib.XMapWindow(connection, xid)
        xlib.XFlush(connection)
        xlib.XCloseDisplay(connection)
        print('Panel widgets attached to Polybar', hex(parent), flush=True)
        return False
    except (OSError, subprocess.SubprocessError, ValueError):
        return True


def reload_requested_panel():
    """Apply a requested bar configuration reload from the desktop session."""
    request = Path.home()/'.cache/rice/polybar-reload-request'
    if request.exists():
        request.unlink()
        with (request.parent/'polybar-reload.log').open('a') as log:
            subprocess.Popen([str(Path.home()/'.config/polybar/restart.sh')],
                             stdout=log, stderr=log, start_new_session=True)
    return True


app = Gtk.Application(application_id='local.laptos.PanelMusicCompact')

def activate(application):
    if application.get_windows():
        return
    window = Widget()
    application.add_window(window)
    application.add_window(PanelLogo())
    application.add_window(AppIcon())
    GLib.timeout_add(250, attach_widgets, application)
    GLib.timeout_add(1000, reload_requested_panel)

app.connect('activate', activate)
app.run(None)
