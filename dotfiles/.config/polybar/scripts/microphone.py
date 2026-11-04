#!/usr/bin/python3
"""Default real microphone activity and mute status."""
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path


def run(*args):
    return subprocess.run(['pactl',*args],capture_output=True,text=True,timeout=2)


def sources():
    result=run('-f','json','list','sources')
    result.check_returncode()
    return [source for source in json.loads(result.stdout or '[]')
            if not source.get('name','').endswith('.monitor') and source.get('monitor_of_sink') in (None,4294967295,'4294967295')]


def current():
    items=sources()
    default=run('get-default-source').stdout.strip()
    return next((item for item in items if item['name']==default),items[0] if items else None)


def targets():
    items=sources()
    result=run('-f','json','list','source-outputs')
    result.check_returncode()
    active={output.get('source') for output in json.loads(result.stdout or '[]') if not output.get('corked',False)}
    preference=Path.home()/'.config/rice/microphone-source'
    chosen=preference.read_text().strip() if preference.exists() else ''
    explicit=next((source for source in items if source['name']==chosen),None)
    if explicit:return [explicit],explicit['index'] in active
    used=[source for source in items if source['index'] in active]
    if used:return used,True
    default=run('get-default-source').stdout.strip()
    selected=next((source for source in items if source['name']==default),items[0] if items else None)
    return ([selected] if selected else []),False


def choose_source():
    from popup_position import popup_args
    items=sources()
    if not items:return
    rows=[source.get('description') or source['name'] for source in items]
    result=subprocess.run(['rofi','-dmenu','-no-custom','-format','i','-theme',
        str(Path.home()/'.config/rofi/audio.rasi')]+popup_args(420,edge_gap=8),
        input='\n'.join(rows),capture_output=True,text=True)
    if result.returncode==0:
        try:
            selected=items[int(result.stdout)]
            path=Path.home()/'.config/rice/microphone-source'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(selected['name'])
        except (ValueError,IndexError):pass


def raw_status():
    try:
        selected,recording=targets()
        if not selected:return '%{F#777777}MIC—%{F-}'
        if all(source.get('mute') for source in selected):return '%{F#777777}MIC×%{F-}'
        color='#B77B7B' if recording else '#D0D0D0'
        return '%{F'+color+'}MIC %{F-}'
    except (OSError,ValueError,subprocess.SubprocessError):
        return '%{F#777777}MIC—%{F-}'


def status():
    command='/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/microphone.py --toggle'
    choose='/usr/bin/python3 __RICE_HOME__/.config/polybar/scripts/microphone.py --choose'
    return '%{A1:'+command+':}%{A3:'+choose+':}'+raw_status()+'%{A}%{A}'


def self_test():
    selected,recording=targets()
    if recording:print('Recording active; test skipped');return
    source=selected[0]
    node=str(source.get('properties',{}).get('object.id',''))
    try:
        result=subprocess.run(['pw-cli','set-param',node,'Props','{ softMute: true }'],capture_output=True,text=True,timeout=2)
        time.sleep(.2)
        text=subprocess.run(['pw-cli','enum-params',node,'Props'],capture_output=True,text=True,timeout=2).stdout
        import re
        match=re.search(r':softMute .*?Bool (true|false)',text,re.S)
        report={'code':result.returncode,'error':result.stderr,'softMute':match.group(1) if match else 'missing'}
        (Path.home()/'.cache/rice/microphone-software-test.json').write_text(json.dumps(report))
        print('Software mute test:',report)
    finally:
        subprocess.run(['pw-cli','set-param',node,'Props','{ softMute: false }'],capture_output=True,timeout=2)


def main():
    if '--choose' in sys.argv:
        choose_source();return
    if '--self-test' in sys.argv:
        self_test();return
    if '--toggle' in sys.argv:
        selected,_=targets()
        if not selected:
            subprocess.run(['rofi','-e','Нет доступных микрофонов'],check=False)
            return
        mute=not all(source.get('mute') for source in selected)
        for source in selected:
            result=run('set-source-mute',source['name'],'1' if mute else '0')
            result.check_returncode()
        return
    if '--check' in sys.argv:
        selected,recording=targets()
        print('Microphone ready; selected:',len(selected),'recording:',recording)
        return
    while True:
        subscriber=None
        try:
            subscriber=subprocess.Popen(['pactl','subscribe'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
            previous=None
            while subscriber.poll() is None:
                label=status()
                if label!=previous:print(label,flush=True);previous=label
                if select.select([subscriber.stdout],[],[],1)[0]:
                    if not os.read(subscriber.stdout.fileno(),65536):break
        finally:
            if subscriber is not None and subscriber.poll() is None:subscriber.terminate()
        import time
        time.sleep(2)


if __name__=='__main__':
    def stop(*_):raise SystemExit
    signal.signal(signal.SIGTERM,stop)
    try:main()
    except BrokenPipeError:pass
    except Exception as error:
        log=Path.home()/'.cache/rice/microphone-error.log'
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text(str(error))
        if '--toggle' in sys.argv:
            subprocess.run(['rofi','-e','Не удалось переключить микрофон: '+str(error)],check=False)
        raise
