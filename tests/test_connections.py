import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]/"app"
sys.path[:0] = [str(ROOT/"skill-catalog/scripts"), str(ROOT/"manager")]
import connections as c
import journal
from storage import atomic_json


class ConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data = self.home/".codex/skill-catalog"
        self.project = self.home/"Game"
        self.project.mkdir()
        self.pid = c.project_id(self.project)
        self.user = {"schema": 1, "skills": {"existing": {"notes": ["keep"]}}, "unrelated": {"preserve": True}, "project_catalog": {"schema": 1, "projects": {self.pid: {"name": "Game", "path": str(self.project), "recommendations": [], "applications": []}}}}
        atomic_json(self.data/"user.json", self.user)
        atomic_json(self.data/"inventory.json", {"projects": [str(self.project)]})
        self.config = self.home/".codex/config.toml"
        self.config.write_text('[mcp_servers.existing]\ncommand="node"\n', 'utf-8')
        self.before = self.config.read_bytes()
        self.calls = []

    def rpc(self, method, params, *args, **kwargs):
        self.calls.append((method, params, kwargs))
        if method == 'app/installed':
            return {'apps':[{'id':'demo','runtimeName':'Example App','enabled':True,'callable':True,'token':'SECRET_APP'}]}, 'test'
        config = {"mcp_servers": {"existing": {"command": "node", "args": ["SECRET_ARG"], "env": {"API_KEY": "SECRET_ENV"}, "http_headers": {"Authorization": "SECRET_HEADER"}}}, "plugins": {"example@local": {"enabled": False}}, "apps": {"_default": {"enabled": True}}}
        if params.get('cwd') == str(self.project):
            config['mcp_servers']['existing']['enabled'] = False
        if method == 'mcpServerStatus/list':
            return {"data": [{"name": "existing", "tools": {"read": {"description": "SECRET_DESCRIPTION"}}, "authStatus": "unsupported", "toolsError": None}]}, 'test'
        return {"config": config, "layers": [{"name": {"type": "user", "file": str(self.config)}, "config": config}]}, 'test'

    def view(self, project=None):
        return c.view(self.data, self.home, project, self.rpc)

    def change(self, **fields):
        return c.change(self.data, self.home, {"action": "annotate", "id": "service:meshy", "revision": self.view()['revision'], "request_id": "request_0001", **fields}, self.rpc)

    def test_secret_free_effective_config_and_project_context(self):
        global_view = self.view()
        raw = json.dumps(global_view)
        self.assertNotIn('SECRET', raw)
        self.assertNotIn('_default', raw)
        self.assertTrue(next(x for x in global_view['services'] if x['id']=='app:demo')['callable'])
        self.assertTrue(next(x for x in global_view['services'] if x['id']=='mcp:existing')['enabled'])
        self.assertFalse(next(x for x in self.view(self.pid)['services'] if x['id']=='mcp:existing')['enabled'])
        self.assertTrue(any(params.get('cwd')==str(self.project) for _,params,_ in self.calls))
        self.assertEqual(self.before, self.config.read_bytes())

    def test_meshy_preparation_never_calls_meshy_or_accepts_key(self):
        self.assertFalse(c.meshy_plan(self.home)['credential_input_available'])
        self.assertEqual(c.meshy_plan(self.home)['status'], 'awaiting_confirmation')
        with self.assertRaises(ValueError):
            c.probe(self.data, self.home, 'service:meshy', self.rpc)
        with self.assertRaises(ValueError):
            self.change(notes='msy_abcdefghijklmnopqrstuvwxyz')
        self.assertEqual({method for method,_,_ in self.calls}, {'config/read', 'app/installed'})
        self.assertEqual(self.before, self.config.read_bytes())
        self.assertNotIn('msy_', (self.data/'user.json').read_text())

    def test_bindings_persist_keep_unknown_fields_and_are_idempotent(self):
        request = {'action':'bind','id':'service:meshy','project_id':self.pid,'purpose':'Модели предметов','policy':'explicit','revision':self.view()['revision'],'request_id':'binding_0001'}
        c.change(self.data,self.home,request,self.rpc)
        replay=c.change(self.data,self.home,request,self.rpc)
        self.assertTrue(replay['replayed'])
        value=json.loads((self.data/'user.json').read_text('utf-8'))
        self.assertEqual(value['unrelated'], self.user['unrelated'])
        self.assertEqual(value['skills'], self.user['skills'])
        self.assertEqual(value[c.KEY]['bindings'][self.pid]['service:meshy']['purpose'],'Модели предметов')
        self.assertEqual(len(journal.read_events(self.data)),1)
        mesh=next(x for x in self.view(self.pid)['services'] if x['id']=='service:meshy')
        self.assertEqual(mesh['project_binding']['policy'],'explicit')
        self.assertFalse(mesh['configured'])
        with self.assertRaises(c.Conflict):
            c.change(self.data,self.home,{**request,'purpose':'Другое'},self.rpc)
        with self.assertRaises(c.Conflict):
            c.change(self.data,self.home,{**request,'request_id':'binding_0002'},self.rpc)
        self.assertEqual(self.before,self.config.read_bytes())

    def test_unbind_changes_only_catalogue(self):
        self.change(action='bind',project_id=self.pid,purpose='Models',policy='explicit')
        self.change(action='unbind',project_id=self.pid,request_id='request_0002')
        mesh=next(x for x in self.view(self.pid)['services'] if x['id']=='service:meshy')
        self.assertIsNone(mesh['project_binding'])
        self.assertEqual(self.before,self.config.read_bytes())

    def test_fallback_is_labelled_and_hides_error(self):
        def fail(*args,**kwargs): raise RuntimeError('SECRET_RPC_TOKEN')
        view=c.view(self.data,self.home,self.pid,fail)
        self.assertEqual(view['status'],'file_only')
        self.assertIn('проектные',view['warning'])
        self.assertNotIn('SECRET',json.dumps(view))
        self.config.write_text('secret = "SECRET_BROKEN', 'utf-8')
        broken=c.view(self.data,self.home,None,fail)
        self.assertEqual(broken['status'],'unavailable')
        self.assertNotIn('SECRET',json.dumps(broken))

    def test_explicit_probe_never_executes_a_tool(self):
        result=c.probe(self.data,self.home,'mcp:existing',self.rpc)
        self.assertEqual(result['status'],'discovered')
        self.assertEqual(result['tool_count'],1)
        self.assertNotIn('SECRET',json.dumps(result))
        method,params,kwargs=self.calls[-1]
        self.assertEqual(method,'mcpServerStatus/list')
        self.assertEqual(params['serverName'],'existing')
        self.assertEqual(kwargs['process_cwd'],str(self.home))

    def test_manual_service_round_trip(self):
        response=self.change(action='add',name='Другой API',kind='api',description='Будущий сервис',notes='По запросу')
        found=next(x for x in self.view()['services'] if x['id']==response['service_id'])
        self.assertFalse(found['configured'])
        self.assertEqual(found['connection_method'],'api')
        self.assertEqual(found['description'],'Будущий сервис')

    def test_provider_is_distinct_from_plugin_marketplace(self):
        import service_profiles
        google=service_profiles.describe({'id':'plugin:google-calendar@openai-curated','name':'google-calendar'})
        self.assertEqual(google['origin'],'third_party')
        self.assertEqual(google['provider'],'Google')
        self.assertEqual(google['integration_author'],'OpenAI')
        unknown=service_profiles.describe({'id':'plugin:unknown@openai-curated','name':'unknown'})
        self.assertEqual(unknown['origin'],'unknown')

    def test_profile_edit_preserves_connection_and_is_idempotent(self):
        profile={'title':'Мой Meshy','provider':'Meshy','origin':'third_party','website':'https://www.meshy.ai/','documentation':'https://docs.meshy.ai/en/api/ai','description':'Модели для игры','capabilities':['Модели','Текстуры']}
        result=self.change(action='profile',profile=profile)
        request={'action':'profile','id':'service:meshy','revision':'old','request_id':'request_0001','profile':profile}
        self.assertTrue(c.change(self.data,self.home,request,self.rpc)['replayed'])
        current=next(x for x in self.view()['services'] if x['id']=='service:meshy')
        self.assertEqual(current['profile']['title'],'Мой Meshy')
        self.assertTrue(current['profile']['customized'])
        self.assertFalse(current['configured'])
        self.assertEqual(self.config.read_bytes(),self.before)
        saved=json.loads((self.data/'user.json').read_text('utf-8'))
        self.assertEqual(saved['unrelated'],self.user['unrelated'])
        self.assertEqual(len(journal.read_events(self.data)),1)

    def test_profiles_reject_secret_and_unsafe_links(self):
        profile={'title':'Demo','provider':'Test','origin':'third_party','website':'https://example.com/','description':'Demo','capabilities':['Read']}
        for url in ['javascript:alert(1)','https://user:password@example.com/','https://example.com/?token=hidden','http://example.com/']:
            with self.assertRaises(ValueError):self.change(action='profile',profile={**profile,'website':url})
        with self.assertRaises(ValueError):self.change(action='profile',profile={**profile,'description':'msy_abcdefghijklmnopqrstuvwxyz'})
        self.assertEqual(self.config.read_bytes(),self.before)
        self.assertNotIn('service_catalog',json.loads((self.data/'user.json').read_text('utf-8')))

    def test_cloudflare_option_and_connection_identity(self):
        option=next(x for x in self.view()['services'] if x['id']=='service:cloudflare')
        self.assertFalse(option['configured'])
        self.assertEqual(option['connection']['state'],'available')
        for card in self.view()['services']:
            self.assertTrue(card['profile']['connection_steps'])
            self.assertTrue(card['profile']['connection_documentation'].startswith('https://'))
        def cloud(method,params,*args,**kwargs):
            if method=='app/installed':return {'apps':[]},'test'
            return {'config':{'mcp_servers':{'my-cloud':{'enabled':True,'url':'https://mcp.cloudflare.com/mcp?api_key=SECRET_CLOUD'}}},'layers':[]},'test'
        view=c.view(self.data,self.home,request_fn=cloud)
        entries=[x for x in view['services'] if x['id']=='service:cloudflare']
        self.assertEqual(len(entries),1)
        self.assertTrue(entries[0]['configured'])
        self.assertEqual(entries[0]['server_name'],'my-cloud')
        self.assertNotIn('SECRET_CLOUD',json.dumps(view))

    def test_discovery_survives_refresh_but_not_configuration_change(self):
        c.probe(self.data,self.home,'mcp:existing',self.rpc)
        card=next(x for x in self.view()['services'] if x['id']=='mcp:existing')
        self.assertEqual(card['connection']['state'],'connected')
        self.assertTrue(card['last_check']['fresh'])
        self.assertNotIn('SECRET', (self.data/'connection-checks.json').read_text('utf-8'))
        def changed(method,params,*args,**kwargs):
            response,client=self.rpc(method,params,*args,**kwargs)
            if method=='config/read':response['config']['mcp_servers']['existing']['args']=['changed']
            return response,client
        view=c.view(self.data,self.home,request_fn=changed)
        card=next(x for x in view['services'] if x['id']=='mcp:existing')
        self.assertEqual(card['connection']['state'],'needs_check')
        self.assertNotIn('last_check',card)

    def test_old_discovery_result_is_not_a_live_status(self):
        c.probe(self.data,self.home,'mcp:existing',self.rpc)
        path=self.data/'connection-checks.json';saved=json.loads(path.read_text('utf-8'))
        saved['checks']['mcp:existing']['result']['checked_at']='2020-01-01T00:00:00+00:00'
        atomic_json(path,saved)
        card=next(x for x in self.view()['services'] if x['id']=='mcp:existing')
        self.assertFalse(card['last_check']['fresh'])
        self.assertEqual(card['connection']['state'],'needs_check')


if __name__ == '__main__': unittest.main()
