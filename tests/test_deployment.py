"""Deployment boundaries: repeatability, user data, profile and real launchers."""
from pathlib import Path
import json
import os
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import deployment as d


class Deployment(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='catalogue-test-')
        self.home=(Path(self.tmp.name)/'пользователь с пробелом').resolve();self.home.mkdir()
    def tearDown(self):self.tmp.cleanup()

    def install(self):return d.install(ROOT,home=self.home,offline=True)

    def test_install_repeat_preserves_data_and_instructions(self):
        profile=self.home/'.codex';profile.mkdir()
        instructions=profile/'AGENTS.md';instructions.write_text('Owner instructions','utf-8')
        result=self.install();runtime=Path(result['installed'])
        self.assertTrue(Path(result['launcher']).exists())
        if sys.platform=='win32':
            from windows_shortcut import inspect
            link=inspect(result['launcher'])
            self.assertTrue(Path(link['target']).is_file())
            self.assertIn(str(runtime/'launch.py'),link['arguments'])
        self.assertEqual(instructions.read_text(),'Owner instructions')
        note=Path(result['notes'])/'Моё.md';note.write_text('Keep me','utf-8')
        overlay=Path(result['work'])/'annotations.json';d.write(overlay,{'custom':True})
        again=self.install();self.assertEqual(again['outcome'],'unchanged')
        self.assertEqual(note.read_text('utf-8'),'Keep me');self.assertTrue(d.read(overlay)['custom'])
        meta=d.read(Path(result['skill'])/'installation.json')
        self.assertEqual(meta['catalogue']['runtime'],str(runtime))
        self.assertEqual(meta['source_revision'],'v'+d.read(ROOT/'release.json')['version'])
        self.assertFalse((runtime/'.codex').exists())

    def test_modified_program_skill_or_shortcut_is_not_overwritten(self):
        result=self.install();runtime=Path(result['installed'])
        file=runtime/'launch.py';original=file.read_bytes();file.write_bytes(original+b'\n# user')
        with self.assertRaises(ValueError):self.install()
        file.write_bytes(original)
        extra=Path(result['skill'])/'my-file.md';extra.write_text('Mine')
        with self.assertRaises(ValueError):self.install()
        extra.unlink()
        link=Path(result['launcher'])
        if link.is_file():
            link.write_bytes(b'Modified')
            with self.assertRaises(ValueError):self.install()

    def test_update_keeps_old_program_and_reuses_known_shortcut(self):
        result=self.install();runtime=Path(result['installed'])
        marker=d.read(runtime/d.MARKER);marker['bundle_id']='old-revision'
        d.write(runtime/d.MARKER,marker)
        newer=self.install()
        self.assertEqual(newer['outcome'],'update')
        self.assertTrue((Path(newer['program_backup'])/'launch.py').is_file())
        d.manifest(runtime)

    def test_missing_codex_does_not_replace_program(self):
        with patch('discovery.executable',side_effect=FileNotFoundError('missing')):
            with self.assertRaises(FileNotFoundError):d.install(ROOT,home=self.home)
        self.assertFalse(Path(d.locations(self.home)['runtime']).exists())

    def test_legacy_name_upgrade_keeps_paths_and_data_and_renames_launcher(self):
        result=self.install();runtime=Path(result['installed']);work=Path(result['work'])
        meta=d.installation(runtime)
        legacy_runtime=runtime.with_name('Asemic-Catalogue')
        legacy_work=work.with_name('asemic-catalogue-current')
        legacy_link=Path(result['launcher']).with_name('Asemic Catalogue'+Path(result['launcher']).suffix)
        Path(result['launcher']).rename(legacy_link);work.rename(legacy_work)
        d.write(legacy_work/'annotations.json',{'custom':'Keep all annotations'})
        note=Path(result['notes'])/'Моя заметка.md';note.write_text('Keep notes','utf-8')
        meta.update(application='asemic-catalogue',product='Asemic Catalogue',runtime=str(legacy_runtime),work=str(legacy_work),shortcut=str(legacy_link))
        (runtime/d.MARKER).unlink();d.write(runtime/d.LEGACY_MARKER,meta);runtime.rename(legacy_runtime)
        upgraded=self.install()
        self.assertEqual(upgraded['outcome'],'update')
        self.assertEqual(upgraded['installed'],str(legacy_runtime));self.assertEqual(upgraded['work'],str(legacy_work))
        self.assertEqual(d.read(legacy_work/'annotations.json'),{'custom':'Keep all annotations'})
        self.assertEqual(note.read_text('utf-8'),'Keep notes')
        self.assertFalse(legacy_link.exists());self.assertTrue(Path(upgraded['previous_launcher_backup']).exists())
        self.assertEqual(Path(upgraded['launcher']).stem,d.NAME)
        self.assertEqual(d.installation(legacy_runtime)['developer'],'55user3125')
        self.assertEqual(d.installation(legacy_runtime)['product'],'Codex Extension Catalogue')
        self.assertEqual(self.install()['outcome'],'unchanged')

    def test_unmanaged_legacy_folder_is_preserved(self):
        legacy=self.home/'Applications/Asemic-Catalogue';legacy.mkdir(parents=True)
        mine=legacy/'owner.txt';mine.write_text('Keep my folder')
        result=self.install()
        self.assertEqual(Path(result['installed']).name,'Codex-Extension-Catalogue')
        self.assertEqual(mine.read_text(),'Keep my folder')

    def test_custom_profile_is_respected_for_real_home_only(self):
        custom=self.home/'custom-profile'
        # This profile test must not read the developer machine's installed marker.
        with patch.dict(os.environ,{'CODEX_HOME':str(custom)}), patch('deployment.installation',return_value=None):
            self.assertEqual(d.locations()['profile'],str(custom.resolve()))
            self.assertEqual(d.locations(self.home)['profile'],str(self.home/'.codex'))

    def test_posix_launchers_quote_paths_and_mac_manifest(self):
        runtime=self.home/"Applications/L'Application $literal";runtime.mkdir(parents=True)
        assets=runtime/'assets';assets.mkdir();(assets/'catalogue.icns').write_bytes(b'test')
        mac=Path(d.shortcut(runtime,self.home/'mac','darwin'))
        self.assertEqual(plistlib.loads((mac/'Contents/Info.plist').read_bytes())['CFBundleExecutable'],'launch')
        self.assertIn("'\"'\"'",(mac/'Contents/MacOS/launch').read_text())
        linux=Path(d.shortcut(runtime,self.home/'linux','linux'))
        self.assertIn('Type=Application',linux.read_text());self.assertIn('Terminal=false',linux.read_text())
        self.assertIn(r'\\$literal',linux.read_text())
        with self.assertRaises(ValueError):d.shortcut(runtime,self.home/'linux','linux')

    def test_archive_manifest_rejects_added_file(self):
        info=d.manifest(ROOT);self.assertIn('START-CODEX.txt',info['files'])
        self.assertNotIn('.local',set(Path(n).parts[0] for n in info['files']))


if __name__=='__main__':unittest.main()
