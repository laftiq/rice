#!/usr/bin/env python3
"""Restore one installer backup. Defaults to preview; edited files are protected."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def restore(backup, home, apply=False, force=False):
    backup=Path(backup).resolve();home=Path(home).expanduser().resolve()
    records=json.loads((backup/'manifest.json').read_text())
    restored=0
    for record in reversed(records):
        relative=Path(record['path'])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe manifest path')
        target=home/relative
        if not target.parent.resolve().is_relative_to(home):raise ValueError('Target parent escapes home')
        if target.is_file() and not target.is_symlink():
            current=hashlib.sha256(target.read_bytes()).hexdigest()
            if current!=record['installed_sha256'] and not force:
                print('SKIP modified:',relative);continue
        elif target.is_symlink() and not force:
            print('SKIP new symlink:',relative);continue
        print('RESTORE' if record['existed'] else 'REMOVE new file',relative)
        if not apply:continue
        if target.exists() or target.is_symlink():target.unlink()
        if record['existed']:
            target.parent.mkdir(parents=True,exist_ok=True)
            if 'symlink' in record:os.symlink(record['symlink'],target)
            else:shutil.copy2(backup/'files'/relative,target)
        restored+=1
    return restored

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('backup',type=Path,nargs='?')
    p.add_argument('--target-home',type=Path,default=Path.home())
    p.add_argument('--apply',action='store_true');p.add_argument('--force',action='store_true')
    a=p.parse_args()
    if a.backup is None:
        print('Available backups:')
        for path in sorted((a.target_home/'.local/state/laptos-rice/backups').glob('*')):print(path)
        print('Usage: rice-restore BACKUP [--apply] [--force]');return
    restore(a.backup,a.target_home,a.apply,a.force)

if __name__=='__main__':main()
