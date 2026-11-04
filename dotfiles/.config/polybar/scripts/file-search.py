#!/usr/bin/python3
"""Small filename search in the user's home, including hidden entries."""
import os
import subprocess
import sys
import threading
import ctypes as C
import ctypes.util
import re
from pathlib import Path
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QLockFile, QSize
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel

HOME = Path.home()
SKIP = {'node_modules','__pycache__','venv','env','target','session-app-data-backup','lost+found'}


def activate_previous(pid):
    """Raise a search started before local activation support was installed."""
    def prop(*args):
        result = subprocess.run(['xprop', *args], capture_output=True, text=True, timeout=2)
        return result.stdout
    try:
        for wid in re.findall(r'0x[0-9a-fA-F]+', prop('-root', '_NET_CLIENT_LIST')):
            info = prop('-id', wid, '_NET_WM_PID', '_NET_WM_NAME')
            if not re.search(rf'_NET_WM_PID\(CARDINAL\) = {pid}\b', info):
                continue
            if 'Поиск файлов' not in info:
                continue
            x = C.CDLL(ctypes.util.find_library('X11'))
            signatures = {
                'XOpenDisplay': ([C.c_char_p], C.c_void_p),
                'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
                'XInternAtom': ([C.c_void_p, C.c_char_p, C.c_int], C.c_ulong),
                'XSendEvent': ([C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.c_void_p], C.c_int),
                'XFlush': ([C.c_void_p], C.c_int),
                'XCloseDisplay': ([C.c_void_p], C.c_int),
            }
            for name, (args, result) in signatures.items():
                getattr(x, name).argtypes, getattr(x, name).restype = args, result
            display = x.XOpenDisplay(None)
            if not display:
                return False
            class Data(C.Union):
                _fields_ = [('l', C.c_long * 5)]
            class Message(C.Structure):
                _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                            ('display', C.c_void_p), ('window', C.c_ulong), ('message_type', C.c_ulong),
                            ('format', C.c_int), ('data', Data)]
            event = C.create_string_buffer(C.sizeof(C.c_long) * 24)
            message = Message.from_buffer(event)
            message.type, message.send_event, message.format = 33, True, 32
            message.display, message.window = display, int(wid, 16)
            message.message_type = x.XInternAtom(display, b'_NET_ACTIVE_WINDOW', False)
            message.data.l[0] = 2
            x.XSendEvent(display, x.XDefaultRootWindow(display), False,
                         (1 << 20) | (1 << 19), event)
            x.XFlush(display)
            x.XCloseDisplay(display)
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


class Index(QObject):
    batch = pyqtSignal(object)
    finished = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.stop = threading.Event()

    def run(self):
        batch, count = [], 0
        for folder, dirs, files in os.walk(HOME, followlinks=False):
            if self.stop.is_set():
                return
            dirs[:] = sorted(name for name in dirs if name not in SKIP)
            for name in dirs + files:
                path = Path(folder)/name
                batch.append((name.casefold(), str(path), name in dirs))
                count += 1
                if len(batch) >= 2000:
                    self.batch.emit(batch)
                    batch = []
        if batch:
            self.batch.emit(batch)
        self.finished.emit(count)


class Search(QWidget):
    def __init__(self, index):
        super().__init__(None,Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.index, self.paths = index, []
        self.setWindowTitle('Поиск файлов')
        self.setFixedWidth(600)
        self.resize(600,300)
        self.setStyleSheet('''
            QWidget { background:#242424; color:#d0d0d0; font:12px "DejaVu Sans Mono"; }
            QLineEdit { background:#343434; border:0; padding:12px; selection-background-color:#505050; }
            QListWidget { border:0; outline:0; }
            QListWidget::item { padding:8px; border:0; }
            QListWidget::item:selected { background:#343434; }
            QLabel { color:#858585; font-size:11px; }
            QScrollBar:vertical { background:transparent; width:3px; }
            QScrollBar::handle:vertical { background:#777777; min-height:20px; }
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
        ''')
        layout=QVBoxLayout(self)
        layout.setContentsMargins(14,14,14,12)
        layout.setSpacing(8)
        self.query=QLineEdit()
        self.query.setPlaceholderText('Найти файл или папку…')
        layout.addWidget(self.query)
        self.results=QListWidget()
        self.results.setIconSize(QSize(22,22))
        self.results.itemActivated.connect(self.open_selected)
        self.results.itemClicked.connect(self.open_selected)
        layout.addWidget(self.results,1)
        self.status=QLabel('Поиск…')
        layout.addWidget(self.status)
        self.delay=QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.setInterval(100)
        self.delay.timeout.connect(self.filter)
        self.query.textChanged.connect(lambda *_:self.delay.start())
        self.query.installEventFilter(self)
        self.results.installEventFilter(self)
        index.batch.connect(self.receive)
        index.finished.connect(self.indexed)
        self.complete=False
        screen=app.screenAt(QCursor.pos()) or app.primaryScreen()
        rect=screen.availableGeometry()
        self.move(rect.center().x()-300,rect.center().y()-225)

    def receive(self, batch):
        self.paths.extend(batch)
        if not self.delay.isActive():self.delay.start()

    def indexed(self,count):
        self.complete=True
        self.filter()

    def filter(self):
        terms=self.query.text().casefold().split()
        self.results.clear()
        count=0
        for name,path,is_dir in self.paths:
            if terms and not all(term in name for term in terms):continue
            if not terms and Path(path).parent!=HOME:continue
            entry=Path(path)
            relative=str(entry.parent.relative_to(HOME))
            item=QListWidgetItem(entry.name+'\n'+('~' if relative=='.' else '~/'+relative))
            item.setData(Qt.ItemDataRole.UserRole,(path,is_dir))
            item.setIcon(QIcon.fromTheme('folder' if is_dir else 'text-x-generic'))
            self.results.addItem(item)
            count+=1
            if count>=150:break
        if count:self.results.setCurrentRow(0)
        prefix='Найдено: '+str(count)+('+' if count==150 else '')
        self.status.setText(prefix)
        self.results.setFixedHeight(min(300,max(96,count*48)))
        self.adjustSize()

    def open_selected(self,*_):
        item=self.results.currentItem()
        if not item:return
        path,is_dir=item.data(Qt.ItemDataRole.UserRole)
        parent=bool(app.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        if parent or is_dir:
            subprocess.Popen([str(HOME/'.local/bin/pcmanfm-qt'),str(Path(path).parent if parent else Path(path))],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(['xdg-open',path],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.close()

    def eventFilter(self,watched,event):
        if event.type()==event.Type.KeyPress:
            if event.key()==Qt.Key.Key_Escape:self.close();return True
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.open_selected();return True
            if watched is self.query and event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down):
                row=self.results.currentRow()+(-1 if event.key()==Qt.Key.Key_Up else 1)
                self.results.setCurrentRow(max(0,min(row,self.results.count()-1)))
                return True
        return super().eventFilter(watched,event)

    def closeEvent(self,event):
        self.index.stop.set()
        super().closeEvent(event)
        app.quit()


app=QApplication(sys.argv)
cache=HOME/'.cache/rice'
cache.mkdir(parents=True,exist_ok=True)
lock=QLockFile(str(cache/'file-search.lock'))
socket_name=str(cache/'file-search.sock')
if '--check' not in sys.argv and not lock.tryLock(0):
    client=QLocalSocket()
    client.connectToServer(socket_name)
    if client.waitForConnected(500):
        client.write(b'show\n')
        client.waitForBytesWritten(500)
        client.disconnectFromServer()
        sys.exit(0)
    try:
        pid=int((cache/'file-search.lock').read_text().splitlines()[0])
    except (OSError, ValueError, IndexError):
        pid=0
    if not pid or not activate_previous(pid):
        print('File search is already running but could not be activated.',file=sys.stderr)
    sys.exit(0)
index=Index()
window=Search(index)
if '--check' in sys.argv:
    window.receive([('documents',str(HOME/'Documents'),True)])
    window.filter()
    print('File search initialized')
else:
    QLocalServer.removeServer(socket_name)
    server=QLocalServer()
    if not server.listen(socket_name):
        print('File search activation:',server.errorString(),file=sys.stderr)
    def activate():
        while server.hasPendingConnections():
            client=server.nextPendingConnection()
            client.disconnectFromServer()
            client.deleteLater()
        window.showNormal()
        window.raise_()
        window.activateWindow()
        window.query.setFocus()
    server.newConnection.connect(activate)
    threading.Thread(target=index.run,daemon=True).start()
    window.show()
    window.query.setFocus()
    app.exec()
    server.close()
lock.unlock()
