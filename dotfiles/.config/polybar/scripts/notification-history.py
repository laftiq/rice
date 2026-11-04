#!/usr/bin/python3
"""Browse Dunst history without removing or redisplaying notifications."""
import html
import json
import re
import subprocess
from pathlib import Path
from popup_position import popup_args
import notification_data as data

THEME = str(Path.home() / '.config/rofi/notifications.rasi')


def plain(value):
    while isinstance(value, dict) and 'data' in value:
        value = value['data']
    return str(value or '')


def entries(value):
    if isinstance(value, list):
        return [entry for item in value for entry in entries(item)]
    if isinstance(value, dict):
        if 'summary' in value:
            return [value]
        return entries(value.get('data', []))
    return []


def clean(text):
    return html.unescape(re.sub('<[^>]+>', '', plain(text)))


def menu(rows, message=None, selected=0):
    args = ['rofi', '-dmenu', '-no-custom', '-no-sort', '-markup-rows', '-format', 'i',
            '-selected-row', str(selected), '-theme', THEME] + popup_args(420, edge_gap=8)
    if message:
        args += ['-mesg', message]
    return subprocess.run(args, input='\n'.join(rows), capture_output=True, text=True)


def main():
    history = data.history()
    history.sort(key=data.timestamp, reverse=True)
    data.mark_viewed(history)
    if not history:
        menu(['История пока пуста'])
        return
    rows = []
    for entry in history:
        app = html.escape(' '.join(clean(entry.get('appname', '')).split())[:22])
        title = html.escape(' '.join(clean(entry.get('summary', '')).split())[:55])
        body_text = ' '.join(clean(entry.get('body', '')).split())
        # Show the message itself directly in the history, with a compact preview.
        body = html.escape(body_text[:100] + ('…' if len(body_text) > 100 else ''))
        stamp = data.clock(entry)
        heading = f'<span foreground="#777777">{stamp}</span>  <b>{title}</b>'
        if app:
            heading += f' <span size="small" foreground="#777777">{app}</span>'
        rows.append(heading + '&#10;<span foreground="#a0a0a0">' + (body or 'Без текста') + '</span>')
    rows.append('<span foreground="#858585">Очистить историю</span>')
    selected = 0
    while True:
        result = menu(rows, selected=selected)
        if result.returncode:
            return
        try:
            selected = int(result.stdout.strip())
            if selected == len(history):
                result = subprocess.run(['dunstctl', 'history-clear'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    menu(['История очищена'])
                return
            entry = history[selected]
        except (ValueError, IndexError):
            return
        message = (f'<span foreground="#858585">{html.escape(clean(entry.get("appname", "")))}</span>\n'
                   f'<b>{html.escape(clean(entry.get("summary", "")))}</b>\n\n'
                   f'{html.escape(clean(entry.get("body", "")))}')
        if menu(['‹ Назад к истории'], message).returncode:
            return


if __name__ == '__main__':
    main()
