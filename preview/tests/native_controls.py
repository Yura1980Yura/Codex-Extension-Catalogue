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
    def test_codex_project_mcp_switch_preserves_user_config_and_approvals(self):
        import discovery,json
        project=self.root/'project';project.mkdir();project_file=project/'.codex/config.toml';project_file.parent.mkdir()
        project_file.write_text('[mcp_servers.sample]\ncommand="unused"\nenabled=true\ndefault_tools_approval_mode="prompt"\n[plugins."sample@local"]\nenabled=true\n[apps.sample]\nenabled=true\ndefault_tools_approval_mode="prompt"\n')
        self.file.write_text(self.file.read_text()+'\n[projects.'+json.dumps(str(project))+']\ntrust_level="trusted"\n')
        original=self.file.read_bytes();self.snapshot['projects'][0]['path']=str(project)
        self.control.request=discovery.request
        for index,(field,name) in enumerate([('mcp_servers','sample'),('plugins','sample@local'),('apps','sample')]):
            component=self.snapshot['addons'][0]['components'][index]
            component['contexts']['p']={'scope':'local','installed':True,'enabled':True,'sources':[{'scope':'project','applied':True,'path':str(project_file)}]}
            for enabled in (False,True):
                control=self.control.decorate(self.snapshot)['addons'][0]['components'][index]['contexts']['p']['control']
                result=self.control.change(self.snapshot,{'id':'addon','component_id':component['id'],'context':'p','enabled':enabled,'revision':control['revision']})
                self.assertEqual(result['verification'],'codex_config_read')
                self.assertEqual(tomllib.loads(project_file.read_text())[field][name]['enabled'],enabled)
                self.assertEqual(tomllib.loads(project_file.read_text())['mcp_servers']['sample']['default_tools_approval_mode'],'prompt')
                self.assertEqual(self.file.read_bytes(),original)
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
