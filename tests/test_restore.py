import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
installer=module('rice_installer',ROOT/'install.py')
restorer=module('rice_restorer',ROOT/'scripts/restore.py')

class RestoreTests(unittest.TestCase):
 def test_dry_run_writes_nothing(self):
  with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
   home=Path(directory)/'fresh'
   installer.install(home,dry_run=True,build_locker=False)
   self.assertFalse(home.exists())
 def test_apply_restore_preserves_original_and_unrelated_files(self):
  with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
   home=Path(directory)
   config=home/'.config/kitty/kitty.conf';config.parent.mkdir(parents=True);config.write_text('original kitty config')
   unrelated=home/'untouched';unrelated.write_text('keep')
   backup=installer.install(home,dry_run=False,session=True,shell=True,build_locker=False)
   self.assertIn(str(home),(home/'.config/polybar/config.ini').read_text())
   self.assertNotIn('__RICE_HOME__',(home/'.config/polybar/config.ini').read_text())
   self.assertTrue((home/'.config/rice/screenshot.py').exists())
   restorer.restore(backup,home,apply=True)
   self.assertEqual(config.read_text(),'original kitty config')
   self.assertEqual(unrelated.read_text(),'keep')
   self.assertFalse((home/'.config/rice/screenshot.py').exists())
 def test_modified_files_are_not_overwritten_on_restore(self):
  with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
   home=Path(directory);backup=installer.install(home,dry_run=False,build_locker=False)
   config=home/'.config/kitty/kitty.conf';config.write_text('new personal edit')
   restorer.restore(backup,home,apply=True)
   self.assertEqual(config.read_text(),'new personal edit')
 def test_external_symlink_is_rejected(self):
  with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
   root=Path(directory);home=root/'home';home.mkdir();outside=root/'outside';outside.mkdir()
   (home/'.config').symlink_to(outside,target_is_directory=True)
   with self.assertRaises(ValueError):installer.install(home,dry_run=False,build_locker=False)
   self.assertEqual(list(outside.iterdir()),[])

if __name__=='__main__':unittest.main()
