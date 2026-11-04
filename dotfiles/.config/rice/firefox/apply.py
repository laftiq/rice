#!/usr/bin/env python3
"""Apply only visual Firefox settings to an explicitly chosen existing profile."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--profile',required=True,type=Path)
p.add_argument('--apply',action='store_true')
a=p.parse_args();profile=a.profile.expanduser().resolve()
if not profile.is_dir() or not (profile/'prefs.js').exists():p.error('Choose an existing Firefox profile directory with prefs.js')
print('Profile:',profile)
print('Close Firefox before applying. Only user.js and chrome CSS are affected.')
if not a.apply:raise SystemExit(0)
for lock in ['lock','.parentlock','parent.lock']:
 if (profile/lock).exists() or (profile/lock).is_symlink():p.error('Firefox profile appears in use. Close Firefox first.')
backup=Path.home()/'.local/state/laptos-rice/firefox'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True)
manifest={}
for name in ['user.js','chrome/userChrome.css','chrome/userContent.css']:
 src=profile/name;manifest[name]=src.exists()
 if src.exists():
  dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
prefs={'layout.css.prefers-color-scheme.content-override':0,'ui.systemUsesDarkTheme':1,'toolkit.legacyUserProfileCustomizations.stylesheets':True,'browser.uidensity':1,'browser.compactmode.show':True,'browser.tabs.tabMinWidth':100,'browser.toolbars.bookmarks.visibility':'newtab','browser.tabs.closeWindowWithLastTab':False,'browser.tabs.warnOnClose':True}
user=profile/'user.js';text=user.read_text() if user.exists() else ''
text=re.sub(r'// BEGIN LAPTOS FIREFOX STYLE.*?// END LAPTOS FIREFOX STYLE', '',text,flags=re.S)
text+='\n// BEGIN LAPTOS FIREFOX STYLE\n'+''.join('user_pref('+json.dumps(k)+', '+json.dumps(v)+');\n' for k,v in prefs.items())+'// END LAPTOS FIREFOX STYLE\n'
user.write_text(text);(profile/'chrome').mkdir(exist_ok=True)
for name in ['userChrome.css','userContent.css']:shutil.copy2(Path(__file__).parent/name,profile/'chrome'/name)
print('Applied. Backup:',backup)
