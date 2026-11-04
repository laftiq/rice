#!/usr/bin/env python3
"""Static integrity checks; no graphical session or credentials are accessed."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
errors=[];counts={'python':0,'shell':0,'xml':0,'managed':0}
for path in ROOT.rglob('*'):
 if not path.is_file() or any(p in {'.git','.build','__pycache__','.private'} for p in path.parts):continue
 try:text=path.read_text()
 except UnicodeDecodeError:continue
 relative=path.relative_to(ROOT)
 if path.suffix=='.py':
  try:ast.parse(text,filename=str(relative));counts['python']+=1
  except SyntaxError as e:errors.append(f'{relative}: {e}')
 if text.startswith(('#!/bin/sh','#!/bin/bash')):
  shell='bash' if text.startswith('#!/bin/bash') else 'sh'
  result=subprocess.run([shell,'-n',str(path)],capture_output=True,text=True)
  if result.returncode:errors.append(f'{relative}: {result.stderr}')
  counts['shell']+=1
 if path.suffix=='.xml':
  try:ET.fromstring(text);counts['xml']+=1
  except ET.ParseError as e:errors.append(f'{relative}: {e}')
 if 'dotfiles' in relative.parts:
  counts['managed']+=1
  if '/home/laptos' in text:errors.append(f'{relative}: machine-specific home path')
  for raw in re.findall(r'__RICE_HOME__/([^\s\"\'<>;:)]+)',text):
   # Shell strings may contain encoded whitespace/punctuation; only static references.
   ref=ROOT/'dotfiles'/raw
   if not ref.exists() and raw != 'Pictures/Screenshots' and not any(x in raw for x in ['$', '*','\\','/laptos-rice/backup','/laptos-rice/restore']):
    errors.append(f'{relative}: missing bundled reference {raw}')
 # Private credential formats, not variable names or API method names.
 patterns=[r'gh[pousr]_[A-Za-z0-9]{25,}',r'github_pat_[A-Za-z0-9_]{30,}',r'\b\d{7,12}:[A-Za-z0-9_-]{30,}',r'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----',r'https?://[^\s"\']+\?(?:[^\s"\']*&)?(?:token|password|secret)=[^&\s"\']+']
 if any(re.search(pattern,text) for pattern in patterns):errors.append(f'{relative}: possible credential')
for required in ['vendor/i3lock/LICENSE','vendor/i3lock/i3lock.c','vendor/i3lock/unlock_indicator.c','dotfiles/.local/share/fonts/PanelNetworkIcons.ttf']:
 if not (ROOT/required).exists():errors.append('Missing '+required)
manifest=json.loads((ROOT/'docs/snapshot-manifest.json').read_text())
for entry in manifest['files']:
 if not (ROOT/'dotfiles'/entry['path']).exists():errors.append('Snapshot file missing: '+entry['path'])
if errors:
 print('\n'.join(errors));raise SystemExit(1)
print('OK:',json.dumps(counts),'— syntax, local references, XML, known credential patterns and snapshot inventory')
