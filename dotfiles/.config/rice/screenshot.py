#!/usr/bin/python3
"""Select and annotate a screenshot in place, then copy or save it."""
import argparse
import math
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QSize, QLockFile, QTimer
from PyQt6.QtGui import (QColor, QCursor, QFont, QImage, QPainter, QPainterPath,
                        QPen, QPolygonF, QKeySequence, QShortcut)
from PyQt6.QtWidgets import (QApplication, QWidget, QFrame, QVBoxLayout,
                            QHBoxLayout, QPushButton, QSpinBox, QLabel, QLineEdit,
                            QFileDialog, QColorDialog)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

HOME = Path.home()
TOOLS = [('move', 'Выбор'), ('pen', 'Перо'), ('arrow', 'Стрелка'),
         ('rect', 'Рамка'), ('ellipse', 'Овал'), ('text', 'Текст'),
         ('marker', 'Маркер'), ('blur', 'Размыть'), ('pixel', 'Пиксели'),
         ('number', 'Номер')]
STYLE = '''
QFrame#tools { background:#242424; border:1px solid #505050; }
QWidget { color:#d0d0d0; font:12px "DejaVu Sans"; }
QPushButton { background:#303030; border:1px solid transparent;
    padding:5px 8px; border-radius:0; }
QPushButton:hover, QPushButton:checked { background:#454545; border-color:#858585; }
QPushButton:disabled { color:#666666; }
QSpinBox, QLineEdit { background:#303030; color:#d0d0d0;
    border:1px solid #777777; padding:5px; selection-background-color:#555555; }
QLabel { background:transparent; border:0; }
QToolTip { background:#242424; color:#d0d0d0; border:1px solid #555555; }
'''


class Capture(QWidget):
    def __init__(self, image, geometry, selection=None):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle('Снимок экрана')
        self.setGeometry(geometry)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.image = image
        self.area = QRectF(selection) if selection else QRectF()
        self.items, self.undo_stack, self.redo_stack = [], [], []
        self.tool, self.color, self.stroke_width = 'move', QColor('#d69a9a'), 3
        self.drag = None
        self.draft = None
        self.start = QPointF()
        self.moving = None
        self.resize_edge = None
        self.text_at = None
        self.textbox = QLineEdit(self)
        self.textbox.hide()
        self.textbox.returnPressed.connect(self.finish_text)
        self.textbox.installEventFilter(self)
        self.setStyleSheet(STYLE)
        self.make_toolbar()
        for key, fn in [('Escape', self.cancel), ('Ctrl+C', self.copy),
                        ('Ctrl+S', self.save),
                        ('Ctrl+Z', self.undo), ('Ctrl+Shift+Z', self.redo),
                        ('Ctrl+Y', self.redo), ('Delete', self.delete_item)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(fn)
        if self.valid():
            self.place_toolbar()

    def valid(self):
        return self.area.width() >= 3 and self.area.height() >= 3

    def make_toolbar(self):
        self.toolbar = QFrame(self)
        self.toolbar.setObjectName('tools')
        layout = QVBoxLayout(self.toolbar)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        first, second = QHBoxLayout(), QHBoxLayout()
        first.setSpacing(3)
        second.setSpacing(4)
        self.buttons = {}
        for tool, name in TOOLS:
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, t=tool: self.set_tool(t))
            first.addWidget(button)
            self.buttons[tool] = button
        self.buttons['move'].setChecked(True)
        for color in ['#d69a9a', '#d0d0d0', '#141517', '#c3ad83', '#8eaa91', '#8197b0']:
            button = QPushButton('')
            button.setFixedSize(23, 23)
            button.setStyleSheet(f'background:{color}; border:1px solid #777777; padding:0;')
            button.clicked.connect(lambda checked=False, c=color: self.set_color(c))
            second.addWidget(button)
        button = QPushButton('Цвет')
        button.clicked.connect(self.pick_color)
        second.addWidget(button)
        self.swatch = QLabel(' ')
        self.swatch.setFixedSize(12, 23)
        self.swatch.setStyleSheet(f'background:{self.color.name()};')
        second.addWidget(self.swatch)
        size = QSpinBox()
        size.setRange(1, 30)
        size.setValue(self.stroke_width)
        size.setFixedWidth(58)
        size.setToolTip('Толщина линии / размер текста')
        size.valueChanged.connect(lambda value: setattr(self, 'stroke_width', value))
        second.addWidget(size)
        second.addStretch()
        self.dimensions = QLabel()
        second.addWidget(self.dimensions)
        for name, fn in [('Отмена', self.undo), ('Повтор', self.redo),
                         ('Копировать', self.copy), ('Сохранить', self.save),
                         ('×', self.close)]:
            button = QPushButton(name)
            button.clicked.connect(fn)
            second.addWidget(button)
        layout.addLayout(first)
        layout.addLayout(second)
        self.toolbar.hide()

    def set_tool(self, tool):
        self.finish_text()
        self.tool = tool
        self.moving = None
        for key, button in self.buttons.items():
            button.setChecked(key == tool)
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == 'move' else Qt.CursorShape.CrossCursor)
        self.update()

    def set_color(self, color):
        self.color = QColor(color)
        self.swatch.setStyleSheet(f'background:{self.color.name()};')

    def pick_color(self):
        color = QColorDialog.getColor(self.color, self, 'Цвет')
        if color.isValid():
            self.set_color(color)

    def snapshot(self):
        return [dict(item, points=list(item.get('points', []))) for item in self.items]

    def checkpoint(self):
        self.undo_stack.append(self.snapshot())
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.items = self.undo_stack.pop()
            self.moving = None
            self.update()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.items = self.redo_stack.pop()
            self.moving = None
            self.update()

    def bounds(self, item):
        if item['kind'] in ('pen', 'marker'):
            points = item['points']
            xs, ys = [p.x() for p in points], [p.y() for p in points]
            return QRectF(min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)).adjusted(-8, -8, 8, 8)
        return item['rect'].normalized().adjusted(-5, -5, 5, 5)

    def paint_item(self, painter, item):
        kind, color, width = item['kind'], QColor(item['color']), item['width']
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = item['rect'].normalized()
        if kind in ('pen', 'marker'):
            points = item['points']
            if kind == 'marker':
                painter.setOpacity(.35)
                painter.setPen(QPen(color, max(12, width * 5), Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.RoundJoin))
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if len(points) == 1:
                painter.drawPoint(points[0])
            else:
                painter.drawPath(path)
        elif kind == 'rect':
            painter.drawRect(rect)
        elif kind == 'ellipse':
            painter.drawEllipse(rect)
        elif kind == 'arrow':
            a, b = item['points']
            painter.drawLine(a, b)
            angle = math.atan2(b.y()-a.y(), b.x()-a.x())
            length = max(12, width * 4)
            left = QPointF(b.x()-length*math.cos(angle-.45), b.y()-length*math.sin(angle-.45))
            right = QPointF(b.x()-length*math.cos(angle+.45), b.y()-length*math.sin(angle+.45))
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([b, left, right]))
        elif kind == 'text':
            painter.setFont(QFont('DejaVu Sans', max(12, width * 3)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, item['text'])
        elif kind == 'number':
            painter.setBrush(color)
            painter.drawEllipse(rect)
            painter.setPen(QColor('#141517') if color.lightness() > 150 else QColor('#ffffff'))
            painter.setFont(QFont('DejaVu Sans', 13, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, item['text'])
        elif kind in ('blur', 'pixel') and 'image' in item:
            painter.drawImage(rect, item['image'])
        painter.restore()

    def rendered(self):
        result = self.image.copy()
        painter = QPainter(result)
        for item in self.items:
            self.paint_item(painter, item)
        painter.end()
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(QPointF(), self.image)
        if self.valid():
            painter.save()
            painter.setClipRect(self.area)
            for item in self.items:
                self.paint_item(painter, item)
            if self.draft:
                if self.draft['kind'] in ('blur', 'pixel'):
                    painter.fillRect(self.draft['rect'].normalized(), QColor(100, 100, 100, 130))
                else:
                    self.paint_item(painter, self.draft)
            painter.restore()
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if self.valid():
            shade.addRect(self.area)
        painter.fillPath(shade, QColor(0, 0, 0, 145))
        if self.valid():
            painter.setPen(QPen(QColor('#b8b8b8'), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.area)
            if self.tool == 'move':
                painter.setBrush(QColor('#d0d0d0'))
                for point in self.handles().values():
                    painter.drawRect(QRectF(point.x()-3, point.y()-3, 6, 6))
            if self.moving is not None and self.moving < len(self.items):
                painter.drawRect(self.bounds(self.items[self.moving]))
        painter.end()

    def handles(self):
        r = self.area
        return {'tl': r.topLeft(), 'tr': r.topRight(), 'bl': r.bottomLeft(), 'br': r.bottomRight()}

    def place_toolbar(self):
        if not self.valid():
            self.toolbar.hide()
            return
        self.dimensions.setText(f'{round(self.area.width())} × {round(self.area.height())}')
        self.toolbar.adjustSize()
        screen = QApplication.screenAt(self.mapToGlobal(self.area.center().toPoint())) or QApplication.primaryScreen()
        available = screen.geometry().translated(-self.geometry().topLeft())
        x = min(max(available.left()+4, round(self.area.left())), available.right()-self.toolbar.width()-4)
        y = round(self.area.bottom())+10
        if y + self.toolbar.height() > available.bottom():
            y = round(self.area.top())-self.toolbar.height()-10
        y = max(available.top()+4, y)
        self.toolbar.move(max(0, x), y)
        self.toolbar.show()
        self.toolbar.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.finish_text()
        point = event.position()
        self.start = point
        self.toolbar.hide()
        if not self.valid() or not self.area.adjusted(-7, -7, 7, 7).contains(point):
            self.drag = 'select'
            self.area = QRectF(point, point)
        elif self.tool == 'move':
            self.resize_edge = next((key for key, p in self.handles().items()
                                     if abs(p.x()-point.x())<8 and abs(p.y()-point.y())<8), None)
            if self.resize_edge:
                self.drag = 'resize'
                self.original_area = QRectF(self.area)
            else:
                self.moving = next((i for i in range(len(self.items)-1, -1, -1)
                                    if self.bounds(self.items[i]).contains(point)), None)
                if self.moving is not None:
                    self.checkpoint()
                    self.original_item = dict(self.items[self.moving])
                    self.drag = 'item'
                else:
                    self.original_area = QRectF(self.area)
                    self.drag = 'region'
        elif self.tool == 'text':
            self.text_at = point
            self.textbox.setGeometry(int(point.x()), int(point.y()), min(300, self.width()-int(point.x())-4), 36)
            self.textbox.clear()
            self.textbox.show()
            self.textbox.setFocus()
        elif self.tool == 'number':
            self.checkpoint()
            count = sum(item['kind']=='number' for item in self.items)+1
            self.items.append(dict(kind='number', color=self.color.name(), width=2,
                                   rect=QRectF(point.x()-16, point.y()-16, 32, 32), text=str(count)))
            self.place_toolbar()
        else:
            self.drag = 'draw'
            self.draft = dict(kind=self.tool, color=self.color.name(), width=self.stroke_width,
                              rect=QRectF(point, point),
                              points=[point, point] if self.tool == 'arrow' else [point])
        self.update()

    def mouseMoveEvent(self, event):
        point = event.position()
        if self.drag == 'select':
            self.area = QRectF(self.start, point).normalized().intersected(QRectF(self.rect()))
        elif self.drag == 'draw':
            self.draft['rect'] = QRectF(self.start, point)
            if self.tool in ('pen', 'marker'):
                self.draft['points'].append(point)
            else:
                self.draft['points'] = [self.start, point]
        elif self.drag == 'resize':
            r = QRectF(self.original_area)
            {'tl': r.setTopLeft, 'tr': r.setTopRight, 'bl': r.setBottomLeft,
             'br': r.setBottomRight}[self.resize_edge](point)
            self.area = r.normalized().intersected(QRectF(self.rect()))
        elif self.drag == 'region':
            r = self.original_area.translated(point-self.start)
            r.moveLeft(max(0, min(r.left(), self.width()-r.width())))
            r.moveTop(max(0, min(r.top(), self.height()-r.height())))
            self.area = r
        elif self.drag == 'item':
            delta = point-self.start
            item = dict(self.original_item)
            item['rect'] = item['rect'].translated(delta)
            item['points'] = [p+delta for p in item.get('points', [])]
            self.items[self.moving] = item
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.drag == 'draw' and self.draft:
            item = self.draft
            rect = item['rect'].normalized().intersected(self.area)
            if item['kind'] in ('blur', 'pixel') and rect.width() >= 2 and rect.height() >= 2:
                item['rect'] = rect
                patch = self.crop(rect)
                if item['kind'] == 'pixel':
                    patch = patch.scaled(max(1, patch.width()//12), max(1, patch.height()//12),
                                         Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.FastTransformation).scaled(
                                             patch.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                             Qt.TransformationMode.FastTransformation)
                else:
                    from PIL import Image, ImageFilter
                    patch = patch.convertToFormat(QImage.Format.Format_RGBA8888)
                    data = patch.constBits().asstring(patch.sizeInBytes())
                    pil = Image.frombytes('RGBA', (patch.width(), patch.height()), data,
                                          'raw', 'RGBA', patch.bytesPerLine()).filter(ImageFilter.GaussianBlur(12))
                    patch = QImage(pil.tobytes(), pil.width, pil.height,
                                   pil.width*4, QImage.Format.Format_RGBA8888).copy()
                item['image'] = patch
            if item['kind'] not in ('blur', 'pixel') or 'image' in item:
                self.checkpoint()
                self.items.append(item)
            self.draft = None
        self.drag = None
        self.place_toolbar()
        self.update()

    def finish_text(self):
        if not self.textbox.isVisible():
            return
        text = self.textbox.text().strip()
        if text:
            self.checkpoint()
            self.items.append(dict(kind='text', color=self.color.name(), width=self.stroke_width,
                                   rect=QRectF(self.text_at.x(), self.text_at.y(),
                                               max(40, self.area.right()-self.text_at.x()),
                                               max(30, self.stroke_width*6)), text=text))
        self.textbox.hide()
        self.setFocus()
        self.place_toolbar()
        self.update()

    def eventFilter(self, obj, event):
        if obj is self.textbox and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.textbox.hide()
                self.setFocus()
                self.place_toolbar()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.copy()
        else:
            super().keyPressEvent(event)

    def delete_item(self):
        if self.moving is not None and self.moving < len(self.items):
            self.checkpoint()
            self.items.pop(self.moving)
            self.moving = None
            self.update()

    def crop(self, rect=None):
        rect = (rect or self.area).toAlignedRect()
        scale = self.image.devicePixelRatio()
        pixels = QRect(round(rect.x()*scale), round(rect.y()*scale),
                       round(rect.width()*scale), round(rect.height()*scale))
        result = self.rendered().copy(pixels)
        result.setDevicePixelRatio(1)
        return result

    def copy(self):
        if self.textbox.hasFocus():
            return
        if not self.valid():
            return
        self.finish_text()
        self.clipboard_image = self.crop()
        QApplication.clipboard().setImage(self.clipboard_image)
        self.hide()
        # Keep the X11 clipboard owner alive until another application replaces
        # the image. Closing immediately would lose screenshots without a manager.
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.clipboard_monitor = QTimer(self)
        self.clipboard_monitor.setInterval(750)
        self.clipboard_monitor.timeout.connect(self.release_clipboard)
        self.clipboard_monitor.start()
        if hasattr(self, 'activation_server'):
            self.activation_server.close()
        if lock.isLocked():
            lock.unlock()
        print('Copied screenshot; capture lock released.', flush=True)

    def release_clipboard(self):
        if not QApplication.clipboard().ownsClipboard():
            QApplication.quit()

    def save(self):
        if not self.valid():
            return
        self.finish_text()
        folder = HOME/'Pictures/Screenshots'
        folder.mkdir(parents=True, exist_ok=True)
        name = folder/('Screenshot_'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.png')
        target, _ = QFileDialog.getSaveFileName(self, 'Сохранить снимок', str(name),
                                               'PNG (*.png);;JPEG (*.jpg)')
        if target:
            if not self.crop().save(target):
                self.dimensions.setText('Не удалось сохранить')
                return
            self.close()

    def cancel(self):
        if self.textbox.isVisible():
            self.textbox.hide()
            self.place_toolbar()
        else:
            self.close()


def grab_desktop(app):
    geometry = QRect()
    screens = app.screens()
    for screen in screens:
        geometry = geometry.united(screen.geometry())
    scale = max(screen.devicePixelRatio() for screen in screens)
    image = QImage(QSize(round(geometry.width()*scale), round(geometry.height()*scale)),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(scale)
    image.fill(QColor('#141517'))
    painter = QPainter(image)
    for screen in screens:
        rect = screen.geometry().translated(-geometry.topLeft())
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            painter.end()
            raise RuntimeError('Не удалось захватить экран')
        painter.drawPixmap(rect, pixmap)
    painter.end()
    return image, geometry


def active_geometry():
    try:
        text = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        import re
        wid = re.search(r'0x[0-9a-fA-F]+', text).group()
        info = subprocess.check_output(['xwininfo', '-id', wid], text=True)
        values = [int(re.search(pattern+r':\s*(-?\d+)', info).group(1)) for pattern in
                  ['Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height']]
        return QRect(*values)
    except (OSError, subprocess.SubprocessError, AttributeError):
        return None


def acquire_capture(lock, cache):
    if lock.tryLock(0):
        return True
    client = QLocalSocket()
    client.connectToServer(str(cache/'screenshot.sock'))
    if client.waitForConnected(1000):
        client.write(b'show\n')
        client.waitForBytesWritten(1000)
        client.disconnectFromServer()
        print('Requested activation of existing capture.', flush=True)
        return False
    # Upgrade the old capture process, which had no activation socket and
    # silently blocked every subsequent hotkey. Only signal this exact script.
    try:
        pid = int((cache/'screenshot.lock').read_text().splitlines()[0])
        process = Path(f'/proc/{pid}')
        args = (process/'cmdline').read_bytes().split(b'\0')
        if (pid != os.getpid() and process.stat().st_uid == os.getuid()
                and str(Path(__file__).resolve()).encode() in args):
            print('Replacing unresponsive/legacy capture:', pid, flush=True)
            os.kill(pid, signal.SIGTERM)
            if lock.tryLock(2000):
                return True
    except (OSError, ValueError, IndexError):
        # QLockFile validates dead owners before removing stale locks.
        if lock.tryLock(0):
            return True
    print('Unable to activate capture or acquire lock.', flush=True)
    subprocess.run(['notify-send', 'Снимок экрана',
                    'Не удалось открыть захват. Подробности: ~/.cache/rice/screenshot.log'],
                   check=False)
    return False


def show_capture(window):
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
    window.show()
    window.raise_()
    window.activateWindow()
    window.setFocus(Qt.FocusReason.OtherFocusReason)
    print('Capture window shown:', window.geometry().getRect(), flush=True)


def main():
    global lock
    parser = argparse.ArgumentParser()
    parser.add_argument('--active', action='store_true')
    parser.add_argument('--fullscreen', action='store_true')
    parser.add_argument('--preview')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Rice Screenshot')
    cache = HOME/'.cache/rice'
    cache.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(cache/'screenshot.lock'))
    if args.preview:
        # Previews must not compete with the actual desktop capture lock.
        lock = QLockFile(str(cache/f'screenshot-preview-{os.getpid()}.lock'))
        if not lock.tryLock(0):
            return 1
    elif not acquire_capture(lock, cache):
        return 0
    if args.preview:
        geometry = QRect(0, 0, 1280, 800)
        image = QImage(geometry.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor('#303030'))
        painter = QPainter(image)
        painter.setPen(QColor('#d0d0d0'))
        painter.setFont(QFont('DejaVu Sans', 20))
        painter.drawText(QRect(60, 160, 800, 300), Qt.AlignmentFlag.AlignCenter,
                         'Снимок экрана\nРедактирование поверх выделенной области')
        painter.end()
        window = Capture(image, geometry, QRect(100, 150, 950, 440))
        window.items.append(dict(kind='arrow', color='#d69a9a', width=4,
                                 rect=QRectF(250, 430, 160, -75),
                                 points=[QPointF(250, 430), QPointF(410, 355)]))
        window.show()
        app.processEvents()
        window.grab().save(args.preview)
        lock.unlock()
        return 0
    print(datetime.now().isoformat(), 'Starting capture', os.getpid(), flush=True)
    socket_name = str(cache/'screenshot.sock')
    QLocalServer.removeServer(socket_name)
    server = QLocalServer()
    if not server.listen(socket_name):
        raise RuntimeError('Capture activation socket: '+server.errorString())
    selection = active_geometry() if args.active else None
    image, geometry = grab_desktop(app)
    print('Desktop captured:', image.size().width(), image.size().height(), flush=True)
    if args.fullscreen:
        selection = geometry
    if selection:
        selection = selection.intersected(geometry).translated(-geometry.topLeft())
    window = Capture(image, geometry, selection)
    window.activation_server = server
    def activate():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            client.disconnectFromServer()
            client.deleteLater()
        show_capture(window)
    server.newConnection.connect(activate)
    show_capture(window)
    QTimer.singleShot(150, lambda: show_capture(window) if window.isVisible() else None)
    result = app.exec()
    server.close()
    if lock.isLocked():
        lock.unlock()
    return result


if __name__ == '__main__':
    sys.exit(main())
