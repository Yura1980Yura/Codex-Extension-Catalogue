from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'app'
sys.path[:0]=[str(ROOT/'skill-catalog/scripts')]
import resources as r
import organization as o
import directions
from storage import atomic_json,read_json

class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name);self.data=self.home/'.codex/skill-catalog';self.pid='project:demo'
        self.user={'schema':1,'skills':{'pdf':{'notes':['Сохранить мою заметку']}},'unrelated':{'keep':True},'project_catalog':{'schema':1,'projects':{self.pid:{'name':'Demo','path':str(self.home/'Demo'),'recommendations':[],'applications':[]}}}}
        self.inventory={'skills':{'pdf':{'id':'pdf','name':'pdf','origin':'builtin','state':'present','tasks':[]}}}
        atomic_json(self.data/'user.json',self.user);atomic_json(self.data/'inventory.json',self.inventory)
        self.config=self.home/'.codex/config.toml';self.config.write_text('unchanged=true\n','utf-8');self.before=self.config.read_bytes()
        self.cards=[{**self.inventory['skills']['pdf'],'activation':{'enabled':True}}]
        self.observed={'services':[],'projects':[{'id':self.pid,'name':'Demo','path':str(self.home/'Demo')}],'checked_at':'2026-10-27','source':'test','warning':None}
        self.p1=patch.object(r.connections,'view',side_effect=lambda *a,**kw:deepcopy(self.observed));self.p1.start();self.addCleanup(self.p1.stop)
        self.p2=patch.object(r.catalog,'load_cards',side_effect=lambda *a,**kw:(self.inventory,deepcopy(self.cards)));self.p2.start();self.addCleanup(self.p2.stop)

    def item(self,cid,kind='plugin'):
        return {'id':cid,'name':cid,'kind':kind,'configured':True,'enabled':True,'sources':[],'profile':r.service_profiles.describe({'id':cid,'name':cid}),'connection':{'state':'needs_check','label':'Требует проверки','reason':'test'}}

    def view(self):return r.view(self.data,self.home)

    def change(self,**request):
        return r.change(self.data,self.home,{'revision':self.view()['revision'],'request_id':'resource_test_01',**request})

    def test_components_do_not_create_account_connections(self):
        self.observed['services']=[self.item('plugin:browser@openai-bundled'),self.item('plugin:unified-computer-use@openai-bundled')]
        view=self.view();browser=next(x for x in view['resources'] if x['id']=='resource:browser')
        self.assertEqual(len(browser['components']),2);self.assertEqual(browser['connections'],[])
        self.assertEqual(view['connection_count'],0)

    def test_local_capability_and_cloud_connection_have_separate_evidence(self):
        cloud=self.item('service:cloudflare','mcp');cloud['connection']={'state':'connected','label':'Подключено','reason':'OAuth verified'}
        self.observed['services']=[cloud]
        view=self.view();pdf=next(x for x in view['resources'] if x['id']=='resource:pdf');cf=next(x for x in view['resources'] if x['id']=='resource:cloudflare')
        self.assertEqual(pdf['availability']['label'],'Доступен навык');self.assertEqual(pdf['connections'],[])
        self.assertEqual(len(cf['connections']),1);self.assertEqual(cf['availability']['state'],'connected')

    def test_project_link_requires_evidence_for_actual_integration(self):
        with self.assertRaises(ValueError):self.change(action='bind',id='resource:pdf',project_id=self.pid,role='runtime',purpose='PDF export')
        self.change(action='bind',id='resource:pdf',project_id=self.pid,role='recommended',purpose='Подготовка отчётов',policy='explicit')
        saved=read_json(self.data/'user.json');self.assertEqual(saved['unrelated'],self.user['unrelated']);self.assertEqual(saved['skills'],self.user['skills'])
        binding=saved[r.KEY]['bindings'][self.pid]['resource:pdf'];self.assertFalse(binding['confirmed'])
        self.assertEqual(binding['role'],'recommended');self.assertEqual(self.config.read_bytes(),self.before)

    def test_profile_can_change_facets_but_not_connection_state(self):
        self.change(action='profile',id='resource:pdf',profile={'title':'PDF задачи','provider':'OpenAI','origin':'builtin','description':'Отчёты','capabilities':['Чтение'],'resource_kind':'builtin','billing':'included','direction_ids':['documents'],'tags':['PDF'],'status':'disabled'})
        pdf=next(x for x in self.view()['resources'] if x['id']=='resource:pdf')
        self.assertEqual(pdf['profile']['title'],'PDF задачи');self.assertEqual(pdf['tags'],['PDF'])
        self.assertEqual(pdf['availability']['state'],'connected');self.assertEqual(self.config.read_bytes(),self.before)

    def test_migration_is_repeatable_and_preserves_explicit_choices(self):
        self.inventory['skills']['zoo']={'id':'zoo','name':'zoo-cafe','origin':'unknown','state':'present','tasks':[]}
        self.inventory['skills']['blender']={'id':'blender','name':'blender-image-to-3d','origin':'unknown','state':'present','tasks':[]}
        atomic_json(self.data/'inventory.json',self.inventory)
        result=o.migrate(self.data);self.assertTrue(result['saved'])
        saved=read_json(self.data/'user.json');self.assertEqual(saved['skills']['pdf']['notes'],['Сохранить мою заметку'])
        self.assertEqual(saved['skills']['zoo']['origin'],'personal');self.assertEqual(saved['skills']['blender']['origin'],'third_party')
        self.assertTrue(all(saved['directions']['assignments'].get(key) for key in self.inventory['skills']))
        self.assertTrue(o.migrate(self.data)['unchanged']);self.assertEqual(self.config.read_bytes(),self.before)

    def test_migration_preserves_saved_empty_directions(self):
        self.user['directions']={'schema':1,'items':[{'id':'documents','title':'Документы'}],'assignments':{'pdf':[]}}
        atomic_json(self.data/'user.json',self.user)
        o.migrate(self.data)
        self.assertEqual(read_json(self.data/'user.json')['directions']['assignments']['pdf'],[])

    def test_migration_preserves_explicit_unknown_origin(self):
        self.inventory['skills']['pdf'].update(name='blender-image-to-3d',origin='unknown')
        self.user['skills']['pdf'].update(origin='unknown',origin_evidence='Выбор пользователя')
        atomic_json(self.data/'user.json',self.user);atomic_json(self.data/'inventory.json',self.inventory)
        o.migrate(self.data)
        saved=read_json(self.data/'user.json')['skills']['pdf']
        self.assertEqual(saved['origin'],'unknown')
        self.assertEqual(saved['origin_evidence'],'Выбор пользователя')

    def test_skill_resource_edit_preserves_notes_and_checks_revision(self):
        before=o.skill_metadata(self.inventory['skills']['pdf'],self.user)
        o.change_skill(self.data,{'skill_id':'pdf','revision':before['revision'],'tags':['Отчёт'],'resource_ids':['resource:pdf']})
        saved=read_json(self.data/'user.json');self.assertEqual(saved['skills']['pdf']['notes'],['Сохранить мою заметку'])
        with self.assertRaises(directions.Conflict):o.change_skill(self.data,{'skill_id':'pdf','revision':before['revision'],'tags':['Другое'],'resource_ids':[]})

    def test_inventory_project_gets_recommendations_without_false_runtime_claims(self):
        path=str(self.home/'Rea');self.inventory['projects']=[path]
        atomic_json(self.data/'inventory.json',self.inventory)
        o.migrate(self.data);saved=read_json(self.data/'user.json')
        links=saved[r.KEY]['bindings'][r.connections.project_id(path)]
        self.assertEqual(set(links),{'resource:rea','resource:catalog','resource:github'})
        self.assertTrue(all(x['role']=='recommended' and not x['confirmed'] for x in links.values()))
        self.assertNotIn(r.connections.project_id(path),saved['project_catalog']['projects'])

    def test_resource_change_retry_is_idempotent_and_conflicting_retry_rejected(self):
        request={'action':'bind','id':'resource:pdf','project_id':self.pid,'role':'runtime','purpose':'Экспорт отчёта','confirmed':True,'evidence':'reports/export.py','policy':'explicit','revision':self.view()['revision'],'request_id':'resource_retry_01'}
        r.change(self.data,self.home,request)
        self.assertTrue(r.change(self.data,self.home,request)['replayed'])
        with self.assertRaises(directions.Conflict):r.change(self.data,self.home,{**request,'purpose':'Изменённый запрос'})
        self.assertEqual(self.config.read_bytes(),self.before)

    def test_export_keeps_resource_links_and_excludes_runtime_config(self):
        import exporter
        self.change(action='bind',id='resource:pdf',project_id=self.pid,role='recommended',purpose='Подготовка отчётов',policy='explicit')
        with patch('catalog.load_cards',return_value=({'updated_at':None,'skills':{}},[])):
            views,_=exporter.build_views(self.data,[])
        self.assertEqual(len(views),5)
        self.assertIn('Подготовка отчётов',views['Сервисы и подключения.md'])
        self.assertIn('Рекомендован',views['Сервисы и подключения.md'])
        self.assertNotIn('unchanged=true',''.join(views.values()))

if __name__=='__main__':unittest.main()
