#!/usr/bin/python3
import calendar
from datetime import date
import fcntl
from pathlib import Path
import subprocess
from popup_position import popup_args

MONTHS = ('ЯНВАРЬ', 'ФЕВРАЛЬ', 'МАРТ', 'АПРЕЛЬ', 'МАЙ', 'ИЮНЬ',
          'ИЮЛЬ', 'АВГУСТ', 'СЕНТЯБРЬ', 'ОКТЯБРЬ', 'НОЯБРЬ', 'ДЕКАБРЬ')


def shift(year, month, delta):
    year, month = divmod(year * 12 + month - 1 + delta, 12)
    return year, month + 1


def render(year, month, today):
    lines = [f'<span foreground="#D0D0D0"><b>{MONTHS[month-1]} {year}</b></span>',
             '', '<span foreground="#777777"> ПН  ВТ  СР  ЧТ  ПТ  СБ  ВС </span>']
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        cells = []
        for weekday, day in enumerate(week):
            if day == 0:
                cells.append('    ')
            elif (year, month, day) == (today.year, today.month, today.day):
                cells.append(f'<span background="#454545" foreground="#FFFFFF"><b> {day:2} </b></span>')
            else:
                color = '#858585' if weekday >= 5 else '#D0D0D0'
                cells.append(f'<span foreground="{color}"> {day:2} </span>')
        lines.append(''.join(cells))
    return '\n'.join(lines)


def main():
    lock_path = Path.home()/'.cache/polybar/calendar.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        today = date.today()
        year, month = today.year, today.month
        while True:
            result = subprocess.run([
                'rofi', '-dmenu', '-no-custom', '-no-sort', '-format', 'i',
                '-selected-row', '1', '-mesg', render(year, month, today),
                '-theme', str(Path.home()/'.config/rofi/calendar.rasi')
            ] + popup_args(260), input='‹ Назад\nСегодня\nВперёд ›', text=True, capture_output=True)
            if result.returncode:
                return
            choice = result.stdout.strip()
            if choice == '1':
                today = date.today()
                year, month = today.year, today.month
            elif choice in ('0', '2'):
                year, month = shift(year, month, -1 if choice == '0' else 1)
                if not 1 <= year <= 9999:
                    year, month = today.year, today.month
            else:
                return


if __name__ == '__main__':
    main()
