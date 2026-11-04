#!/usr/bin/python3
import os
import re
import signal
import subprocess

ENV = dict(os.environ, LC_ALL='C')


def read(*args):
    return subprocess.run(['pactl', *args], env=ENV, capture_output=True,
                          text=True, check=True).stdout


def status():
    try:
        muted = read('get-sink-mute', '@DEFAULT_SINK@').strip().endswith('yes')
        values = re.findall(r'(\d+)%', read('get-sink-volume', '@DEFAULT_SINK@'))
        volume = round(sum(map(int, values)) / len(values)) if values else 0
        return 'VOL muted' if muted else f'VOL {volume}%{{T3}}%%{{T-}}'
    except subprocess.CalledProcessError:
        return 'VOL --'


def main():
    subscriber = subprocess.Popen(['pactl', 'subscribe'], env=ENV, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
    def stop(*_):
        raise SystemExit
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        previous = status()
        print(previous, flush=True)
        for event in subscriber.stdout:
            if ' on sink ' not in event and ' on server ' not in event:
                continue
            current = status()
            if current != previous:
                print(current, flush=True)
                previous = current
    finally:
        subscriber.terminate()
        subscriber.wait()


if __name__ == '__main__':
    main()
