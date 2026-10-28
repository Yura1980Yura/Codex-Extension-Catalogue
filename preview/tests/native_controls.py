"""Opt-in integration check: real Codex, disposable configuration, no service calls."""
import sys, unittest, tomllib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_controls

class NativeSwitches(unittest.TestCase):
    setUp = test_controls.Switches.setUp
    tearDown = test_controls.Switches.tearDown
    payload = test_controls.Switches.payload
    rpc = test_controls.Switches.rpc
    def test_account_app_override_can_be_created_without_changing_other_apps(self):
        import discovery
        self.control.request=discovery.request
        component=self.snapshot['addons'][0]['components'][2]
        component['id']='app:account_only';component['config_name']='account_only'
        component['contexts']['all']['sources']=[{'scope':'account','path':'Codex app/installed'}]
        original=tomllib.loads(self.file.read_text())
        for enabled in (False,True):
            result=self.control.change(self.snapshot,self.payload(2,enabled))
            self.assertEqual(result['verification'],'codex_config_read')
        actual=tomllib.loads(self.file.read_text());self.assertTrue(actual['apps'].pop('account_only')['enabled'])
        self.assertEqual(actual,original)
    def test_codex_switches_all_three_kinds_and_preserves_permissions(self):
        import discovery
        self.control.request=discovery.request
        original=tomllib.loads(self.file.read_text())
        for index in range(3):
            with self.subTest(kind=('mcp','plugin','app')[index]):
                off=self.control.change(self.snapshot,self.payload(index))
                self.assertEqual(off['verification'],'codex_config_read')
                self.assertFalse(self.control.decorate(self.snapshot)['addons'][0]['components'][index]['contexts']['all']['enabled'])
                on=self.control.change(self.snapshot,self.payload(index,True))
                self.assertEqual(on['verification'],'codex_config_read')
        self.assertEqual(tomllib.loads(self.file.read_text()),original)
        self.assertEqual(len(self.control.journal.read_events(self.source)),6)

if __name__=='__main__':unittest.main()
