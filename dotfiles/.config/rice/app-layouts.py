#!/usr/bin/python3
"""Remember keyboard groups per application without replacing the keyboard map."""
import ctypes as C
import ctypes.util
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path

HOME=Path.home()
CONFIG=HOME/'.config/rice/app-layouts.json'
CACHE=HOME/'.cache/rice'
MEMORY=CACHE/'app-layouts-memory.json'
RUNNING=True


class Keyboard:
    def __init__(self):
        self.x=C.CDLL(ctypes.util.find_library('X11'))
        signatures={
            'XOpenDisplay':([C.c_char_p],C.c_void_p),
            'XDefaultRootWindow':([C.c_void_p],C.c_ulong),
            'XInternAtom':([C.c_void_p,C.c_char_p,C.c_int],C.c_ulong),
            'XGetWindowProperty':([C.c_void_p,C.c_ulong,C.c_ulong,C.c_long,C.c_long,C.c_int,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.POINTER(C.c_ubyte))],C.c_int),
            'XFree':([C.c_void_p],C.c_int),
            'XkbGetState':([C.c_void_p,C.c_uint,C.c_void_p],C.c_int),
            'XkbLockGroup':([C.c_void_p,C.c_uint,C.c_uint],C.c_int),
            'XFlush':([C.c_void_p],C.c_int),
            'XCloseDisplay':([C.c_void_p],C.c_int),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.x,name);fn.argtypes=args;fn.restype=result
        self.display=self.x.XOpenDisplay(None)
        if not self.display:raise RuntimeError('X11 display unavailable')
        self.handler=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p)(lambda *_:0)
        self.x.XSetErrorHandler.argtypes=[C.c_void_p]
        self.x.XSetErrorHandler(self.handler)
        self.root=self.x.XDefaultRootWindow(self.display)
        self.atoms={}

    def prop(self,wid,name):
        atom=self.atoms.setdefault(name,self.x.XInternAtom(self.display,name.encode(),False))
        actual,count,remaining=C.c_ulong(),C.c_ulong(),C.c_ulong()
        fmt=C.c_int()
        data=C.POINTER(C.c_ubyte)()
        result=self.x.XGetWindowProperty(self.display,wid,atom,0,4096,False,0,C.byref(actual),C.byref(fmt),C.byref(count),C.byref(remaining),C.byref(data))
        if result or not data:return None
        try:
            if fmt.value==8:return C.string_at(data,count.value)
            if fmt.value==32:return list(C.cast(data,C.POINTER(C.c_ulong))[:count.value])
        finally:self.x.XFree(data)

    def active(self):
        value=self.prop(self.root,'_NET_ACTIVE_WINDOW')
        if not value or not value[0]:return None
        wid=value[0]
        raw=self.prop(wid,'WM_CLASS') or b''
        names=[name.decode(errors='replace').casefold() for name in raw.split(b'\0') if name]
        if not names:return None
        if any(name in ('rofi','panelmusic','panelmusiccompact','flameshot') for name in names):return None
        return wid,names[-1],names

    def group(self):
        # XkbStateRec begins with its effective group byte; reserve more than
        # the complete structure to avoid ABI-dependent padding assumptions.
        state=C.create_string_buffer(64)
        if self.x.XkbGetState(self.display,0x0100,state)!=0:raise RuntimeError('XKB state unavailable')
        return state.raw[0]

    def select(self,group):
        if group not in (0,1):return
        if not self.x.XkbLockGroup(self.display,0x0100,group):raise RuntimeError('XKB group change rejected')
        self.x.XFlush(self.display)


def load(path,default):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return default


def save(memory):
    temporary=MEMORY.with_suffix('.tmp')
    temporary.write_text(json.dumps(memory,ensure_ascii=False,indent=2))
    temporary.replace(MEMORY)


def desired(names,memory,rules,fallback):
    for name in names:
        if name in rules:
            return {'us':0,'ru':1}.get(rules[name],0)
    return memory.get(names[-1],fallback)


def stop(*_):
    global RUNNING
    RUNNING=False


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    if '--check' in sys.argv:
        keyboard=Keyboard()
        group=keyboard.group()
        assert group in (0,1)
        assert desired(['kitty'],{'kitty':1},{'kitty':'us'},1)==0
        assert desired(['firefox'],{'firefox':1},{'kitty':'us'},0)==1
        keyboard.x.XCloseDisplay(keyboard.display)
        print('Per-app layouts: XKB available; policy checks passed')
        return
    with (CACHE/'app-layouts.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        lock.write(str(os.getpid()));lock.flush()
        keyboard=Keyboard()
        memory=load(MEMORY,{})
        memory={key:group for key,group in memory.items() if isinstance(key,str) and group in (0,1)}
        active=None
        last_group=keyboard.group()
        general=last_group
        settings=load(CONFIG,{})
        rules=settings.get('force_on_focus',{})
        mtime=CONFIG.stat().st_mtime_ns
        try:
            while RUNNING:
                now=CONFIG.stat().st_mtime_ns
                if now!=mtime:
                    mtime=now
                    settings=load(CONFIG,{})
                    rules=settings.get('force_on_focus',{})
                    active=None
                current=keyboard.active()
                group=keyboard.group()
                if current is None:
                    time.sleep(.15);continue
                wid,app,names=current
                if active is None or wid!=active[0]:
                    if active and settings.get('remember_other_apps',True):
                        memory[active[1]]=last_group
                        save(memory)
                    target=desired(names,memory,rules,general)
                    if target!=group:keyboard.select(target)
                    active=current
                    last_group=target
                    if not any(name in rules for name in names):general=target
                else:
                    if group!=last_group:
                        memory[app]=group
                        last_group=group
                        if not any(name in rules for name in names):general=group
                        save(memory)
                time.sleep(.15)
        finally:
            save(memory)
            keyboard.x.XCloseDisplay(keyboard.display)


signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
if __name__=='__main__':main()
