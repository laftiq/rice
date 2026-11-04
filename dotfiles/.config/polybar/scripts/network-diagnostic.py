#!/usr/bin/python3
"""One-shot, read-only diagnostics in the real desktop session."""
import json
from pathlib import Path
import subprocess
import time

report={'time':time.strftime('%Y-%m-%d %H:%M:%S')}
commands={
 'links':['ip','-j','-s','link','show'],
 'routes':['ip','-j','route','show','table','all'],
 'rules':['ip','-j','rule','show'],
 'route_probe':['ip','-j','route','get','77.88.8.8'],
 'gateway_ping':['ping','-n','-c','5','-W','1','192.168.0.1'],
 'yandex_config':['curl','-sS','--fail','--noproxy','*','--interface','eno1','--max-time','8','--max-filesize','100000','https://yandex.ru/internet/api/v0/get-probes'],
 'direct_yandex':['curl','-sS','--fail','--noproxy','*','--interface','eno1','--connect-timeout','4','--max-time','6','-o','/dev/null','-w','%{json}','https://ya.ru/'],
 'direct_msft':['curl','-sS','--fail','--noproxy','*','--interface','eno1','--connect-timeout','4','--max-time','6','-o','/dev/null','-w','%{json}','http://www.msftconnecttest.com/connecttest.txt'],
 'qdisc':['tc','-j','qdisc','show'],
 'classes':['tc','-j','class','show','dev','eno1'],
 'sockets':['ss','-tinp'],
 'processes':['ps','-eo','pid,comm,pcpu,pmem','--sort=-pcpu'],
 'network_manager':['nmcli','-f','GENERAL.DEVICE,GENERAL.STATE,GENERAL.CONNECTION,WIRED-PROPERTIES.CARRIER','device','show'],
}
for name,args in commands.items():
 try:
  result=subprocess.run(args,capture_output=True,text=True,timeout=18)
  report[name]={'code':result.returncode,'stdout':result.stdout[:60000],'stderr':result.stderr[:2000]}
 except (OSError,subprocess.TimeoutExpired) as e:report[name]={'error':str(e)}
(Path.home()/'.cache/rice/network-diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

request=Path.home()/'.cache/rice/network-direct-speed-request'
if request.exists():
    request.unlink()
    subprocess.run(['/usr/bin/python3',str(Path(__file__).with_name('network-direct-speed.py'))],timeout=22)
