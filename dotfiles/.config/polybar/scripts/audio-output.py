#!/usr/bin/python3
import json
import subprocess
from popup_position import popup_args
from pathlib import Path


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True).stdout.strip()


def choices(sinks, default):
    result = []
    for sink in sinks:
        name = sink['name']
        description = sink.get('description') or name
        active = sink.get('active_port')
        if isinstance(active, dict):
            active = active.get('name')
        ports = sink.get('ports', [])
        if isinstance(ports, dict):
            ports = [dict(value, name=key) for key, value in ports.items()]
        ports = [p for p in ports if str(p.get('availability', p.get('available', 'unknown'))).lower() not in ('no', 'not available')]
        for port in ports or [None]:
            port_name = port['name'] if port else None
            selected = name == default and (not port or port_name == active)
            label = description + (' — ' + port.get('description', port_name) if port else '')
            result.append((('● ' if selected else '  ') + label.replace('\n', ' '), name, port_name))
    return result


def main():
    options = choices(json.loads(run('pactl', '-f', 'json', 'list', 'sinks')), run('pactl', 'get-default-sink'))
    if not options:
        run('rofi', '-e', 'Нет доступных устройств вывода звука')
        return
    selected = next((i for i, option in enumerate(options) if option[0].startswith('● ')), 0)
    menu = subprocess.run(['rofi', '-selected-row', str(selected), '-dmenu', '-i', '-no-custom', '-format', 'i', '-p', 'Вывод звука', '-theme', str(Path.home()/'.config/rofi/audio.rasi')] + popup_args(420), input='\n'.join(o[0] for o in options), text=True, capture_output=True)
    if menu.returncode:
        return
    index = int(menu.stdout.strip())
    if not 0 <= index < len(options):
        return
    _, sink, port = options[index]
    if port:
        run('pactl', 'set-sink-port', sink, port)
    run('pactl', 'set-default-sink', sink)
    failed = []
    for stream in json.loads(run('pactl', '-f', 'json', 'list', 'sink-inputs')):
        try:
            run('pactl', 'move-sink-input', str(stream['index']), sink)
        except subprocess.CalledProcessError:
            failed.append(str(stream['index']))
    if failed:
        run('rofi', '-e', 'Устройство выбрано. Для некоторых приложений потребуется перезапустить воспроизведение.')


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, ValueError, KeyError) as error:
        subprocess.run(['rofi', '-e', 'Не удалось переключить звук: ' + (getattr(error, 'stderr', '') or str(error))], check=False)
