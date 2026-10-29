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
        self.tmp=tempfile.TemporaryDirectory(prefix='asemic-test-')
        self.home=Path(self.tmp.name)/'пользователь с пробелом';self.home.mkdir()
    def tearDown(self):self.tmp.cleanup()

    def install(self):return d.install(ROOT,home=self.home,offline=True)

    def test_install_repeat_preserves_data_and_instructions(self):
        profile=self.home/'.codex';profile.mkdir()
        instructions=profile/'AGENTS.md';instructions.write_text('Owner instructions','utf-8')
        result=self.install();runtime=Path(result['installed'])
        self.assertTrue(Path(result['launcher']).exists())
        self.assertEqual(instructions.read_text(),'Owner instructions')
        note=Path(result['notes'])/'Моё.md';note.write_text('Keep me','utf-8')
        overlay=Path(result['work'])/'annotations.json';d.write(overlay,{'custom':True})
        again=self.install();self.assertEqual(again['outcome'],'unchanged')
        self.assertEqual(note.read_text('utf-8'),'Keep me');self.assertTrue(d.read(overlay)['custom'])
        meta=d.read(Path(result['skill'])/'installation.json')
        self.assertEqual(meta['catalogue']['runtime'],str(runtime))
        self.assertEqual(meta['source_revision'],'v3.6.0')
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
        marker=d.read(runtime/'.asemic-installation.json');marker['bundle_id']='old-revision'
        d.write(runtime/'.asemic-installation.json',marker)
        newer=self.install()
        self.assertEqual(newer['outcome'],'update')
        self.assertTrue((Path(newer['program_backup'])/'launch.py').is_file())
        d.manifest(runtime)

    def test_missing_codex_does_not_replace_program(self):
        with patch('discovery.executable',side_effect=FileNotFoundError('missing')):
            with self.assertRaises(FileNotFoundError):d.install(ROOT,home=self.home)
        self.assertFalse(Path(d.locations(self.home)['runtime']).exists())

    def test_custom_profile_is_respected_for_real_home_only(self):
        custom=self.home/'custom-profile'
        with patch.dict(os.environ,{'CODEX_HOME':str(custom)}):
            self.assertEqual(d.locations()['profile'],str(custom.resolve()))
            self.assertEqual(d.locations(self.home)['profile'],str(self.home/'.codex'))

    def test_posix_launchers_quote_paths_and_mac_manifest(self):
        runtime=self.home/"Applications/L'Application $literal";runtime.mkdir(parents=True)
        assets=runtime/'assets';assets.mkdir();(assets/'asemic.icns').write_bytes(b'test')
        mac=Path(d.shortcut(runtime,self.home/'mac','darwin'))
        self.assertEqual(plistlib.loads((mac/'Contents/Info.plist').read_bytes())['CFBundleExecutable'],'launch')
        self.assertIn("'\"'\"'",(mac/'Contents/MacOS/launch').read_text())
        linux=Path(d.shortcut(runtime,self.home/'linux','linux'))
        self.assertIn('Type=Application',linux.read_text());self.assertIn('Terminal=false',linux.read_text())
        with self.assertRaises(ValueError):d.shortcut(runtime,self.home/'linux','linux')

    def test_archive_manifest_rejects_added_file(self):
        info=d.manifest(ROOT);self.assertIn('START-CODEX.txt',info['files'])
        self.assertNotIn('.local',set(Path(n).parts[0] for n in info['files']))


if __name__=='__main__':unittest.main()
