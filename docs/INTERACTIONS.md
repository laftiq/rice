# Все сохранённые привязки Openbox

Автоматически извлечено из полного rc.xml. Модификаторы: W = Super, A = Alt, C = Ctrl, S = Shift. Коды X11 сохранены намеренно: привязки работают по физической клавише при US/RU.

Физические клавиши текущей X11-карты: 0x28=D, 0x1a=E, 0x21=P, 0x27=S, 0x37=V, 0x2e=L, 0x29=F.

## Клавиатура

| Привязка | Действие и параметры |
| --- | --- |
| `C-A-Left` | GoToDesktop; to=left; wrap=no |
| `C-A-Right` | GoToDesktop; to=right; wrap=no |
| `C-A-Up` | GoToDesktop; to=up; wrap=no |
| `C-A-Down` | GoToDesktop; to=down; wrap=no |
| `S-A-Left` | SendToDesktop; to=left; wrap=no |
| `S-A-Right` | SendToDesktop; to=right; wrap=no |
| `S-A-Up` | SendToDesktop; to=up; wrap=no |
| `S-A-Down` | SendToDesktop; to=down; wrap=no |
| `W-F1` | GoToDesktop; to=1 |
| `W-F2` | GoToDesktop; to=2 |
| `W-F3` | GoToDesktop; to=3 |
| `W-F4` | GoToDesktop; to=4 |
| `W-0x28` | ToggleShowDesktop |
| `A-F4` | Close |
| `A-Escape` | Lower / FocusToBottom / Unfocus |
| `A-space` | ShowMenu; menu=client-menu |
| `A-Print` | Execute; command=__RICE_HOME__/.local/bin/rice-screenshot --active |
| `A-Tab` | Execute; command=/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/window-switcher.py |
| `A-S-Tab` | Execute; command=/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/window-switcher.py --reverse |
| `C-A-Tab` | NextWindow; panels=yes; desktop=yes; finalactions:  |
| `W-S-Right` | DirectionalCycleWindows; direction=right |
| `W-S-Left` | DirectionalCycleWindows; direction=left |
| `W-S-Up` | DirectionalCycleWindows; direction=up |
| `W-S-Down` | DirectionalCycleWindows; direction=down |
| `W-0x1a` | Execute; startupnotify: true             Konqueror; command=__RICE_HOME__/.local/bin/pcmanfm-qt |
| `S-Print` | Execute; command=__RICE_HOME__/.local/bin/rice-screenshot --fullscreen |
| `Print` | Execute; command=__RICE_HOME__/.local/bin/rice-screenshot |
| `W-space` | Execute; command=rofi -show drun |
| `W-Return` | Execute; command=kitty |
| `W-0x21` | Execute; command=__RICE_HOME__/.local/bin/pcmanfm-qt |
| `W-S-0x27` | Execute; command=__RICE_HOME__/.local/bin/rice-screenshot |
| `W-0x37` | Execute; command=python3 __RICE_HOME__/.config/polybar/scripts/clipboard.py |
| `W-0x2e` | Execute; command=__RICE_HOME__/.config/rice/lock.sh |
| `W-S-0x29` | Execute; command=/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/file-search.py |

## Мышь: все контексты

| Контекст | Кнопка | Событие | Действие и параметры |
| --- | --- | --- | --- |
| Frame | A-Left | Press | Focus / Raise |
| Frame | A-Left | Click | Unshade |
| Frame | A-Left | Drag | Move |
| Frame | A-Right | Press | Focus / Raise / Unshade |
| Frame | A-Right | Drag | Resize |
| Frame | A-Middle | Press | Lower / FocusToBottom / Unfocus |
| Frame | A-Up | Click | GoToDesktop; to=previous |
| Frame | A-Down | Click | GoToDesktop; to=next |
| Frame | C-A-Up | Click | GoToDesktop; to=previous |
| Frame | C-A-Down | Click | GoToDesktop; to=next |
| Frame | A-S-Up | Click | SendToDesktop; to=previous |
| Frame | A-S-Down | Click | SendToDesktop; to=next |
| Titlebar | Left | Drag | Move |
| Titlebar | Left | DoubleClick | ToggleMaximize |
| Titlebar | Up | Click | if; shaded=no; then:  |
| Titlebar | Down | Click | if; shaded=yes; then:  |
| Titlebar Top Right Bottom Left TLCorner TRCorner BRCorner BLCorner | Left | Press | Focus / Raise / Unshade |
| Titlebar Top Right Bottom Left TLCorner TRCorner BRCorner BLCorner | Middle | Press | Lower / FocusToBottom / Unfocus |
| Titlebar Top Right Bottom Left TLCorner TRCorner BRCorner BLCorner | Right | Press | Focus / Raise / ShowMenu; menu=client-menu |
| Top | Left | Drag | Resize; edge=top |
| Left | Left | Drag | Resize; edge=left |
| Right | Left | Drag | Resize; edge=right |
| Bottom | Left | Drag | Resize; edge=bottom |
| Bottom | Right | Press | Focus / Raise / ShowMenu; menu=client-menu |
| TRCorner BRCorner TLCorner BLCorner | Left | Press | Focus / Raise / Unshade |
| TRCorner BRCorner TLCorner BLCorner | Left | Drag | Resize |
| Client | Left | Press | Focus / Raise |
| Client | Middle | Press | Focus / Raise |
| Client | Right | Press | Focus / Raise |
| Icon | Left | Press | Focus / Raise / Unshade / ShowMenu; menu=client-menu |
| Icon | Right | Press | Focus / Raise / ShowMenu; menu=client-menu |
| AllDesktops | Left | Press | Focus / Raise / Unshade |
| AllDesktops | Left | Click | ToggleOmnipresent |
| Shade | Left | Press | Focus / Raise |
| Shade | Left | Click | ToggleShade |
| Iconify | Left | Press | Focus / Raise |
| Iconify | Left | Click | Iconify |
| Maximize | Left | Press | Focus / Raise / Unshade |
| Maximize | Middle | Press | Focus / Raise / Unshade |
| Maximize | Right | Press | Focus / Raise / Unshade |
| Maximize | Left | Click | ToggleMaximize |
| Maximize | Middle | Click | ToggleMaximize; direction=vertical |
| Maximize | Right | Click | ToggleMaximize; direction=horizontal |
| Close | Left | Press | Focus / Raise / Unshade |
| Close | Left | Click | If; query: [Aa][Yy][Uu][Gg][Rr][Aa][Mm]; then: /usr/bin/flatpak kill com.ayugram.desktop; else:  |
| Desktop | A-Up | Click | GoToDesktop; to=previous |
| Desktop | A-Down | Click | GoToDesktop; to=next |
| Desktop | C-A-Up | Click | GoToDesktop; to=previous |
| Desktop | C-A-Down | Click | GoToDesktop; to=next |
| Desktop | Left | Press | Focus / Raise |
| Desktop | Right | Press | Focus / Raise |
| Root | Middle | Press | ShowMenu; menu=client-list-combined-menu |
| Root | Right | Press | ShowMenu; menu=root-menu |
| MoveResize | A-Up | Click | GoToDesktop; to=previous |
| MoveResize | A-Down | Click | GoToDesktop; to=next |

## Корневое меню

| Пункт | Действие |
| --- | --- |
| Приложения | rofi -show drun |
| Терминал | kitty |
| Файлы | __RICE_HOME__/.local/bin/pcmanfm-qt |
| Заблокировать | __RICE_HOME__/.config/rice/lock.sh |
| Перечитать настройки |  |
| Выйти |  |

## Kitty: русские комбинации

```text
map kitty_mod+ч copy_to_clipboard
map kitty_mod+с paste_from_clipboard
map kitty_mod+ы paste_from_selection
map kitty_mod+щ pass_selection_to_program
map kitty_mod+л scroll_line_up
map kitty_mod+о scroll_line_down
map kitty_mod+ж scroll_to_prompt -1
map kitty_mod+я scroll_to_prompt 1
map kitty_mod+р show_scrollback
map kitty_mod+п show_last_command_output
map kitty_mod+и new_os_window
map kitty_mod+ц close_window
map kitty_mod+а move_window_forward
map kitty_mod+м move_window_backward
map kitty_mod+к start_resizing_window
map kitty_mod+е new_tab
map kitty_mod+й close_tab
map kitty_mod+alt+е set_tab_title
map kitty_mod+д next_layout
map kitty_mod+у open_url_with_hints
map kitty_mod+з>а kitten hints --type path --program -
map kitty_mod+з>shift+а kitten hints --type path
map kitty_mod+з>д kitten hints --type line --program -
map kitty_mod+з>ц kitten hints --type word --program -
map kitty_mod+з>р kitten hints --type hash --program -
map kitty_mod+з>и kitten hints --type linenum
map kitty_mod+з>н kitten hints --type hyperlink
map kitty_mod+г kitten unicode_input
map kitty_mod+ф>т set_background_opacity +0.1
map kitty_mod+ф>д set_background_opacity -0.1
map kitty_mod+ф>1 set_background_opacity 1
map kitty_mod+ф>в set_background_opacity default
```

## Polybar: все действия конфигурации

Здесь сохранены также определения неактивных модулей; список активных см. config.ini.

- `[module/filesystem]` — `format-mounted = %{A1:python3 __RICE_HOME__/.config/polybar/scripts/disks-menu.py:}<label-mounted>%{A}`
- `[module/pulseaudio]` — `click-left = python3 __RICE_HOME__/.config/polybar/scripts/audio-output.py`
- `[module/pulseaudio]` — `click-right = pactl set-sink-mute @DEFAULT_SINK@ toggle`
- `[module/pulseaudio]` — `scroll-up = pactl set-sink-volume @DEFAULT_SINK@ +5%`
- `[module/pulseaudio]` — `scroll-down = pactl set-sink-volume @DEFAULT_SINK@ -5%`
- `[module/memory]` — `format = %{A1:python3 __RICE_HOME__/.config/polybar/scripts/memory-menu.py:}<label>%{A}`
- `[module/date]` — `click-left = python3 __RICE_HOME__/.config/polybar/scripts/calendar-menu.py`
- `[module/date]` — `click-right = python3 __RICE_HOME__/.config/polybar/scripts/clock.py toggle`
- `[module/powermenu]` — `click-left = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/power-menu.py`
- `[module/notifications]` — `click-left = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/notifications.py toggle`
- `[module/notifications]` — `click-right = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/notification-history.py`
- `[module/internet]` — `click-left = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/internet-menu.py`
- `[module/internet]` — `click-right = xdg-open https://yandex.ru/internet/`
- `[module/happ]` — `click-left = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/happ-vpn.py toggle`
- `[module/happ]` — `click-right = /usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/happ-vpn.py open`
