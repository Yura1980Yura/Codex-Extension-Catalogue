from copy import deepcopy
import json,sys,tempfile,tomllib,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controls import Controls,Conflict,ControlError

class Switches(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.home=self.root/'home';self.work=self.root/'work';self.work.mkdir()
        self.file=self.home/'.codex/config.toml';self.file.parent.mkdir(parents=True)
        self.source=self.root/'data';self.source.mkdir()
        self.file.write_text('[mcp_servers.sample]\ncommand="unused"\nenabled=true\ndefault_tools_approval_mode="prompt"\n[plugins."sample@local"]\nenabled=true\n[apps.sample]\nenabled=true\ndefault_tools_approval_mode="prompt"\n[unrelated]\nsecret="DO_NOT_LEAK"\n',encoding='utf-8')
        self.calls=[];self.fail=None
        self.control=Controls({'home':str(self.home),'source_data':str(self.source),'runtime':str(Path(__file__).resolve().parents[2]/'app')},self.work,self.rpc)
        self.snapshot={'projects':[{'id':'p'}],'addons':[{'id':'addon','title':'Sample','skills':[],'components':[
            {'id':kind+':'+name,'kind':kind,'name':name,'config_name':name,'contexts':{'all':{'scope':'global','installed':True,'enabled':True,'sources':[{'scope':'user','applied':True,'path':str(self.file)}]}}}
            for kind,name in [('mcp','sample'),('plugin','sample@local'),('app','sample')]]}]}
    def tearDown(self):self.tmp.cleanup()
    def rpc(self,method,params,**kwargs):
        self.calls.append((method,params))
        if method=='config/read':
            return {'config':tomllib.loads(self.file.read_text()),'layers':[{'name':{'type':'user','file':str(self.file)},'version':'v1'}]},'fixture'
        if method=='config/value/write':
            if self.fail=='before':raise TimeoutError('DO_NOT_LEAK')
            field,quoted,_=params['keyPath'].split('.')
            name=json.loads(quoted);header='['+field+'.'+('"'+name+'"' if '@' in name else name)+']'
            text=self.file.read_text();start=text.index(header);end=text.find('\n[',start+1);end=len(text) if end<0 else end
            part=text[start:end].replace('enabled=true','enabled=false') if not params['value'] else text[start:end].replace('enabled=false','enabled=true')
            self.file.write_text(text[:start]+part+text[end:])
            if self.fail=='after':raise TimeoutError('DO_NOT_LEAK')
            return {'status':'ok'},'fixture'
        raise AssertionError(method)
    def payload(self,index=0,enabled=False):
        item=self.control.decorate(self.snapshot)['addons'][0]['components'][index]
        return {'id':'addon','component_id':item['id'],'revision':item['contexts']['all']['control']['revision'],'enabled':enabled}
    def test_each_kind_off_on_preserves_other_settings(self):
        original=tomllib.loads(self.file.read_text())
        for index in range(3):
            self.control.change(self.snapshot,self.payload(index))
            item=self.control.decorate(self.snapshot)['addons'][0]['components'][index]
            self.assertFalse(item['contexts']['all']['enabled'])
            self.control.change(self.snapshot,self.payload(index,True))
        self.assertEqual(tomllib.loads(self.file.read_text()),original)
        self.assertEqual(len(self.control.journal.read_events(self.source)),6)
        self.assertTrue(all('expectedVersion' in params for method,params in self.calls if method=='config/value/write'))
    def test_stale_revision_no_write(self):
        payload=self.payload();self.file.write_text(self.file.read_text()+'\n# Another editor\n')
        with self.assertRaises(Conflict):self.control.change(self.snapshot,payload)
        self.assertFalse(self.calls)
    def test_unknown_id_path_and_bad_bool_rejected(self):
        for delta in ({'component_id':'mcp:../../other'},{'id':'missing'},{'enabled':'false'},{'context':'missing'}):
            with self.assertRaises(ControlError):self.control.change(self.snapshot,{**self.payload(),**delta})
        self.assertFalse(self.calls)
    def test_browser_cannot_select_configuration_key(self):
        self.control.change(self.snapshot,{**self.payload(),'keyPath':'unrelated.secret','path':'other'})
        self.assertEqual(tomllib.loads(self.file.read_text())['unrelated']['secret'],'DO_NOT_LEAK')
    def test_project_and_managed_sources_are_not_overwritten(self):
        item=self.snapshot['addons'][0]['components'][0]['contexts']['all']
        for source in ('project','system','legacyManagedConfigTomlFromMdm'):
            item['sources']=[{'scope':source,'applied':True}]
            self.assertFalse(self.control.decorate(self.snapshot)['addons'][0]['components'][0]['contexts']['all']['control']['supported'])
    def test_lost_response_reads_committed_value_and_records_once(self):
        self.fail='after';self.control.change(self.snapshot,self.payload())
        events=self.control.journal.read_events(self.source)
        self.assertEqual(len(events),1);self.assertEqual(events[0]['kind'],'extension_activation_changed')
        self.control.recover();self.assertEqual(len(self.control.journal.read_events(self.source)),1)
    def test_failed_write_is_not_reported_as_success_or_leaked(self):
        self.fail='before'
        with self.assertRaises(ControlError) as error:self.control.change(self.snapshot,self.payload())
        self.assertNotIn('DO_NOT_LEAK',str(error.exception))
        self.assertEqual(self.control.journal.read_events(self.source)[0]['kind'],'extension_activation_unconfirmed')
        self.assertTrue(self.control.decorate(self.snapshot)['addons'][0]['components'][0]['contexts']['all']['enabled'])
    def test_recovery_records_pending_without_replaying_write(self):
        pending={'activation_id':'recover','field':'mcp_servers','name':'sample','enabled':True,'before_enabled':False}
        self.control.storage.atomic_json(self.control.pending,pending)
        self.control.recover();self.control.recover()
        self.assertFalse(self.calls);self.assertEqual(len(self.control.journal.read_events(self.source)),1)
    def test_concurrent_changes_rejected(self):
        with self.control.lock:
            with self.assertRaises(Conflict):self.control.change(self.snapshot,self.payload())
    def test_public_state_contains_no_credentials(self):
        self.assertNotIn('DO_NOT_LEAK',json.dumps(self.control.decorate(self.snapshot)))
    def test_fresh_skill_discovery_is_merged_without_losing_other_contexts(self):
        part={'id':'skill','skill_id':'s','kind':'skill','installed':False,'observations':[
            {'kind':'discovery','cwd':'game','path':'skill','at':'2026-10-28T01:00:00Z','enabled':True},
            {'kind':'discovery','cwd':'other','path':'skill','at':'2026-10-28T01:00:00Z','enabled':True}]}
        self.snapshot['addons'][0]['components']=[part]
        self.control.storage.atomic_json(self.source/'inventory.json',{'skills':{'s':{'observations':[
            {'kind':'discovery','cwd':'game','path':'skill','at':'2026-10-28T02:00:00Z','enabled':False}]}}})
        observed=self.control.decorate(self.snapshot)['addons'][0]['components'][0]['observations']
        self.assertEqual(len(observed),2)
        self.assertFalse(next(o for o in observed if o['cwd']=='game')['enabled'])
        self.assertTrue(next(o for o in observed if o['cwd']=='other')['enabled'])
    def test_confirmed_account_app_can_get_a_local_override(self):
        component=self.snapshot['addons'][0]['components'][2]
        component['id']='app:account_only';component['config_name']='account_only'
        facts=component['contexts']['all'];facts['sources']=[{'scope':'account','path':'Codex app/installed'}]
        self.assertTrue(self.control.decorate(self.snapshot)['addons'][0]['components'][2]['contexts']['all']['control']['supported'])
        facts['sources']=[]
        self.assertFalse(self.control.decorate(self.snapshot)['addons'][0]['components'][2]['contexts']['all']['control']['supported'])

if __name__=='__main__':unittest.main()
