#!/usr/bin/env python3
"""Restore the graphite Openbox rice, with per-file backups and dry-run support."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def render(data, home):
    try:
        return data.decode().replace('__RICE_HOME__', str(home)).encode()
    except UnicodeDecodeError:
        return data

def install(home, dry_run=True, session=False, shell=False, build_locker=True):
    home = home.expanduser().resolve()
    if any(char.isspace() for char in str(home)):
        raise ValueError('Use a home path without whitespace: upstream panel commands contain shell paths.')
    if home == Path('/'):
        raise ValueError('Refusing / as target home')
    files=[]
    for source in sorted((ROOT/'dotfiles').rglob('*')):
        if not source.is_file(): continue
        relative=source.relative_to(ROOT/'dotfiles')
        if str(relative) in {'.xinitrc','.xsession'} and not session: continue
        if str(relative)=='.zshrc' and not shell: continue
        destination=home/relative
        if not destination.resolve().is_relative_to(home):
            raise ValueError('Destination symlink escapes target home: '+str(relative))
        files.append((source,relative))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=home/'.local/state/laptos-rice/backups'/stamp
    if dry_run:
        print('DRY RUN — no files or packages changed.')
        print('Target:',home,'| files:',len(files))
        for _,relative in files: print(relative)
        print('Custom locker:', 'build from source' if build_locker else 'system fallback')
        return None
    # Compile first: missing build tools must not leave a partly applied desktop.
    locker=None
    if build_locker:
        if not Path('/etc/pam.d/i3lock').is_file():
            raise ValueError('Install the distribution i3lock package first (PAM configuration required).')
        subprocess.run(['sh',str(ROOT/'scripts/build-locker.sh')],check=True)
        locker=ROOT/'.build/i3lock/i3lock'
    backup.mkdir(parents=True)
    manifest=[]
    def put(relative,data,mode):
        destination=home/relative
        if not destination.resolve().is_relative_to(home): raise ValueError('Unsafe target: '+str(relative))
        record={'path':str(relative),'existed':destination.exists() or destination.is_symlink()}
        if record['existed']:
            saved=backup/'files'/relative;saved.parent.mkdir(parents=True,exist_ok=True)
            if destination.is_symlink():
                record['symlink']=os.readlink(destination);destination.unlink()
            else: shutil.copy2(destination,saved)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data);destination.chmod(mode)
        record['installed_sha256']=digest(destination)
        manifest.append(record)
        (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        for source,relative in files:
            put(relative,render(source.read_bytes(),home),source.stat().st_mode&0o777)
        if locker:
            put(Path('.local/libexec/i3lock'),locker.read_bytes(),0o755)
        # Keep restore helpers available even if the checkout is moved or removed.
        for name in ['restore.py','backup.py']:
            put(Path('.local/share/laptos-rice')/name,(ROOT/'scripts'/name).read_bytes(),0o755)
        # Store an installed-file list for future private snapshots.
        inventory=json.dumps([record['path'] for record in manifest],indent=2)+'\n'
        put(Path('.local/share/laptos-rice/installed-files.json'),inventory.encode(),0o600)
        if home==Path.home().resolve():
            if shutil.which('fc-cache'): subprocess.run(['fc-cache','-f'],check=False)
        print('Installed. Backup:',backup)
        print('Log out and select Openbox (X11). No session has been restarted.')
        return backup
    except Exception:
        print('Restore interrupted. Per-file recovery manifest:',backup/'manifest.json',file=sys.stderr)
        raise

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Write files; default is a dry run')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--target-home',type=Path,default=Path.home())
    parser.add_argument('--with-session',action='store_true',help='Also install .xinitrc and .xsession')
    parser.add_argument('--with-shell',action='store_true',help='Also install the minimal .zshrc')
    parser.add_argument('--skip-lock-build',action='store_true',help='Use distribution i3lock fallback (different password indicator)')
    args=parser.parse_args()
    if os.geteuid()==0 and args.target_home==Path.home():parser.error('Run as the desktop user, not root.')
    install(args.target_home,not args.apply or args.dry_run,args.with_session,args.with_shell,not args.skip_lock_build)

if __name__=='__main__': main()
