#!/usr/bin/env python3
"""Create a private local snapshot of files managed by laptos-rice."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import tarfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--target-home',type=Path,default=Path.home())
a=p.parse_args();home=a.target_home.expanduser().resolve()
files=json.loads((home/'.local/share/laptos-rice/installed-files.json').read_text())
folder=home/'.local/state/laptos-rice/snapshots';folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
archive=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.tar.gz')
with tarfile.open(archive,'w:gz',dereference=False) as tar:
 for name in files:
  relative=Path(name)
  if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe inventory path')
  source=home/relative
  if source.is_file() and source.resolve().is_relative_to(home):tar.add(source,arcname=str(relative),recursive=False)
archive.chmod(0o600)
print('Private local snapshot:',archive)
