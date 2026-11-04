#!/usr/bin/python3
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

DIRECTORY = Path.home()/'.cache/rice-clipboard'
HISTORY = DIRECTORY/'history.json'
MEDIA = DIRECTORY/'media.json'
IMAGES = DIRECTORY/'images'
SOCKET = DIRECTORY/'clipboard.sock'
TABS = ('text', 'files', 'photos')


def load(path=HISTORY):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False)
    temporary.replace(path)


def image_path(filename):
    # Only cache-owned PNG files may be read or removed by media commands.
    if not isinstance(filename, str) or len(filename) != 68 or not filename.endswith('.png'):
        raise ValueError('Invalid image name')
    int(filename[:-4], 16)
    return IMAGES/filename


def prune(media):
    existing = []
    photo_count = 0
    file_count = 0
    image_bytes = 0
    for item in media:
        if item.get('type') == 'photos':
            try:
                path = image_path(item['image'])
                size = path.stat().st_size
            except (OSError, ValueError, KeyError):
                continue
            if photo_count >= 40 or image_bytes + size > 250*1024*1024:
                continue
            photo_count += 1
            image_bytes += size
        elif item.get('type') == 'files':
            if file_count >= 80:
                continue
            file_count += 1
        else:
            continue
        existing.append(item)
    retained = {item['image'] for item in existing if item['type'] == 'photos'}
    for path in IMAGES.glob('*.png'):
        if path.name not in retained:
            image_path(path.name).unlink(missing_ok=True)
    return existing


def daemon():
    from PyQt6.QtCore import QBuffer, QIODevice, QLockFile, QMimeData, QUrl
    from PyQt6.QtGui import QImage
    from PyQt6.QtNetwork import QLocalServer
    from PyQt6.QtWidgets import QApplication
    DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    DIRECTORY.chmod(0o700)
    IMAGES.mkdir(mode=0o700, exist_ok=True)
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(DIRECTORY/'daemon.lock'))
    if not lock.tryLock(0):
        return
    history = load()
    media = prune(load(MEDIA))
    clipboard = app.clipboard()

    def save_media(item=None):
        nonlocal media
        if item:
            media = [item] + [old for old in media if old != item]
        media = prune(media)
        save(MEDIA, media)

    def capture():
        mime = clipboard.mimeData()
        if mime is None or mime.hasFormat('application/x-keepassxc'):
            return
        if mime.hasUrls():
            urls = [url.toString() for url in mime.urls() if url.isLocalFile()]
            if urls:
                save_media({'type': 'files', 'urls': urls})
                return
        if mime.hasImage():
            image = clipboard.image()
            if image.isNull():
                return
            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not image.save(buffer, 'PNG'):
                return
            data = bytes(buffer.data())
            if len(data) > 250*1024*1024:
                return
            filename = hashlib.sha256(data).hexdigest()+'.png'
            path = image_path(filename)
            if not path.exists():
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
            save_media({'type': 'photos', 'image': filename,
                        'width': image.width(), 'height': image.height()})
            return
        text = clipboard.text()
        if text and len(text) <= 100000:
            history[:] = [text] + [old for old in history if old != text][:79]
            save(HISTORY, history)

    server = QLocalServer()
    QLocalServer.removeServer(str(SOCKET))
    if not server.listen(str(SOCKET)):
        raise RuntimeError(server.errorString())
    clients = {}

    def connected():
        nonlocal media
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            clients[client] = bytearray()
            def ready(client=client):
                nonlocal media
                buffer = clients[client]
                buffer.extend(bytes(client.readAll()))
                if b'\n' not in buffer:
                    return
                reply = {'ok': True}
                try:
                    command = json.loads(bytes(buffer).split(b'\n', 1)[0])
                    if command.get('clear'):
                        tab = command['clear']
                        if tab is True or tab == 'text':
                            history.clear()
                            save(HISTORY, history)
                        elif tab in ('files', 'photos'):
                            media = [item for item in media if item['type'] != tab]
                            save_media()
                    elif isinstance(command.get('text'), str):
                        clipboard.setText(command['text'])
                    elif isinstance(command.get('urls'), list):
                        urls = [QUrl(url) for url in command['urls']]
                        urls = [url for url in urls if url.isLocalFile() and Path(url.toLocalFile()).exists()]
                        if not urls:
                            raise ValueError('Оригиналы файлов перемещены или удалены')
                        mime = QMimeData()
                        mime.setUrls(urls)
                        mime.setData('x-special/gnome-copied-files', ('copy\n'+'\n'.join(url.toString() for url in urls)).encode())
                        mime.setData('application/x-kde-cutselection', b'0')
                        clipboard.setMimeData(mime)
                    elif isinstance(command.get('image'), str):
                        image = QImage(str(image_path(command['image'])))
                        if image.isNull():
                            raise ValueError('Фото больше нет в папке истории')
                        clipboard.setImage(image)
                except (OSError, ValueError, TypeError) as error:
                    reply = {'ok': False, 'error': str(error)}
                client.write(json.dumps(reply).encode()+b'\n')
                client.disconnectFromServer()
            def disconnected(client=client):
                clients.pop(client, None)
                client.deleteLater()
            client.readyRead.connect(ready)
            client.disconnected.connect(disconnected)
            ready()
    server.newConnection.connect(connected)
    clipboard.dataChanged.connect(capture)
    capture()
    app.exec()


def send(command):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5)
        client.connect(str(SOCKET))
        client.sendall(json.dumps(command).encode()+b'\n')
        reply = bytearray()
        while b'\n' not in reply:
            chunk = client.recv(4096)
            if not chunk:
                break
            reply.extend(chunk)
        # The previous daemon version acknowledges by closing the connection.
        if reply:
            result = json.loads(reply)
            if not result.get('ok'):
                raise ValueError(result.get('error', 'Ошибка буфера'))


def file_label(item):
    paths = [Path(unquote(urlparse(url).path)) for url in item['urls']]
    label = paths[0].name if paths else 'Файлы'
    if len(paths) > 1:
        label += f'  +{len(paths)-1}'
    if paths and not paths[0].exists():
        label += '  · оригинал недоступен'
    return label


def tab_entries(tab):
    return load() if tab == 'text' else [item for item in load(MEDIA) if item.get('type') == tab]


def entry_id(item):
    return hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def script_mode(tab):
    message = ''
    if os.environ.get('ROFI_RETV') == '1':
        try:
            action = os.environ.get('ROFI_INFO', '')
            if action == 'clear':
                send({'clear': tab})
            elif action == 'folder':
                target = IMAGES if tab == 'photos' else DIRECTORY
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                subprocess.Popen([str(Path.home()/'.local/bin/pcmanfm-qt'), str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            else:
                item = next((item for item in tab_entries(tab) if entry_id(item) == action), None)
                if item is not None:
                    send({'text': item} if tab == 'text' else {'urls': item['urls']} if tab == 'files' else {'image': item['image']})
                    return
                message = 'Запись уже удалена из истории'
        except (OSError, ValueError) as error:
            message = str(error).replace('\n', ' ')
    print('\0no-custom\x1ftrue')
    if message:
        print('\0message\x1f'+message)
    entries = tab_entries(tab)
    for item in entries:
        icon = ''
        if tab == 'text':
            row = ' '.join(item.split())[:100]
        elif tab == 'files':
            row = file_label(item).replace('\n', ' ')
        else:
            row = f'Фото  {item["width"]} × {item["height"]}'
            icon = '\x1ficon\x1f'+str(image_path(item['image']))
        print(row.replace('\0', '')+'\0info\x1f'+entry_id(item)+icon)
    if not entries:
        print('Пока пусто\0nonselectable\x1ftrue')
    if tab != 'text':
        print('↗  Открыть папку истории\0info\x1ffolder')
    print('×  Очистить эту вкладку\0info\x1fclear')


def watch_outside_click(window, margin=56):
    """Observe X11 button transitions without grabbing input from the desktop."""
    import ctypes as C
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import QApplication
    x11 = C.CDLL('libX11.so.6')
    x11.XOpenDisplay.argtypes = [C.c_char_p]
    x11.XOpenDisplay.restype = C.c_void_p
    x11.XDefaultRootWindow.argtypes = [C.c_void_p]
    x11.XDefaultRootWindow.restype = C.c_ulong
    x11.XQueryPointer.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                                  C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_int),
                                  C.POINTER(C.c_int), C.POINTER(C.c_uint)]
    x11.XQueryPointer.restype = C.c_int
    x11.XCloseDisplay.argtypes = [C.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        return
    root = x11.XDefaultRootWindow(display)
    def buttons():
        root_return, child = C.c_ulong(), C.c_ulong()
        rx, ry, wx, wy = C.c_int(), C.c_int(), C.c_int(), C.c_int()
        mask = C.c_uint()
        x11.XQueryPointer(display, root, C.byref(root_return), C.byref(child), C.byref(rx),
                          C.byref(ry), C.byref(wx), C.byref(wy), C.byref(mask))
        return mask.value & ((1 << 8) | (1 << 9) | (1 << 10))
    previous = buttons()
    def poll():
        nonlocal previous
        current = buttons()
        pressed = current & ~previous
        previous = current
        if pressed and not window.frameGeometry().adjusted(-margin, -margin, margin, margin).contains(QCursor.pos()):
            window.close()
    timer = QTimer(window)
    timer.setInterval(16)
    timer.timeout.connect(poll)
    timer.start()
    def cleanup():
        timer.stop()
        x11.XCloseDisplay(display)
    QApplication.instance().aboutToQuit.connect(cleanup)


def menu():
    from PyQt6.QtCore import Qt, QSize, QLockFile
    from PyQt6.QtNetwork import QLocalServer
    from PyQt6.QtGui import QIcon, QImageReader, QPixmap, QShortcut, QKeySequence, QCursor
    from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QPushButton, QLineEdit, QListWidget, QListWidgetItem,
                                QLabel, QFrame, QListView)
    app = QApplication([sys.argv[0]])
    DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = QLockFile(str(DIRECTORY/'menu.lock'))
    menu_socket = DIRECTORY/'menu.sock'
    if not lock.tryLock(0):
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(1)
                client.connect(str(menu_socket))
                client.sendall(b'show\n')
            return
        except OSError:
            # Upgrade a previous menu process that had no activation socket.
            try:
                pid = int((DIRECTORY/'menu.lock').read_text().splitlines()[0])
                args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                if str(Path(__file__).resolve()).encode() in args and b'--daemon' not in args:
                    os.kill(pid, signal.SIGTERM)
            except (OSError, ValueError, IndexError):
                pass
            if not lock.tryLock(1500):
                return

    class PhotoList(QListWidget):
        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        def wheelEvent(self, event):
            if self.owner.tab == 'photos' and event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.angleDelta().y():
                self.owner.zoom_photos(1 if event.angleDelta().y() > 0 else -1)
                event.accept()
            elif self.owner.tab == 'photos' and event.angleDelta().y() and event.pixelDelta().isNull():
                bar = self.verticalScrollBar()
                distance = max(56, round(self.owner.photo_size * 0.55))
                bar.setValue(bar.value() - round(event.angleDelta().y() / 120 * distance))
                event.accept()
            else:
                super().wheelEvent(event)

    class ClipboardWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.tab = 'text'
            self.photo_size = 130
            self.setWindowTitle('Буфер обмена')
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, True)
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                                Qt.WindowType.WindowStaysOnTopHint)
            self.setStyleSheet('''
                QWidget { background: #242424; color: #D0D0D0;
                          font-family: "DejaVu Sans Mono"; font-size: 12px; }
                QPushButton { border: none; background: #303030; padding: 8px 12px; }
                QPushButton:hover { background: #3C3C3C; }
                QPushButton:checked { background: #454545; color: white; }
                QLineEdit { background: #303030; border: none; padding: 7px; }
                QListWidget { border: none; outline: none; background: #242424; }
                QListWidget::item { padding: 6px; border: none; }
                QListWidget::item:selected { background: #454545; }
                QListWidget::item:hover { background: #343434; }
                QScrollBar:vertical { background: #242424; width: 5px; }
                QScrollBar::handle:vertical { background: #555555; min-height: 20px; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
                QLabel#muted { color: #858585; font-size: 10px; }
                QFrame#preview { background: #202020; }
            ''')
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(5)
            tabs = QHBoxLayout()
            tabs.setSpacing(3)
            self.buttons = {}
            for tab, label in zip(TABS, ('Текст', 'Файлы', 'Фото')):
                button = QPushButton(label)
                button.setCheckable(True)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda checked, tab=tab: self.switch(tab))
                tabs.addWidget(button)
                self.buttons[tab] = button
            close = QPushButton('×')
            close.setFixedWidth(30)
            close.setCursor(Qt.CursorShape.PointingHandCursor)
            close.clicked.connect(self.close)
            tabs.addWidget(close)
            layout.addLayout(tabs)
            self.search = QLineEdit()
            self.search.setPlaceholderText('Найти в истории…')
            self.search.textChanged.connect(self.filter_rows)
            layout.addWidget(self.search)
            body = QHBoxLayout()
            body.setSpacing(6)
            self.list = PhotoList(self)
            self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.list.setIconSize(QSize(40, 40))
            self.list.setMouseTracking(True)
            self.list.setCursor(Qt.CursorShape.PointingHandCursor)
            self.list.itemClicked.connect(self.clicked)
            self.list.itemDoubleClicked.connect(self.copy_selected)
            self.list.currentItemChanged.connect(self.preview_selected)
            body.addWidget(self.list, 1)
            self.preview = QFrame()
            self.preview.setObjectName('preview')
            preview_layout = QVBoxLayout(self.preview)
            preview_layout.setContentsMargins(5, 5, 5, 5)
            preview_layout.setSpacing(4)
            self.image = QLabel('Выбери фото')
            self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image.setFixedSize(380, 260)
            preview_layout.addWidget(self.image)
            self.dimensions = QLabel('')
            self.dimensions.setObjectName('muted')
            self.dimensions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(self.dimensions)
            body.addWidget(self.preview)
            layout.addLayout(body)
            actions = QHBoxLayout()
            actions.setSpacing(4)
            self.folder = QPushButton('Папка')
            self.folder.clicked.connect(self.open_folder)
            actions.addWidget(self.folder)
            self.clear_button = QPushButton('Очистить вкладку')
            self.clear_button.clicked.connect(self.clear_tab)
            actions.addWidget(self.clear_button)
            self.copy_button = QPushButton('Скопировать')
            self.copy_button.clicked.connect(self.copy_selected)
            actions.addWidget(self.copy_button)
            for button in (self.folder, self.clear_button, self.copy_button):
                button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addLayout(actions)
            self.status = QLabel('')
            self.status.setObjectName('muted')
            self.status.setWordWrap(True)
            self.status.hide()
            layout.addWidget(self.status)
            self.escape = QShortcut(QKeySequence('Escape'), self)
            self.escape.activated.connect(self.close)
            self.enter = QShortcut(QKeySequence('Return'), self)
            self.enter.activated.connect(self.copy_selected)
            self.switch('text')

        def closeEvent(self, event):
            event.accept()
            app.quit()

        def switch(self, tab):
            self.tab = tab
            for name, button in self.buttons.items():
                button.setChecked(name == tab)
            self.search.clear()
            self.status.hide()
            self.preview.hide()
            self.search.setVisible(tab != 'photos')
            self.list.setViewMode(QListView.ViewMode.IconMode if tab == 'photos' else QListView.ViewMode.ListMode)
            self.list.setResizeMode(QListView.ResizeMode.Adjust)
            self.list.setMovement(QListView.Movement.Static)
            self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel if tab == 'photos' else QListView.ScrollMode.ScrollPerItem)
            self.list.setWrapping(tab == 'photos')
            self.list.setSpacing(0)
            self.list.setGridSize(QSize(self.photo_size+14, round(self.photo_size*0.7)+14) if tab == 'photos' else QSize())
            self.list.setIconSize(QSize(self.photo_size, round(self.photo_size*0.7)) if tab == 'photos' else QSize(40, 40))
            self.folder.setVisible(tab != 'text')
            self.copy_button.setVisible(tab == 'photos')
            self.setFixedWidth(460)
            self.refresh()
            self.position()

        def refresh(self):
            self.list.clear()
            for entry in tab_entries(self.tab):
                if self.tab == 'text':
                    label = ' '.join(entry.split())[:120]
                elif self.tab == 'files':
                    label = file_label(entry).replace('\n', ' ')
                else:
                    label = ''
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                item.setToolTip(label)
                if self.tab == 'photos':
                    item.setIcon(QIcon(str(image_path(entry['image']))))
                self.list.addItem(item)
            count = self.list.count()
            if count:
                self.list.setCurrentRow(0)
            else:
                placeholder = QListWidgetItem('Пока пусто')
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(placeholder)
                self.image.clear()
                self.dimensions.clear()
            if self.tab == 'photos':
                self.layout_photos()
            else:
                self.list.setFixedHeight(max(42, min(count, 8)*32))
            self.filter_rows(self.search.text())
            self.adjustSize()

        def zoom_photos(self, direction):
            self.photo_size = max(64, min(self.width()-40, self.photo_size + direction*20))
            self.layout_photos()
            current = self.list.currentItem()
            if current:
                self.list.scrollToItem(current)
            self.adjustSize()

        def layout_photos(self):
            width = self.photo_size + 14
            screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
            max_height = min(440, round(screen.availableGeometry().height()*0.65))
            icon_height = min(self.photo_size if self.photo_size >= 300 else round(self.photo_size*0.7), max_height-18)
            height = icon_height + 14
            self.list.setIconSize(QSize(self.photo_size, icon_height))
            self.list.setGridSize(QSize(width, height))
            columns = max(1, (self.width()-22)//width)
            rows = max(1, (self.list.count()+columns-1)//columns)
            limit = max_height if self.photo_size >= 300 else 312
            self.list.setFixedHeight(min(limit, rows*height+4))
            self.list.doItemsLayout()

        def filter_rows(self, text):
            for index in range(self.list.count()):
                item = self.list.item(index)
                item.setHidden(text.casefold() not in item.text().casefold())

        def position(self):
            self.adjustSize()
            screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
            area = screen.availableGeometry()
            self.move(area.center().x()-self.width()//2, area.center().y()-self.height()//2)

        def selected(self):
            item = self.list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item and not item.isHidden() else None

        def preview_selected(self, current, previous=None):
            if self.tab != 'photos' or not current or not self.preview.isVisible():
                return
            entry = current.data(Qt.ItemDataRole.UserRole)
            if not entry:
                return
            reader = QImageReader(str(image_path(entry['image'])))
            reader.setAutoTransform(True)
            original = reader.size()
            if original.isValid():
                reader.setScaledSize(original.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            if image.isNull():
                self.image.setText('Фото удалено')
            else:
                self.image.setPixmap(QPixmap.fromImage(image))
            self.dimensions.setText(f'{entry["width"]} × {entry["height"]}')

        def clicked(self, item):
            if self.tab != 'photos':
                self.copy_selected()

        def copy_selected(self, *_):
            entry = self.selected()
            if entry is None:
                return
            try:
                send({'text': entry} if self.tab == 'text' else {'urls': entry['urls']} if self.tab == 'files' else {'image': entry['image']})
                self.close()
            except (OSError, ValueError) as error:
                self.error(error)

        def clear_tab(self):
            try:
                send({'clear': self.tab})
                self.refresh()
            except (OSError, ValueError) as error:
                self.error(error)

        def open_folder(self):
            target = IMAGES if self.tab == 'photos' else DIRECTORY
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            subprocess.Popen([str(Path.home()/'.local/bin/pcmanfm-qt'), str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def error(self, error):
            self.status.setText(str(error))
            self.status.show()
            self.adjustSize()

    window = ClipboardWindow()
    server = QLocalServer()
    QLocalServer.removeServer(str(menu_socket))
    server.listen(str(menu_socket))
    clients = []
    def activate():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            clients.append(client)
            window.show()
            window.position()
            window.raise_()
            window.activateWindow()
            window.search.setFocus()
            client.disconnectFromServer()
    server.newConnection.connect(activate)
    window.show()
    watch_outside_click(window)
    window.activateWindow()
    window.search.setFocus()
    app.exec()
    server.close()
    lock.unlock()


def stop():
    try:
        pid = int((DIRECTORY/'daemon.lock').read_text().splitlines()[0])
        args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        if str(Path(__file__).resolve()).encode() not in args or b'--daemon' not in args:
            return
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not Path(f'/proc/{pid}').exists():
                break
            time.sleep(0.1)
    except (OSError, ValueError, IndexError):
        pass


if __name__ == '__main__':
    if '--daemon' in sys.argv:
        daemon()
    elif '--stop' in sys.argv:
        stop()
    elif '--rofi-mode' in sys.argv:
        tab = sys.argv[sys.argv.index('--rofi-mode')+1]
        if tab in TABS:
            script_mode(tab)
    else:
        try:
            menu()
        except (OSError, ValueError, IndexError) as error:
            subprocess.run(['rofi', '-e', f'Буфер: {error}\nПерезапуск: ~/.config/polybar/start-clipboard.sh --restart'], check=False)
