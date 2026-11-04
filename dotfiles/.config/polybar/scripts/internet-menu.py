#!/usr/bin/python3
"""Panel popup with live traffic and on-demand speed measurements."""
import os
import json
import sys
import threading
import time
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QLockFile, QObject, pyqtSignal, QUrl
from PyQt6.QtGui import QCursor, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout
from internet import Probe, Cancelled, connection, counters, rate


class Signals(QObject):
    event = pyqtSignal(str, object)


class InternetMenu(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('Интернет')
        self.setObjectName('internet')
        self.setFixedWidth(350)
        self.setStyleSheet('''
            QWidget#internet { background:#242424; border:0; }
            QLabel { color:#d0d0d0; border:0; font:13px "DejaVu Sans Mono"; }
            QLabel[muted="true"] { color:#858585; }
            QLabel[heading="true"] { color:#b8b8b8; font:bold 13px "DejaVu Sans Mono"; }
            QLabel[metric="true"] { font:bold 13px "DejaVu Sans Mono"; }
            QPushButton { color:#d0d0d0; background:transparent; border:0;
                border-left:2px solid transparent; padding:7px 6px; text-align:left; font:13px "DejaVu Sans Mono"; }
            QPushButton:hover, QPushButton:focus { background:transparent; border-left:2px solid #b8b8b8; }
            QPushButton:disabled { color:#777777; }
        ''')
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 10, 10, 8)
        box.setSpacing(7)
        title = QLabel('ИНТЕРНЕТ')
        title.setProperty('heading', True)
        box.addWidget(title)
        self.link = QLabel()
        self.status = QLabel('Проверяем доступ в интернет…')
        self.status.setWordWrap(True)
        self.status.setProperty('muted', True)
        self.live = QLabel()
        self.live.setProperty('muted', True)
        box.addWidget(self.link)
        box.addWidget(self.status)
        box.addWidget(self.live)
        self.identity = QLabel('Внешний IP: определяем…')
        self.identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.identity.setWordWrap(True)
        box.addWidget(self.identity)
        box.addSpacing(5)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(5)
        self.metrics = {}
        for row, (name, label) in enumerate([('download','Приём · Мбит/с'),('upload','Отдача · Мбит/с'),
                                            ('latency','Задержка · мс'),('jitter','Джиттер · мс')]):
            caption = QLabel(label)
            caption.setProperty('muted', True)
            value = QLabel('—')
            value.setProperty('metric', True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(caption, row, 0)
            grid.addWidget(value, row, 1)
            self.metrics[name] = value
        box.addLayout(grid)
        self.stage = QLabel()
        self.stage.setWordWrap(True)
        self.stage.setProperty('muted', True)
        self.stage.hide()
        box.addWidget(self.stage)
        box.addSpacing(3)
        self.button = QPushButton('Измерить скорость')
        self.button.setToolTip('Быстрый замер через Cloudflare · до 38 МБ. Задержка HTTPS. Учитывается текущий VPN.')
        self.button.clicked.connect(self.toggle_test)
        box.addWidget(self.button)
        self.copy = QPushButton('Копировать внешний IP')
        self.copy.setEnabled(False)
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.public_ip))
        box.addWidget(self.copy)
        browser = QPushButton('Яндекс Интернетометр ↗')
        browser.clicked.connect(self.open_browser)
        box.addWidget(browser)
        for button in (self.button, self.copy, browser):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.public_ip = ''
        self.previous = None
        self.closed = False
        self.testing = False
        self.test_probe = None
        self.identity_probe = Probe()
        self.signals = Signals(self)
        self.signals.event.connect(self.result)
        QShortcut(QKeySequence('Escape'), self, activated=self.close)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        threading.Thread(target=self.fetch_identity, daemon=True).start()
        self.adjustSize()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        rect = screen.availableGeometry()
        x = max(rect.left()+8, min(QCursor.pos().x()-self.width()//2, rect.right()-self.width()-8))
        # Keep the popup directly under the 32px top bar, including multi-monitor setups.
        self.move(x, max(screen.geometry().top()+38, rect.top()+6))

    def emit(self, kind, value):
        if not self.closed:
            try:
                self.signals.event.emit(kind, value)
            except RuntimeError:
                pass

    def fetch_identity(self):
        try:
            self.emit('identity', self.identity_probe.identity())
        except Cancelled:
            pass
        except (OSError, ValueError, RuntimeError) as error:
            self.emit('identity-error', str(error))

    def refresh(self):
        info = connection()
        iface = info['interface']
        device = info['device'] or iface
        self.link.setText(f"{info['kind']} · {device}" if info['linked'] else 'Нет подключения')
        try:
            state = json.loads((Path.home()/'.cache/rice/internet-status.json').read_text())
            online = state.get('online') if time.time()-state['time'] < 40 else None
        except (OSError, ValueError, KeyError):
            online = None
        status = ('Интернет доступен' if online else 'Без доступа к интернету') if online is not None else 'Проверяем доступ в интернет…'
        if not info['linked']:
            status = 'Кабель отключён / Wi-Fi не подключён'
        elif info['vpn']:
            status += ' · VPN'
        self.status.setText(status)
        self.link.setToolTip(f"Локальный IP: {info['address']}")
        now = time.monotonic()
        totals = counters(iface) if iface else (0, 0)
        down = up = 0
        if self.previous and self.previous[0] == iface:
            dt = max(now-self.previous[1], .01)
            down, up = [max(0,b-a)/dt for a,b in zip(self.previous[2],totals)]
        self.previous = (iface,now,totals)
        self.live.setText(f'Сейчас: ↓ {rate(down)}Б/с   ↑ {rate(up)}Б/с')

    def toggle_test(self):
        if self.testing:
            self.test_probe.cancel()
            self.button.setEnabled(False)
            return
        self.testing = True
        self.test_probe = Probe()
        for value in self.metrics.values():
            value.setText('—')
        self.button.setText('Остановить проверку')
        self.stage.show()
        self.stage.setText('Подключаемся…')
        threading.Thread(target=self.measure, args=(self.test_probe,), daemon=True).start()

    def measure(self, probe):
        try:
            probe.speed(self.emit)
        except Cancelled:
            self.emit('stage','Проверка остановлена')
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.emit('stage',str(error))
        finally:
            self.emit('finished',None)

    def result(self, kind, value):
        if kind == 'identity':
            self.public_ip = value['ip']
            self.identity.setText(f"Внешний IP: {value['ip']}")
            self.identity.setToolTip(f"Страна: {value['location']} · сервер проверки: {value['server']}")
            self.copy.setEnabled(True)
        elif kind == 'identity-error':
            self.identity.setText('Внешний IP: недоступен')
            self.identity.setToolTip(value)
        elif kind == 'latency':
            for key,number in value.items():
                self.metrics[key].setText(f'{number:.0f}')
        elif kind in ('download','upload'):
            self.metrics[kind].setText(f'{value:.1f}')
        elif kind == 'stage':
            self.stage.setText(value)
            self.stage.show()
        elif kind == 'finished':
            self.testing = False
            self.button.setText('Измерить снова')
            self.button.setEnabled(True)

    def open_browser(self):
        self.close()
        QDesktopServices.openUrl(QUrl('https://yandex.ru/internet/'))

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.timer.stop()
        self.identity_probe.cancel()
        if self.test_probe:
            self.test_probe.cancel()
        QApplication.quit()

    def hideEvent(self, event):
        # Qt.Popup dismisses itself when a click lands outside its bounds.
        # Its hide event must also cancel probes and release the process lock.
        self.shutdown()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    cache = Path.home()/'.cache/rice'
    cache.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(cache/'internet-menu.lock'))
    if not lock.tryLock(0):
        sys.exit(0)
    window = InternetMenu()
    window.show()
    window.activateWindow()
    window.setFocus()
    app.exec()
