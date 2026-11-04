#!/usr/bin/python3
"""Bounded direct download comparison against the Yandex-provided CDN probes."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse
cache=Path.home()/'.cache/rice'
cfg=json.loads((cache/'yandex-probes.json').read_text())
urls=[p['url'] for p in cfg['download']['probes'] if '/50mb?' in p['url']][:3]
assert urls and all(urlparse(u).scheme=='https' and urlparse(u).hostname.endswith('.cdn.yandex.net') for u in urls)
def download(url):
 r=subprocess.run(['curl','-sS','--fail','--noproxy','*','--interface','eno1','--connect-timeout','4',
                   '--max-time','15','--max-filesize','60000000','-o','/dev/null','-w','%{json}',url],
                  capture_output=True,text=True,timeout=18)
 try:metrics=json.loads(r.stdout)
 except ValueError:metrics={}
 return {'metrics':metrics,'exit':r.returncode,'error':r.stderr}
t=time.monotonic()
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(download,urls))
elapsed=time.monotonic()-t
total=sum(r['metrics'].get('size_download',0) for r in results)
report={'Mbps':total*8/elapsed/1e6,'elapsed':elapsed,'bytes':total,'streams':results}
(cache/'network-direct-speed.json').write_text(json.dumps(report,indent=2))
