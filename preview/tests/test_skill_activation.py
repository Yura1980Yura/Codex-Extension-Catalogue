from pathlib import Path
import json,sys,tempfile,tomllib,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controls import Controls,Conflict

class ExactSkillActivation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.home=self.root/'home';self.profile=self.home/'.codex';self.profile.mkdir(parents=True)
        self.source=self.root/'data';self.source.mkdir();self.work=self.root/'work';self.work.mkdir();self.file=self.profile/'config.toml';self.file.write_text('')
        self.control=Controls({'home':str(self.home),'source_data':str(self.source),'runtime':str(Path(__file__).resolve().parents[2]/'app')},self.work,self.rpc)
        self.paths=[]
        for name in ['one','two']:
            path=self.root/name/'SKILL.md';path.parent.mkdir();path.write_text('---\nname: same\ndescription: Test only\n---\n');self.paths.append(path)
        self.card={'id':'vendor:test:same','name':'same','locations':[{'path':str(path),'kind':'installation','scope':'repo'} for path in self.paths],'observations':[]}
        self.control.storage.atomic_json(self.source/'inventory.json',{'skills':{self.card['id']:self.card}})
    def tearDown(self):self.temp.cleanup()
    def rpc(self,method,params,**kwargs):
        if method=='skills/config/write':
            self.file.write_text('[[skills.config]]\npath='+json.dumps(params['path'])+'\nenabled='+str(params['enabled']).lower()+'\n');return {'effectiveEnabled':params['enabled']},'fixture'
        if method=='skills/list':
            config=tomllib.loads(self.file.read_text());disabled={Path(row['path']).resolve():row['enabled'] for row in config.get('skills',{}).get('config',[])}
            return {'data':[{'cwd':str(self.home),'skills':[{'path':str(path),'enabled':disabled.get(path.resolve(),True)} for path in self.paths]}]},'fixture'
        raise AssertionError(method)
    def test_each_owner_and_scope_supports_its_selected_installation(self):
        for key in ['local:test','vendor:test','system:test','plugin:test']:
            card={**self.card,'id':key}
            self.assertFalse(self.control.activation.state(card,self.home)['supported'])
            self.assertTrue(self.control.activation.state(card,self.home,path=self.paths[0])['supported'])
            self.assertFalse(self.control.activation.state(card,self.home,path=self.root/'unknown/SKILL.md')['supported'])
    def test_switch_and_recovery_target_one_copy_not_all_same_name_skills(self):
        a=self.control.activation;revision=a.state(self.card,self.home,path=self.paths[0])['revision']
        result=a.change(self.source,self.home,self.home,self.card['id'],False,revision,request_fn=self.rpc,path=self.paths[0])
        self.assertEqual(result['verification'],'confirmed');self.assertFalse(a.state(self.card,self.home,path=self.paths[0])['enabled']);self.assertTrue(a.state(self.card,self.home,path=self.paths[1])['enabled'])
        self.assertEqual(Path(result['event']['data']['skill_path']).resolve(),self.paths[0].resolve())
        a.recover_locked(self.source,self.home);self.assertEqual(len(a.journal.read_events(self.source)),1)
    def test_changed_instruction_invalidates_a_stale_switch(self):
        a=self.control.activation;revision=a.state(self.card,self.home,path=self.paths[0])['revision'];self.paths[0].write_text('Replaced instruction')
        with self.assertRaises(a.Conflict):a.change(self.source,self.home,self.home,self.card['id'],False,revision,request_fn=self.rpc,path=self.paths[0])
        self.assertEqual(self.file.read_text(),'')
    def test_folder_override_and_exact_file_refer_to_same_skill(self):
        self.file.write_text('[[skills.config]]\npath='+json.dumps(str(self.paths[0].parent))+'\nenabled=false\n')
        self.assertFalse(self.control.activation.state(self.card,self.home,path=self.paths[0])['enabled'])
    def test_browser_path_is_ignored_and_only_selected_component_is_changed(self):
        component={'id':'chosen','kind':'skill','skill_id':self.card['id'],'scope':'local','installed':True,'path':str(self.paths[0])}
        snapshot={'projects':[],'addons':[{'id':'a','title':'Same','skills':[self.card],'components':[component]}]}
        control=self.control.decorate(snapshot)['addons'][0]['components'][0]['control']
        self.assertTrue(control['supported']);self.assertEqual(control['scope'],'installation')
        self.control.change(snapshot,{'id':'a','component_id':'chosen','enabled':False,'revision':control['revision'],'path':str(self.paths[1])})
        self.assertFalse(self.control.activation.state(self.card,self.home,path=self.paths[0])['enabled'])
        self.assertTrue(self.control.activation.state(self.card,self.home,path=self.paths[1])['enabled'])
