from pathlib import Path
import json, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Preview, write
from project_registry import registered_projects, merge_projects
from audit import audit
from watch import signature

class Current(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.home=self.root/'home';self.home.mkdir()
        self.work=self.root/'work';self.folder=self.root/'game';self.folder.mkdir()
        write(self.work/'snapshot.json',{'addons':[{'id':'a'},{'id':'b'}],'projects':[{'id':'game','path':str(self.folder)}]})
        self.service=Preview({'home':str(self.home),'source_data':str(self.home/'data')},self.work)
    def tearDown(self):self.tmp.cleanup()
    def test_order_survives_restart_and_refresh_snapshot(self):
        self.service.reorder({'context':'game','order':['b','a'],'revision':0})
        write(self.work/'snapshot.json',{'addons':[{'id':'a'},{'id':'b'},{'id':'c'}]})
        self.assertEqual(Preview(self.service.settings,self.work).state()['overlay']['orders']['game'],['b','a'])
    def test_order_rejects_duplicates_unknown_ids_and_stale_revision(self):
        for order in (['a','a'],['not-installed']):
            with self.assertRaises(ValueError):self.service.reorder({'context':'game','order':order,'revision':0})
        self.service.reorder({'context':'game','order':['a','b'],'revision':0})
        with self.assertRaises(ValueError):self.service.reorder({'context':'game','order':['b','a'],'revision':0})
    def test_open_folder_uses_only_known_project_id(self):
        with patch('server.open_folder', return_value={'opened':True,'foreground':True}) as start:
            self.service.open_project({'id':'game','path':'C:/unrelated'})
            start.assert_called_once_with(self.folder.resolve())
            with self.assertRaises(ValueError):self.service.open_project({'id':'C:/unrelated'})
    def test_names_follow_codex_without_merging_distinct_folders(self):
        write(self.home/'.codex/.codex-global-state.json',{'local-projects':{'x':{'name':'Game','rootPaths':[str(self.folder),'C:/other-access']}}})
        registry,warning=registered_projects(self.home,lambda p:'game')
        self.assertIsNone(warning)
        merged=merge_projects([{'id':'old','name':'Old label','path':str(self.folder)},{'id':'other','name':'Game','path':str(self.root/'other')}],registry)
        self.assertEqual(len(merged),1);self.assertEqual(merged[0]['name'],'Game');self.assertEqual(merged[0]['source'],'codex')
        self.assertEqual(merge_projects(merged, []), [])
        self.assertEqual(registry[0]['additional_folders'],['C:/other-access'])

    def test_folder_request_does_not_invent_foreground_confirmation(self):
        with patch('server.open_folder',return_value={'opened':True,'foreground':None,'confirmation':'launch only'}):
            result=self.service.open_project({'id':'game'})
        self.assertIsNone(result['foreground']);self.assertEqual(result['confirmation'],'launch only')
    def test_signature_detects_install_remove_and_rename_but_not_chat_activity(self):
        settings=self.service.settings
        a=signature(settings,self.work)
        skill=self.home/'.agents/skills/new/SKILL.md';skill.parent.mkdir(parents=True);skill.write_text('new')
        b=signature(settings,self.work);self.assertNotEqual(a,b)
        skill.unlink();self.assertEqual(signature(settings,self.work),a)
        state=self.home/'.codex/.codex-global-state.json'
        write(state,{'local-projects':{'x':{'name':'One','rootPaths':[str(self.folder)]}},'chat':'one'})
        c=signature(settings,self.work)
        write(state,{'local-projects':{'x':{'name':'One','rootPaths':[str(self.folder)]}},'chat':'two'})
        self.assertEqual(signature(settings,self.work),c)
        write(state,{'local-projects':{'x':{'name':'Two','rootPaths':[str(self.folder)]}}})
        self.assertNotEqual(signature(settings,self.work),c)
    def test_audit_does_not_declare_completeness_when_source_failed(self):
        r=audit({'skills':{},'discovery_status':'unavailable'},{'all':{'status':'fallback','apps_status':'unavailable'}},[],{},[])
        self.assertFalse(r['complete']);self.assertIn('skills/list',r['source_failures'])
    def test_audit_detects_unrepresented_skill_and_duplicate_component(self):
        file=str(self.folder/'SKILL.md')
        r=audit({'skills':{'a':{'locations':[{'kind':'user','path':file}]}},'discovery_status':'ok'}, {},[{'components':[{'id':'same'},{'id':'same'}]}],{},[])
        self.assertEqual(len(r['missing_skill_paths']),1);self.assertEqual(r['duplicate_component_ids'],['same']);self.assertFalse(r['complete'])

if __name__=='__main__':unittest.main()
