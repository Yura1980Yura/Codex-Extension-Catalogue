from pathlib import Path
import hashlib,sys,tempfile,tomllib,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config_edits import boolean_edit,write_boolean

class ConfigEdits(unittest.TestCase):
    def test_one_boolean_preserves_comments_permissions_and_multiline_values(self):
        raw=b'# Keep this comment\r\n[mcp_servers."sample.name"]\r\nenabled = true # Keep this too\r\ndefault_tools_approval_mode = "prompt"\r\ncommand = """\n[mcp_servers.fake]\nenabled = true\n"""\r\n'
        updated=boolean_edit(raw,'mcp_servers','sample.name',False)
        self.assertEqual(updated,raw.replace(b'enabled = true #',b'enabled = false #'))
        self.assertEqual(tomllib.loads(updated.decode())['mcp_servers']['sample.name']['default_tools_approval_mode'],'prompt')
    def test_missing_boolean_supported_for_tables_inline_and_dotted_keys(self):
        for text in ['[apps.sample]\nname="Keep"\n','apps={sample={name="Keep"}}\n','apps.sample.name="Keep"\n']:
            updated=boolean_edit(text.encode(),'apps','sample',False)
            self.assertEqual(tomllib.loads(updated.decode())['apps']['sample'],{'name':'Keep','enabled':False})
    def test_existing_inline_boolean_changes_no_other_values(self):
        raw=b'apps={first={enabled=true},second={enabled=true}}'
        actual=tomllib.loads(boolean_edit(raw,'apps','second',False).decode())
        self.assertTrue(actual['apps']['first']['enabled']);self.assertFalse(actual['apps']['second']['enabled'])
    def test_backup_and_stale_file_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config.toml';backup=Path(temp)/'backup/config.toml';raw=b'[apps.sample]\nenabled=true\n';path.write_bytes(raw)
            with self.assertRaises(ValueError):write_boolean(path,'apps','sample',False,'stale',backup)
            self.assertEqual(path.read_bytes(),raw);self.assertFalse(backup.exists())
            write_boolean(path,'apps','sample',False,hashlib.sha256(raw).hexdigest(),backup)
            self.assertEqual(backup.read_bytes(),raw);self.assertFalse(tomllib.loads(path.read_text())['apps']['sample']['enabled'])
