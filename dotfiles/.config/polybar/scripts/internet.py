#!/usr/bin/python3
"""Local network counters and bounded, cancellable Internet measurements."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time

BASE = 'https://speed.cloudflare.com'


def run(args, timeout=4):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def connection():
    try:
        routes = json.loads(run(['ip', '-j', 'route', 'get', '1.1.1.1']) or '[]')
        route = routes[0] if routes else {}
    except (ValueError, IndexError):
        route = {}
    name = route.get('dev', '')
    address = route.get('prefsrc', route.get('src', '—'))
    if not name:
        try:
            routes6 = json.loads(run(['ip', '-j', '-6', 'route', 'show', 'default']) or '[]')
            name = routes6[0].get('dev', '') if routes6 else ''
        except (ValueError, IndexError):
            pass
    physical = []
    physical_present = False
    for entry in Path('/sys/class/net').iterdir():
        if entry.name == 'lo' or not (entry/'device').exists():
            continue
        physical_present = True
        try:
            if (entry/'carrier').read_text().strip() == '1':
                physical.append(entry)
        except OSError:
            continue
    physical.sort(key=lambda entry: entry.name != name)
    device = physical[0] if physical else (Path('/sys/class/net')/name if name else None)
    wireless = bool(device and (device/'wireless').exists())
    linked = bool(physical) if physical_present else bool(name)
    kind = ('Wi-Fi' if wireless else 'Ethernet') if linked else 'Нет подключения'
    return {'interface': name, 'address': address, 'kind': kind, 'linked': linked,
            'wireless': wireless, 'device': device.name if device else '',
            'vpn': bool(name and device and name != device.name)}


def counters(name):
    try:
        base = Path('/sys/class/net')/name/'statistics'
        return tuple(int((base/file).read_text()) for file in ('rx_bytes', 'tx_bytes'))
    except (OSError, ValueError):
        return (0, 0)


def rate(value):
    if value >= 1_000_000:
        return f'{value/1_000_000:.1f}M'
    return f'{value/1000:.0f}K'


class Cancelled(Exception):
    pass


class Probe:
    def __init__(self):
        self.cancelled = threading.Event()
        self.process = None
        self.lock = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def curl(self, url, *, upload=None, metrics=False, timeout=15):
        if self.cancelled.is_set():
            raise Cancelled()
        args = ['curl', '--silent', '--show-error', '--fail', '--connect-timeout', '5',
                '--max-time', str(timeout), '--user-agent', 'PanelInternet/1.0']
        if metrics:
            args += ['--output', '/dev/null', '--write-out', '%{json}']
        if upload is not None:
            args += ['--request', 'POST', '--data-binary', '@-']
        args += [url]
        with self.lock:
            if self.cancelled.is_set():
                raise Cancelled()
            process = subprocess.Popen(args, stdin=subprocess.PIPE if upload is not None else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.process = process
        try:
            output, error = process.communicate(upload, timeout=timeout+2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise RuntimeError('Сервер не ответил вовремя. Попробуйте ещё раз.')
        finally:
            with self.lock:
                self.process = None
        if self.cancelled.is_set():
            raise Cancelled()
        if metrics and process.returncode == 28:
            partial = json.loads(output)
            transferred = partial.get('size_upload' if upload is not None else 'size_download', 0)
            if transferred > 0:
                return partial
        if process.returncode:
            raise RuntimeError('Не удалось связаться с сервером проверки. Проверьте сеть или VPN.')
        return json.loads(output) if metrics else output.decode('utf-8', errors='replace')

    def identity(self):
        trace = self.curl(BASE+'/cdn-cgi/trace', timeout=8)
        values = dict(line.split('=', 1) for line in trace.splitlines() if '=' in line)
        if not values.get('ip'):
            raise RuntimeError('Сервер не вернул внешний IP.')
        return {'ip': values['ip'], 'location': values.get('loc', '—'), 'server': values.get('colo', '—')}

    def speed(self, report):
        report('stage', 'Проверяем задержку…')
        samples = []
        for i in range(5):
            metrics = self.curl(BASE+f'/__down?bytes=0&nonce={time.time_ns()}', metrics=True, timeout=10)
            elapsed = max(0, metrics['time_starttransfer'] - metrics['time_pretransfer'])*1000
            if i:  # Discard the first request as a warm-up.
                samples.append(elapsed)
        report('latency', {'latency': statistics.median(samples),
                           'jitter': statistics.mean(abs(b-a) for a,b in zip(samples, samples[1:]))})
        report('stage', 'Измеряем приём…')
        warm = self.curl(BASE+f'/__down?bytes=1000000&nonce={time.time_ns()}', metrics=True, timeout=12)
        download_size = max(64000, min(29_000_000, int(warm['speed_download']*4)))
        down = self.curl(BASE+f'/__down?bytes={download_size}&nonce={time.time_ns()}', metrics=True, timeout=15)
        if down.get('size_download', 0) <= 0:
            raise RuntimeError('Приём данных прервался. Повторите проверку.')
        report('download', down['speed_download']*8/1_000_000)
        report('stage', 'Измеряем отдачу…')
        warm = self.curl(BASE+'/__up', upload=os.urandom(256_000), metrics=True, timeout=12)
        upload_size = max(64000, min(7_744_000, int(warm['speed_upload']*4)))
        up = self.curl(BASE+'/__up', upload=os.urandom(upload_size), metrics=True, timeout=15)
        if up.get('size_upload', 0) <= 0:
            raise RuntimeError('Отправка данных прервалась. Повторите проверку.')
        report('upload', up['speed_upload']*8/1_000_000)
        report('stage', 'Проверка завершена')


def internet_available():
    # Validate content as well as the response, so captive portals are not "online".
    response = run(['curl', '--silent', '--fail', '--connect-timeout', '2', '--max-time', '3',
                    '--max-filesize', '4096',
                    'http://www.msftconnecttest.com/connecttest.txt'], timeout=4)
    if response == 'Microsoft Connect Test':
        return True
    response = run(['curl', '--silent', '--fail', '--connect-timeout', '2', '--max-time', '3',
                    '--max-filesize', '4096', BASE+'/cdn-cgi/trace'], timeout=4)
    return any(line.startswith('ip=') for line in response.splitlines())


def status_icon(info, online):
    # Private glyphs in the local Panel Network Icons font.
    if not info['linked']:
        code, color = 0xE003, '#777777'
    elif online is None:
        code, color = 0xE004, '#858585'
    elif not online:
        code, color = 0xE002, '#B77B7B'
    else:
        code, color = (0xE001 if info['wireless'] else 0xE000), '#858585'
    return '%{T5}%{F'+color+'}'+chr(code)+'%{F-}%{T-}'


def indicator():
    state = {'online': None, 'checked': 0, 'busy': False, 'generation': 0}
    previous = None
    cache = Path.home()/'.cache/rice/internet-status.json'
    def check(generation):
        online = internet_available()
        if state['generation'] == generation:
            state.update(online=online, checked=time.monotonic())
        state['busy'] = False
    while True:
        info = connection()
        identity = (info['interface'], info['device'], info['linked'])
        if identity != previous:
            state.update(online=None, checked=0, generation=state['generation']+1)
            previous = identity
        if info['linked'] and not state['busy'] and time.monotonic()-state['checked'] >= 15:
            state['busy'] = True
            threading.Thread(target=check, args=(state['generation'],), daemon=True).start()
        print(status_icon(info, state['online']), flush=True)
        try:
            temp = cache.with_suffix('.tmp')
            temp.write_text(json.dumps({'linked':info['linked'], 'online':state['online'],
                                        'kind':info['kind'], 'time':time.time()}))
            temp.replace(cache)
        except OSError:
            pass
        time.sleep(2)


if __name__ == '__main__':
    try:
        indicator()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
