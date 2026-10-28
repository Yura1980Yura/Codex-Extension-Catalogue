from pathlib import Path
import json, sys, tempfile, unittest, threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from skill_sources import definitions, scan, integrate, change, settings_view, canonical
from server import Preview, write, read
from watch import signature


class SkillSources(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.home.mkdir()
        self.game=self.root/'game';self.game.mkdir();self.work=self.root/'work'
        self.project={'id':'game','codex_id':'stable','path':str(self.game),'name':'Игра'}
        self.settings={'home':str(self.home),'source_data':str(self.root/'data')}
        self.overlay={'revision':0,'items':{},'events':[]}

    def skill(self,root,name='sample'):
        path=root/name/'SKILL.md';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('---\nname: '+name+'\ndescription: Проверяет интерфейс\n---\n# Инструкция\n',encoding='utf-8')
        return path

    def rows(self): return definitions(self.settings,[self.project],self.overlay)
    def add(self,path,scope='global'):
        self.overlay['skill_sources']=change(self.overlay,{'action':'save','path':str(path),'scope':scope,'project_id':'game'},[self.project])
    def result(self,addons=None):
        result,docs=scan(self.rows()); instructions={}; addons=addons if addons is not None else []
        integrate(addons,[self.project],result['rows'],docs,instructions)
        return result,addons,instructions

    def test_standard_roots_and_explicit_project_folder(self):
        selected=self.root/'selected';selected.mkdir();self.skill(selected/'.agents/skills','local')
        self.overlay['project_folders']={'codex:stable':{'path':str(selected)}}
        result,addons,_=self.result()
        self.assertTrue(any(r['scope']=='local' and len(r['files'])==1 for r in result['rows']))
        self.assertEqual(addons[0]['components'][0]['project_ids'],['game'])
        self.assertEqual(self.project['path'],str(self.game))

    def test_file_does_not_confer_installation_enablement_or_experience(self):
        path=self.skill(self.root/'custom');self.add(path.parent.parent)
        result,addons,instructions=self.result();c=addons[0]['components'][0]
        self.assertFalse(c['installed']);self.assertIsNone(c['enabled']);self.assertTrue(c['file_found'])
        self.assertNotIn('verified_experience',addons[0]['skills'][0]);self.assertIn(c['skill_id'],instructions)
        self.assertEqual(result['rows'][-1]['files'][0]['availability'],'unconfirmed')

    def test_overlapping_sources_share_one_component_but_preserve_provenance(self):
        path=self.skill(self.home/'.agents/skills');self.add(path.parent)
        _,addons,_=self.result();self.assertEqual(len(addons),1)
        self.assertEqual(len(addons[0]['components'][0]['search_sources']),2)

    def test_same_names_in_different_files_are_not_merged(self):
        self.skill(self.root/'one');self.skill(self.root/'two');self.add(self.root/'one');self.add(self.root/'two')
        _,addons,_=self.result();self.assertEqual(len(addons),2)
        self.assertNotEqual(addons[0]['id'],addons[1]['id'])

    def test_existing_component_retains_group_state_and_context_evidence(self):
        path=self.skill(self.game/'.agents/skills')
        c={'id':'known','kind':'skill','path':str(path),'installed':True,'enabled':False,'scope':'local',
           'observations':[{'kind':'discovery','cwd':str(self.game),'enabled':False}]}
        addon={'id':'bundle','components':[c]};result,addons,_=self.result([addon])
        self.assertEqual(len(addons),1);self.assertFalse(c['enabled']);self.assertTrue(c['installed'])
        row=next(r for r in result['rows'] if r['files'])
        self.assertEqual(row['files'][0]['availability'],'disabled')

    def test_other_project_observation_is_not_project_confirmation(self):
        path=self.skill(self.game/'.agents/skills')
        c={'id':'known','kind':'skill','path':str(path),'scope':'local','observations':[{'kind':'discovery','cwd':str(self.home),'enabled':True}]}
        result,_,_=self.result([{'id':'bundle','components':[c]}])
        self.assertEqual(next(r for r in result['rows'] if r['files'])['files'][0]['availability'],'unconfirmed')

    def test_plugin_cache_does_not_create_installed_addons(self):
        self.skill(self.home/'.codex/plugins/cache/vendor/plugin/1/skills')
        result,addons,_=self.result();self.assertEqual(len(addons),1)
        self.assertFalse(addons[0]['components'][0]['installed'])
        self.assertTrue(addons[0]['components'][0]['managed_package'])
        self.assertEqual(next(r for r in result['rows'] if r['files'])['files'][0]['availability'],'cache')

    def test_disabled_missing_empty_and_invalid_are_distinguished(self):
        empty=self.root/'empty';empty.mkdir();self.add(empty)
        result,_,_=self.result();self.assertEqual(result['rows'][-1]['status'],'empty')
        self.overlay['skill_sources'][0]['enabled']=False
        self.assertEqual(self.result()[0]['rows'][-1]['status'],'disabled')
        self.overlay['skill_sources'][0]['enabled']=True;empty.rmdir()
        self.assertEqual(self.result()[0]['rows'][-1]['status'],'missing')
        empty.write_text('file');self.assertEqual(self.result()[0]['rows'][-1]['status'],'invalid')

    def test_invalid_instruction_and_build_tree_are_not_imported(self):
        custom=self.root/'custom';self.skill(custom/'node_modules');p=self.skill(custom,'bad');p.write_text('# no metadata')
        self.add(custom);result,addons,_=self.result();self.assertFalse(addons)
        row=result['rows'][-1];self.assertEqual(row['status'],'partial');self.assertEqual(len(row['files']),1)

    def test_aliases_resolve_without_duplicates_and_cycles_stop(self):
        path=self.skill(self.root/'custom');self.add(path.parent.parent)
        alias=self.root/'alias'
        try: alias.symlink_to(path.parent.parent,target_is_directory=True)
        except OSError: self.skipTest('Symlink creation unavailable')
        with self.assertRaises(ValueError):self.add(alias)
        (path.parent/'cycle').symlink_to(path.parent.parent,target_is_directory=True)
        _,addons,_=self.result();self.assertEqual(len(addons),1)

    def test_source_edits_persist_with_history_and_revision_protection(self):
        path=self.skill(self.root/'custom');write(self.work/'snapshot.json',{'projects':[self.project],'addons':[]})
        service=Preview(self.settings,self.work)
        request={'action':'save','path':str(path.parent),'scope':'global','revision':0}
        with patch.object(service,'refresh') as refresh:
            state=service.set_skill_sources(request);refresh.assert_not_called()
            self.assertEqual(state['overlay']['revision'],1)
            self.assertEqual(state['overlay']['events'][0]['kind'],'preview_skill_sources')
            with self.assertRaises(ValueError):service.set_skill_sources({**request,'path':str(self.root)})
            again=service.set_skill_sources({**request,'id':state['overlay']['skill_sources'][0]['id'],'revision':1})
            self.assertEqual(again['overlay']['revision'],1)
            rid=again['overlay']['skill_sources'][0]['id']
            service.set_skill_sources({'action':'remove','id':rid,'revision':1})
        self.assertTrue(path.exists());self.assertEqual(read(self.work/'annotations.json')['skill_sources'],[])
        self.assertEqual(Preview(self.settings,self.work).state()['overlay']['revision'],2)

    def test_invalid_inputs_cannot_mutate_standard_roots(self):
        for payload in [{'action':'save','path':'relative','scope':'global'}, {'action':'save','path':str(self.game),'scope':'local','project_id':'missing'}, {'action':'remove','id':self.rows()[0]['id']}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):change(self.overlay,payload,[self.project])
        self.assertNotIn('skill_sources',self.overlay)

    def test_pending_results_and_watcher_follow_changes(self):
        path=self.skill(self.root/'custom');self.add(path.parent.parent)
        snapshot={'projects':[self.project],'skill_sources':self.result()[0]}
        self.assertFalse(settings_view(self.settings,[self.project],self.overlay,snapshot)['pending'])
        self.overlay['skill_sources'][0]['enabled']=False
        self.assertTrue(settings_view(self.settings,[self.project],self.overlay,snapshot)['pending'])
        self.overlay['skill_sources'][0]['enabled']=True;write(self.work/'annotations.json',self.overlay)
        a=signature(self.settings,self.work);path.write_text('changed');b=signature(self.settings,self.work)
        self.assertNotEqual(a,b);path.unlink();self.assertNotEqual(signature(self.settings,self.work),b)

    def test_local_custom_source_follows_stable_project_identity(self):
        self.skill(self.root/'custom');self.add(self.root/'custom','local')
        self.project.update(id='renamed',name='Новое имя')
        row=self.rows()[-1];self.assertEqual(row['project_id'],'renamed');self.assertEqual(row['project_name'],'Новое имя')

    def test_global_status_does_not_borrow_another_projects_enabled_flag(self):
        path=self.skill(self.home/'.agents/skills')
        c={'id':'known','kind':'skill','path':str(path),'scope':'global','observations':[
            {'kind':'discovery','cwd':str(self.home),'enabled':False},
            {'kind':'discovery','cwd':str(self.game),'enabled':True}]}
        result,_,_=self.result([{'id':'bundle','components':[c]}])
        self.assertEqual(next(r for r in result['rows'] if r['files'])['files'][0]['availability'],'disabled')

    def test_refresh_requested_during_collection_runs_again(self):
        service=Preview(self.settings,self.work)
        entered,release,again=threading.Event(),threading.Event(),threading.Event()
        calls=[]
        def collect_again(*args):
            calls.append(True)
            if len(calls)==1: entered.set();release.wait(3)
            else: again.set()
            return {'updated_at':'test'}
        with patch('server.collect',side_effect=collect_again):
            service.refresh();self.assertTrue(entered.wait(2))
            service.refresh();release.set();self.assertTrue(again.wait(2))
        self.assertEqual(len(calls),2)

    def test_http_reports_actionable_path_validation_without_writing(self):
        import re, urllib.request, urllib.error
        from server import make_server
        write(self.work/'snapshot.json',{'projects':[self.project],'addons':[]})
        service=Preview(self.settings,self.work);http=make_server(service,0)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(http.server_port)
            html=urllib.request.urlopen(url).read().decode()
            token=re.search('name="catalog-token" content="([^"]+)"',html)[1]
            request=urllib.request.Request(url+'/api/skill-sources',data=json.dumps({'action':'save','path':'relative','scope':'global','revision':0}).encode(),headers={'Content-Type':'application/json','X-Catalog-Token':token})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,400)
            self.assertIn('абсолютным путём',json.loads(error.exception.read())['error'])
            self.assertFalse((self.work/'annotations.json').exists())
        finally:http.shutdown();http.server_close();thread.join(2)

if __name__=='__main__':unittest.main()
