#!/usr/bin/python3
"""Compact X11 Alt+Tab switcher with mouse selection."""
import ctypes as C
import ctypes.util
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QSize, QLockFile
from PyQt6.QtGui import QIcon, QImage, QPixmap, QCursor
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QLabel, QScrollArea, QStyle


class X11:
    def __init__(self):
        self.lib = C.CDLL(ctypes.util.find_library('X11'))
        signatures = {
            'XOpenDisplay': ([C.c_char_p], C.c_void_p),
            'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
            'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
            'XGetWindowProperty': ([C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long, C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int), C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.POINTER(C.c_ubyte))], C.c_int),
            'XFree': ([C.c_void_p], C.c_int),
            'XQueryKeymap': ([C.c_void_p, C.c_void_p], C.c_int),
            'XKeysymToKeycode': ([C.c_void_p, C.c_ulong], C.c_ubyte),
            'XSendEvent': ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.c_void_p], C.c_int),
            'XFlush': ([C.c_void_p], C.c_int),
            'XCloseDisplay': ([C.c_void_p], C.c_int),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('X11 unavailable')
        self.error_handler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)(lambda *_: 0)
        self.lib.XSetErrorHandler.argtypes = [C.c_void_p]
        self.lib.XSetErrorHandler(self.error_handler)
        self.root = self.lib.XDefaultRootWindow(self.display)
        self.atoms = {}
        self.alt_keys = [self.lib.XKeysymToKeycode(self.display, key) for key in (0xffe9, 0xffea)]

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.lib.XInternAtom(self.display, name.encode(), False)
        return self.atoms[name]

    def prop(self, window, name):
        actual, count, remaining = C.c_ulong(), C.c_ulong(), C.c_ulong()
        fmt = C.c_int()
        data = C.POINTER(C.c_ubyte)()
        status = self.lib.XGetWindowProperty(self.display, window, self.atom(name), 0, 1048576, False, 0,
            C.byref(actual), C.byref(fmt), C.byref(count), C.byref(remaining), C.byref(data))
        if status or not data:
            return []
        try:
            if fmt.value == 8:
                return C.string_at(data, count.value).decode('utf-8', errors='replace').rstrip('\0')
            if fmt.value == 32:
                return list(C.cast(data, C.POINTER(C.c_ulong))[:count.value])
            return []
        finally:
            self.lib.XFree(data)

    def windows(self):
        active = self.prop(self.root, '_NET_ACTIVE_WINDOW')
        desktop = self.prop(self.root, '_NET_CURRENT_DESKTOP')
        result = []
        for wid in reversed(self.prop(self.root, '_NET_CLIENT_LIST_STACKING')):
            state = self.prop(wid, '_NET_WM_STATE')
            types = self.prop(wid, '_NET_WM_WINDOW_TYPE')
            if self.atom('_NET_WM_STATE_SKIP_TASKBAR') in state:
                continue
            if any(self.atom('_NET_WM_WINDOW_TYPE_' + kind) in types for kind in ('DOCK', 'DESKTOP', 'TOOLTIP', 'NOTIFICATION')):
                continue
            where = self.prop(wid, '_NET_WM_DESKTOP')
            if desktop and where and where[0] not in (desktop[0], 0xffffffff):
                continue
            title = self.prop(wid, '_NET_WM_NAME') or self.prop(wid, 'WM_NAME')
            if isinstance(title, str) and title:
                result.append((wid, title))
        if active:
            result.sort(key=lambda item: item[0] != active[0])
        return result

    def icon(self, wid):
        wm_class = self.prop(wid, 'WM_CLASS')
        if isinstance(wm_class, str):
            classes = wm_class.lower().split('\0')
            overrides = {'ayugram': 'ayugram.png', 'com.ayugram.desktop': 'ayugram.png', 'ayugram-desktop': 'ayugram.png', 'happ': 'happ.png', 'yandexmusic': 'yandexmusic.png'}
            for name in classes:
                if name in overrides:
                    path = Path.home()/'.local/share/icons'/overrides[name]
                    if path.is_file():
                        icon = QIcon(str(path))
                        if not icon.isNull():
                            return icon
        values = self.prop(wid, '_NET_WM_ICON')
        offset, candidates = 0, []
        while offset + 2 <= len(values):
            w, h = values[offset:offset+2]
            end = offset + 2 + w*h
            if not w or not h or w*h > 4000000 or end > len(values):
                break
            candidates.append((w, h, offset+2))
            offset = end
        if not candidates:
            return QIcon.fromTheme('application-x-executable')
        w, h, start = min(candidates, key=lambda item: abs(max(item[:2])-32))
        data = b''.join((int(pixel) & 0xffffffff).to_bytes(4, sys.byteorder) for pixel in values[start:start+w*h])
        image = QImage(data, w, h, w*4, QImage.Format.Format_ARGB32).copy()
        return QIcon(QPixmap.fromImage(image))

    def alt_held(self):
        keys = C.create_string_buffer(32)
        self.lib.XQueryKeymap(self.display, keys)
        return any(code and (keys.raw[code//8] & (1 << (code % 8))) for code in self.alt_keys)

    def activate(self, wid):
        class Data(C.Union):
            _fields_ = [('l', C.c_long*5), ('b', C.c_char*20)]
        class Message(C.Structure):
            _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                        ('display', C.c_void_p), ('window', C.c_ulong), ('message_type', C.c_ulong),
                        ('format', C.c_int), ('data', Data)]
        event = C.create_string_buffer(C.sizeof(C.c_long)*24)
        message = Message.from_buffer(event)
        message.type, message.send_event = 33, True
        message.display, message.window = self.display, wid
        message.message_type, message.format = self.atom('_NET_ACTIVE_WINDOW'), 32
        message.data.l[0], message.data.l[1] = 2, 0
        self.lib.XSendEvent(self.display, self.root, False, (1 << 20) | (1 << 19), event)
        self.lib.XFlush(self.display)


class Switcher(QWidget):
    def __init__(self, x11, items, reverse):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.x11, self.items = x11, items
        self.done = False
        self.index = (-1 if reverse else 1) % len(items)
        self.setWindowTitle('Window Switcher')
        self.setStyleSheet('''
            QWidget#switcher { background:#242424; border:1px solid #3c3c3c; }
            QToolButton { background:transparent; border:0; border-bottom:2px solid transparent; padding:9px; border-radius:0px; }
            QToolButton:hover { background:#2c2c2c; }
            QToolButton[selected="true"] { background:#303030; border-bottom:2px solid #b8b8b8; }
            QLabel { color:#d0d0d0; background:transparent; border:0; font:bold 11px "DejaVu Sans Mono"; }
        ''')
        self.setObjectName('switcher')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.buttons = []
        for index, (wid, title) in enumerate(items):
            button = QToolButton()
            button.setIcon(x11.icon(wid))
            button.setIconSize(QSize(32, 32))
            button.setFixedSize(58, 56)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, i=index: self.choose(i))
            row.addWidget(button)
            self.buttons.append(button)
        strip = QWidget()
        row.setContentsMargins(0, 0, 0, 0)
        strip.setLayout(row)
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        content_width = min(max(190, len(items)*62-4), min(720, screen.availableGeometry().width()-80))
        scroll = QScrollArea()
        scroll.setWidget(strip)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background:transparent; border:0; }')
        scroll.setFixedSize(content_width, 56)
        strip.adjustSize()
        self.scroll = scroll
        layout.addWidget(scroll)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedWidth(content_width)
        layout.addWidget(self.label)
        self.update_selection()
        self.adjustSize()
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        rect = screen.availableGeometry()
        self.move(rect.center().x()-self.width()//2, rect.center().y()-self.height()//2)
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.check_alt)
        QTimer.singleShot(100, self.timer.start)

    def update_selection(self):
        for index, button in enumerate(self.buttons):
            button.setProperty('selected', index == self.index)
            button.style().unpolish(button)
            button.style().polish(button)
        self.scroll.ensureWidgetVisible(self.buttons[self.index], 8, 0)
        self.label.setText(self.label.fontMetrics().elidedText(self.items[self.index][1], Qt.TextElideMode.ElideRight, self.label.width()))

    def choose(self, index=None):
        if self.done:
            return
        self.done = True
        self.timer.stop()
        wid = self.items[self.index if index is None else index][0]
        self.hide()
        self.x11.activate(wid)
        app.quit()

    def check_alt(self):
        if not self.x11.alt_held():
            self.choose()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.done = True
            app.quit()
        elif event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Left, Qt.Key.Key_Right):
            backward = event.key() in (Qt.Key.Key_Backtab, Qt.Key.Key_Left) or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.index = (self.index + (-1 if backward else 1)) % len(self.items)
            self.update_selection()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choose()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
            self.choose()
        else:
            super().keyReleaseEvent(event)


app = QApplication(sys.argv)
Path.home().joinpath('.cache/rice').mkdir(parents=True, exist_ok=True)
lock = QLockFile(str(Path.home()/'.cache/rice/window-switcher.lock'))
if not lock.tryLock(0):
    sys.exit(0)
if '--preview' in sys.argv:
    class Preview:
        def icon(self, wid):
            names = ['firefox-esr', 'utilities-terminal', 'system-file-manager', 'audio-x-generic']
            result = QIcon.fromTheme(names[(wid-1) % len(names)])
            return result if not result.isNull() else app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    sample = [(1, 'Firefox'), (2, 'Терминал'), (3, 'Домашняя папка'), (4, 'Яндекс Музыка')]
    window = Switcher(Preview(), sample, False)
    window.show()
    app.processEvents()
    window.grab().save(sys.argv[sys.argv.index('--preview')+1])
    lock.unlock()
    sys.exit(0)
x11 = X11()
items = x11.windows()
if items:
    window = Switcher(x11, items, '--reverse' in sys.argv)
    if '--check' in sys.argv:
        print('Window switcher initialized; windows:', len(items))
    else:
        window.show()
        window.activateWindow()
        window.setFocus()
        app.exec()
x11.lib.XCloseDisplay(x11.display)
lock.unlock()
