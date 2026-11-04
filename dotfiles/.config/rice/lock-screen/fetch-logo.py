#!/usr/bin/python3
from html.parser import HTMLParser
from pathlib import Path
import os
import tempfile
from urllib.parse import urljoin
from urllib.request import Request,urlopen
from PyQt6.QtGui import QGuiApplication,QImageReader

BASE='https://laptos.fun/'
ROOT=Path.home()/'.config/rice/lock-screen'

class Icons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='link' and 'icon' in values.get('rel','').lower() and values.get('href'):
            self.links.append(urljoin(BASE,values['href']))

def fetch(url,limit):
    request=Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'identity'})
    with urlopen(request,timeout=20) as response:
        data=response.read(limit+1)
        if len(data)>limit:
            raise ValueError('Файл слишком большой')
        return data

def main():
    app=QGuiApplication(['fetch-logo','-platform','offscreen'])
    ROOT.mkdir(parents=True,exist_ok=True)
    links=[]
    errors=[]
    try:
        parser=Icons(); parser.feed(fetch(BASE,2*1024*1024).decode('utf-8','replace'))
        links=parser.links
    except Exception as error:
        errors.append(str(error))
    links=sorted(set(links),key=lambda url: ('.svg' not in url.lower(),'.png' not in url.lower()))
    links.append(urljoin(BASE,'favicon.ico'))
    for url in dict.fromkeys(links):
        try:
            data=fetch(url,5*1024*1024)
            with tempfile.NamedTemporaryFile(dir=ROOT,suffix='.img') as temporary:
                temporary.write(data); temporary.flush()
                reader=QImageReader(temporary.name)
                reader.setDecideFormatFromContent(True)
                image=reader.read()
            if image.isNull():
                raise ValueError('Иконка не распознаётся как изображение')
            if not image.save(str(ROOT/'logo.png'),'PNG'):
                raise ValueError('Не удалось сохранить иконку')
            (ROOT/'logo-source.txt').write_text(url+'\n')
            print('Скачана иконка:',url)
            return
        except Exception as error:
            errors.append(str(error))
    raise SystemExit('Не удалось скачать иконку laptos.fun: '+ '; '.join(errors[-3:]))

if __name__=='__main__':
    main()
