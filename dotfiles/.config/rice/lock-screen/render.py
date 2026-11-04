#!/usr/bin/python3
import argparse
from pathlib import Path
import re
import subprocess
from PyQt6.QtCore import Qt,QRectF
from PyQt6.QtGui import QGuiApplication,QColor,QFont,QImage,QPainter,QPen

ROOT=Path.home()/'.config/rice/lock-screen'

def screens():
    try:
        query=subprocess.run(['xrandr','--query'],text=True,capture_output=True,check=True).stdout
        size=re.search(r'current (\d+) x (\d+)',query)
        width,height=map(int,size.groups())
        monitors=[tuple(map(int,match)) for match in re.findall(r' connected (?:primary )?(\d+)x(\d+)\+(\d+)\+(\d+)',query)]
        return width,height,monitors or [(width,height,0,0)]
    except (OSError,ValueError,AttributeError,subprocess.CalledProcessError):
        return 1920,1080,[(1920,1080,0,0)]

def render(logo,width,height,monitors):
    background=QImage(width,height,QImage.Format.Format_RGB32)
    background.fill(QColor('#000000'))
    painter=QPainter(background)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for w,h,x,y in monitors:
        cx,cy=x+w/2,y+h/2
        scale=min(1.5,max(0.7,h/1080))
        # Use the supplied ASCII artwork intact, above i3lock's input indicator.
        max_width=min(640*scale,w*0.72)
        max_height=170*scale
        icon=logo.scaled(int(max_width),int(max_height),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        painter.drawImage(QRectF(cx-icon.width()/2,cy-210*scale-icon.height()/2,icon.width(),icon.height()),icon)
    painter.end()
    return background

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--logo',default=str(ROOT/'logo.png')); parser.add_argument('--output',default=str(ROOT/'background.png'))
    args=parser.parse_args()
    app=QGuiApplication(['lock-background','-platform','offscreen'])
    logo=QImage(args.logo)
    if logo.isNull():
        raise SystemExit('Нет иконки сайта: запусти ~/.config/rice/lock-screen/setup.sh')
    width,height,monitors=screens()
    image=render(logo,width,height,monitors)
    if not image.save(args.output,'PNG'):
        raise SystemExit('Не удалось сохранить фон блокировки')

if __name__=='__main__':
    main()
