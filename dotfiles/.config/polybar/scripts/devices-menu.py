#!/usr/bin/python3
"""Panel menu for removable storage, sound and known Bluetooth devices."""
import html
import json
import subprocess
import sys
from pathlib import Path
from gi.repository import Gio,GLib
from popup_position import popup_args

HOME=Path.home()
THEME=str(HOME/'.config/rofi/devices.rasi')


def run(*args,timeout=5):
    return subprocess.run(list(args),capture_output=True,text=True,timeout=timeout)


def message(text):
    run('rofi','-e',text,'-theme',THEME,*popup_args(420,edge_gap=8),timeout=120)


def menu(rows,title='Устройства'):
    result=subprocess.run(['rofi','-dmenu','-no-custom','-no-sort','-markup-rows','-format','i',
        '-theme',THEME,'-mesg',html.escape(title)]+popup_args(420,edge_gap=8),
        input='\n'.join(rows),text=True,capture_output=True)
    if result.returncode:return None
    try:return int(result.stdout.strip())
    except ValueError:return None


def removable():
    result=run('lsblk','-J','-o','NAME,PATH,TYPE,FSTYPE,LABEL,SIZE,MOUNTPOINTS,RM,TRAN')
    found=[]
    protected=set()
    def visit(items,disk=None,portable=False):
        for item in items:
            if item.get('type')=='disk':disk=item['path']
            external=portable or bool(item.get('rm')) or item.get('tran')=='usb'
            mounts=[mount for mount in item.get('mountpoints',[]) if mount]
            if any(mount in ('/','/home','/boot','/boot/efi') for mount in mounts):
                protected.add(disk or item['path'])
            if external and item.get('fstype') and item.get('fstype')!='swap' and not any(mount in ('/','/home','/boot','/boot/efi') for mount in mounts):
                found.append(dict(item,disk=disk or item['path'],mounts=mounts))
            visit(item.get('children',[]),disk,external)
    if result.returncode==0:visit(json.loads(result.stdout)['blockdevices'])
    return [item for item in found if item['disk'] not in protected]


def bluetooth():
    try:
        bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
        objects=bus.call_sync('org.bluez','/','org.freedesktop.DBus.ObjectManager','GetManagedObjects',None,None,Gio.DBusCallFlags.NONE,800,None).unpack()[0]
        return [(path,interfaces['org.bluez.Device1']) for path,interfaces in objects.items()
                if 'org.bluez.Device1' in interfaces and (interfaces['org.bluez.Device1'].get('Paired') or interfaces['org.bluez.Device1'].get('Connected'))]
    except GLib.Error:return []


def collect():
    rows,actions=[],[]
    def add(label,kind,data):rows.append(label);actions.append((kind,data))
    for item in removable():
        name=item.get('label') or item['name']
        state='подключён' if item['mounts'] else 'не смонтирован'
        add(f'USB  <b>{html.escape(name)}</b>  <span foreground="#858585">{item["size"]} · {state}</span>','disk',item)
    result=run('pactl','-f','json','list','sinks')
    default=run('pactl','get-default-sink').stdout.strip()
    if result.returncode==0:
        for sink in json.loads(result.stdout):
            mark='●' if sink['name']==default else '○'
            add(f'{mark}  Звук · {html.escape(sink.get("description") or sink["name"])}','sound',sink)
    for path,props in bluetooth():
        mark='●' if props.get('Connected') else '○'
        add(f'{mark}  BT · {html.escape(props.get("Alias") or props.get("Name") or "Устройство")}','bluetooth',(path,props))
    return rows,actions


def disk_action(item):
    choices=['Открыть','Безопасно извлечь'] if item['mounts'] else ['Подключить и открыть','Безопасно извлечь']
    choice=menu(choices,item.get('label') or item['name'])
    if choice is None:return
    if choice==0:
        if not item['mounts']:
            result=run('udisksctl','mount','--block-device',item['path'],timeout=30)
            if result.returncode:message(result.stderr.strip() or 'Не удалось подключить накопитель');return
            result=run('lsblk','-n','-o','MOUNTPOINTS',item['path'])
            item['mounts']=[line.strip() for line in result.stdout.splitlines() if line.strip()]
        if item['mounts']:
            subprocess.Popen([str(HOME/'.local/bin/pcmanfm-qt'),item['mounts'][0]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    elif choice==1:
        # Unmount every partition of the drive before requesting power-off.
        siblings=[part for part in removable() if part['disk']==item['disk']]
        for part in siblings:
            if part['mounts']:
                result=run('udisksctl','unmount','--block-device',part['path'],timeout=30)
                if result.returncode:message(result.stderr.strip() or 'Накопитель занят');return
        result=run('udisksctl','power-off','--block-device',item['disk'],timeout=30)
        if result.returncode:message(result.stderr.strip() or 'Устройство размонтировано, но питание не отключилось')


def main():
    rows,actions=collect()
    if '--check' in sys.argv:
        print('Device menu initialized; devices:',len(rows));return
    selected=menu(rows or ['Нет доступных устройств'])
    if selected is None or not actions or not 0<=selected<len(actions):return
    kind,item=actions[selected]
    if kind=='disk':disk_action(item)
    elif kind=='sound':
        result=run('pactl','set-default-sink',item['name'])
        if result.returncode:message(result.stderr.strip());return
        result=run('pactl','-f','json','list','sink-inputs')
        if result.returncode==0:
            for stream in json.loads(result.stdout):
                moved=run('pactl','move-sink-input',str(stream['index']),item['name'])
                if moved.returncode:message('Устройство выбрано. Некоторые приложения нужно перезапустить.');break
    elif kind=='bluetooth':
        path,props=item
        connected=props.get('Connected',False)
        choice=menu(['Отключить' if connected else 'Подключить'],props.get('Alias','Bluetooth'))
        if choice==0:
            try:
                bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
                bus.call_sync('org.bluez',path,'org.bluez.Device1','Disconnect' if connected else 'Connect',None,None,Gio.DBusCallFlags.NONE,20000,None)
            except GLib.Error as error:message('Bluetooth: '+error.message)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        if '--check' in sys.argv:raise
        message('Не удалось получить устройства: '+str(error))
