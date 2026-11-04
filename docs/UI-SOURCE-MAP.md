# Карта обработчиков взаимодействий

Эта карта ссылается на сохранённый код. Она дополняет ручной каталог INVENTORY.md и полный список XML-привязок; исходники сохраняются целиком, включая ветвления, параметры и состояния меню. Номера строк относятся к этому снимку.

## audio-output.py

Исходник: [audio-output.py](../dotfiles/.config/polybar/scripts/audio-output.py)

```text
33: options = choices(json.loads(run('pactl', '-f', 'json', 'list', 'sinks')), run('pactl', 'get-default-sink'))
```

## calendar-menu.py

Исходник: [calendar-menu.py](../dotfiles/.config/polybar/scripts/calendar-menu.py)

```text
50: ] + popup_args(260), input='‹ Назад\nСегодня\nВперёд ›', text=True, capture_output=True)
```

## clipboard.py

Исходник: [clipboard.py](../dotfiles/.config/polybar/scripts/clipboard.py)

```text
18: TABS = ('text', 'files', 'photos')
186: client.readyRead.connect(ready)
187: client.disconnected.connect(disconnected)
189: server.newConnection.connect(connected)
190: clipboard.dataChanged.connect(capture)
198: client.connect(str(SOCKET))
309: timer.timeout.connect(poll)
314: QApplication.instance().aboutToQuit.connect(cleanup)
320: from PyQt6.QtGui import QIcon, QImageReader, QPixmap, QShortcut, QKeySequence, QCursor
332: client.connect(str(menu_socket))
397: button = QPushButton(label)
400: button.clicked.connect(lambda checked, tab=tab: self.switch(tab))
403: close = QPushButton('×')
406: close.clicked.connect(self.close)
410: self.search.setPlaceholderText('Найти в истории…')
411: self.search.textChanged.connect(self.filter_rows)
420: self.list.itemClicked.connect(self.clicked)
421: self.list.itemDoubleClicked.connect(self.copy_selected)
422: self.list.currentItemChanged.connect(self.preview_selected)
441: self.folder = QPushButton('Папка')
442: self.folder.clicked.connect(self.open_folder)
444: self.clear_button = QPushButton('Очистить вкладку')
445: self.clear_button.clicked.connect(self.clear_tab)
447: self.copy_button = QPushButton('Скопировать')
448: self.copy_button.clicked.connect(self.copy_selected)
458: self.escape = QShortcut(QKeySequence('Escape'), self)
459: self.escape.activated.connect(self.close)
460: self.enter = QShortcut(QKeySequence('Return'), self)
461: self.enter.activated.connect(self.copy_selected)
501: item.setToolTip(label)
622: server.newConnection.connect(activate)
```

## devices-menu.py

Исходник: [devices-menu.py](../dotfiles/.config/polybar/scripts/devices-menu.py)

```text
79: choices=['Открыть','Безопасно извлечь'] if item['mounts'] else ['Подключить и открыть','Безопасно извлечь']
```

## file-search.py

Исходник: [file-search.py](../dotfiles/.config/polybar/scripts/file-search.py)

```text
116: self.query.setPlaceholderText('Найти файл или папку…')
120: self.results.itemActivated.connect(self.open_selected)
121: self.results.itemClicked.connect(self.open_selected)
128: self.delay.timeout.connect(self.filter)
129: self.query.textChanged.connect(lambda *_:self.delay.start())
132: index.batch.connect(self.receive)
133: index.finished.connect(self.indexed)
181: if event.key()==Qt.Key.Key_Escape:self.close();return True
182: if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.open_selected();return True
183: if watched is self.query and event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down):
184: row=self.results.currentRow()+(-1 if event.key()==Qt.Key.Key_Up else 1)
235: server.newConnection.connect(activate)
```

## happ-menu.py

Исходник: [happ-menu.py](../dotfiles/.config/polybar/scripts/happ-menu.py)

```text
157: options = server_actions(layout)
```

## internet-menu.py

Исходник: [internet-menu.py](../dotfiles/.config/polybar/scripts/internet-menu.py)

```text
10: from PyQt6.QtGui import QCursor, QDesktopServices, QKeySequence, QShortcut
78: self.button = QPushButton('Измерить скорость')
79: self.button.setToolTip('Быстрый замер через Cloudflare · до 38 МБ. Задержка HTTPS. Учитывается текущий VPN.')
80: self.button.clicked.connect(self.toggle_test)
82: self.copy = QPushButton('Копировать внешний IP')
84: self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.public_ip))
86: browser = QPushButton('Яндекс Интернетометр ↗')
87: browser.clicked.connect(self.open_browser)
98: self.signals.event.connect(self.result)
99: QShortcut(QKeySequence('Escape'), self, activated=self.close)
102: self.timer.timeout.connect(self.refresh)
143: self.link.setToolTip(f"Локальный IP: {info['address']}")
181: self.identity.setToolTip(f"Страна: {value['location']} · сервер проверки: {value['server']}")
185: self.identity.setToolTip(value)
```

## music-widget.py

Исходник: [music-widget.py](../dotfiles/.config/polybar/scripts/music-widget.py)

```text
38: self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
66: self.seek_target.connect('button-press-event', self.seek)
71: self.connect('scroll-event', self.scroll_volume)
80: title.connect('clicked', lambda *_: self.action('Raise'))
88: button.connect('clicked', lambda _, a=action: self.action(a))
92: self.connect('size-allocate', lambda *_: self.position())
95: self.get_screen().connect('monitors-changed', lambda *_: self.position())
132: if event.button != 1 or not self.name or not self.can_seek or not self.track_id or self.track_length <= 0:
264: self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
268: target.connect('button-press-event', self.clicked)
271: self.get_screen().connect('monitors-changed', lambda *_: self.position())
276: if event.button == 1:
278: elif event.button == 3:
285: print('Logo click:', event.button, flush=True, file=output)
307: self.connect('realize', lambda w: w.get_window().set_override_redirect(True))
322: self.ayu_monitor.connect('changed', self.ayu_settings_changed)
324: self.connect('destroy', self.stop_watches)
513: app.connect('activate', activate)
```

## startup-audit.py

Исходник: [startup-audit.py](../dotfiles/.config/polybar/scripts/startup-audit.py)

```text
117: client.connect(str(HOME/'.cache/rice-clipboard/clipboard.sock'))
```

## window-switcher.py

Исходник: [window-switcher.py](../dotfiles/.config/polybar/scripts/window-switcher.py)

```text
155: button = QToolButton()
160: button.clicked.connect(lambda checked=False, i=index: self.choose(i))
190: self.timer.timeout.connect(self.check_alt)
216: if event.key() == Qt.Key.Key_Escape:
219: elif event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Left, Qt.Key.Key_Right):
220: backward = event.key() in (Qt.Key.Key_Backtab, Qt.Key.Key_Left) or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
223: elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
229: if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
```

## screenshot.py

Исходник: [screenshot.py](../dotfiles/.config/rice/screenshot.py)

```text
14: QPen, QPolygonF, QKeySequence, QShortcut)
21: TOOLS = [('move', 'Выбор'), ('pen', 'Перо'), ('arrow', 'Стрелка'),
59: self.textbox.returnPressed.connect(self.finish_text)
67: shortcut = QShortcut(QKeySequence(key), self)
68: shortcut.activated.connect(fn)
86: button = QPushButton(name)
88: button.clicked.connect(lambda checked=False, t=tool: self.set_tool(t))
93: button = QPushButton('')
96: button.clicked.connect(lambda checked=False, c=color: self.set_color(c))
98: button = QPushButton('Цвет')
99: button.clicked.connect(self.pick_color)
109: size.setToolTip('Толщина линии / размер текста')
110: size.valueChanged.connect(lambda value: setattr(self, 'stroke_width', value))
118: button = QPushButton(name)
119: button.clicked.connect(fn)
279: if event.button() == Qt.MouseButton.RightButton:
282: if event.button() != Qt.MouseButton.LeftButton:
355: if event.button() != Qt.MouseButton.LeftButton:
403: if event.key() == Qt.Key.Key_Escape:
411: if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
446: self.clipboard_monitor.timeout.connect(self.release_clipboard)
618: server.newConnection.connect(activate)
```

