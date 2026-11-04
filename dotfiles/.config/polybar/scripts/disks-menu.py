#!/usr/bin/python3
import html
import json
from pathlib import Path
import subprocess
from popup_position import popup_args


def partitions(devices):
    result = []
    for disk in devices:
        result.extend(partitions(disk.get('children', [])))
        if disk.get('fstype') and disk.get('type') != 'rom' and disk['fstype'] != 'swap':
            result.append(disk)
    return result


def render(partition):
    mounts = [m for m in partition.get('mountpoints', []) if m]
    mount = '/' if '/' in mounts else next(iter(mounts), None)
    name = partition.get('label') or partition['name']
    name = html.escape(name[:22])
    if mount:
        percent = partition.get('fsuse%') or '0%'
        count = min(16, max(0, round(float(percent.rstrip('%')) * 16 / 100)))
        description = f'{partition.get("fsavail") or "?"} свободно · {html.escape(mount)}'
        bar = f'<span foreground="#B8B8B8">{"━"*count}</span><span foreground="#454545">{"━"*(16-count)}</span>'
    else:
        description = 'не подключён · открыть'
        bar = '<span foreground="#777777">○</span>'
    row = (f'<span foreground="#D0D0D0"><b>{name}</b></span> '
           f'<span foreground="#858585">{partition.get("size", "")} · {partition["fstype"]}</span>\n'
           f'{bar} <span foreground="#777777" size="small">{description}</span>')
    return row, mount


def main():
    output = subprocess.run(['lsblk', '-J', '-o', 'NAME,PATH,TYPE,FSTYPE,LABEL,SIZE,FSAVAIL,FSUSE%,MOUNTPOINTS'], text=True, capture_output=True, check=True)
    disks = partitions(json.loads(output.stdout)['blockdevices'])
    disks.sort(key=lambda d: (not any(d.get('mountpoints') or []), d['name']))
    rendered = [render(d) for d in disks]
    menu = subprocess.run(['rofi', '-dmenu', '-no-custom', '-no-sort', '-markup-rows', '-format', 'i',
                           '-theme', str(Path.home()/'.config/rofi/disks.rasi')] + popup_args(410),
                          input='\n'.join(row.replace('\n', '&#10;') for row, _ in rendered), text=True, capture_output=True)
    if menu.returncode:
        return
    index = int(menu.stdout.strip())
    if not 0 <= index < len(disks):
        return
    mount = rendered[index][1]
    if not mount:
        mounted = subprocess.run(['gio', 'mount', '-d', disks[index]['path']], text=True, capture_output=True)
        if mounted.returncode:
            subprocess.run(['rofi', '-e', mounted.stderr.strip() or 'Не удалось подключить раздел'], check=False)
            return
        output = subprocess.run(['lsblk', '-n', '-o', 'MOUNTPOINTS', disks[index]['path']], text=True, capture_output=True, check=True)
        mount = next((line.strip() for line in output.stdout.splitlines() if line.strip()), None)
    target = mount or 'computer:///'
    subprocess.Popen(['pcmanfm-qt', target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
