from pathlib import Path
import json, sys, tempfile, threading, unittest, urllib.request, urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Preview, make_server, write

class Isolation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        write(self.root/'snapshot.json',{'addons':[{'id':'sample'}]})
        self.service=Preview({},self.root)
        self.server=make_server(self.service,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        import re
        html=urllib.request.urlopen(self.url).read().decode()
        self.token=re.search('name="catalog-token" content="([^"]+)"',html)[1]
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,body=None,headers=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers={'X-Catalog-Token':self.token,'Content-Type':'application/json',**(headers or {})})
        return urllib.request.urlopen(req)
    def test_notes_persist_only_in_separate_overlay(self):
        original=(self.root/'snapshot.json').read_bytes()
        with self.request('/api/annotate',{'id':'sample','action':'note','text':'Проверено','revision':0}) as r:self.assertEqual(json.load(r)['revision'],1)
        self.assertEqual((self.root/'snapshot.json').read_bytes(),original)
        self.assertEqual(json.loads((self.root/'annotations.json').read_text('utf-8'))['items']['sample']['notes'][0]['text'],'Проверено')
    def test_conflicting_write_does_not_overwrite_note(self):
        self.service.annotate({'id':'sample','action':'note','text':'first','revision':0})
        with self.assertRaises(ValueError):self.service.annotate({'id':'sample','action':'note','text':'second','revision':0})
        self.assertEqual(len(self.service.state()['overlay']['events']),1)
    def test_unrelated_codex_mutations_are_not_routed(self):
        for path in ['/api/connections/meshy-key','/api/install']:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,{'enabled':False})
            self.assertEqual(e.exception.code,403)
    def test_activation_rejects_unknown_component_and_foreign_origin(self):
        for headers,status in [({},400),({'Origin':'https://example.org'},403),({'X-Catalog-Token':'wrong'},403)]:
            with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/activation',{'id':'unknown','component_id':'bad','enabled':False,'revision':'x'},headers)
            self.assertEqual(error.exception.code,status)
    def test_foreign_origin_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/state',headers={'Origin':'https://example.org'})
        self.assertEqual(e.exception.code,403)
    def test_private_api_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(self.url+'/api/state')
        self.assertEqual(e.exception.code,403)
    def test_instruction_cannot_read_arbitrary_path(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/instruction?id=../../config.toml')
        self.assertEqual(e.exception.code,404)
    def test_working_data_cannot_be_used_for_preview(self):
        with self.assertRaises(ValueError):Preview({'source_data':str(self.root)},self.root)
    def test_new_project_only_updates_preview_settings_and_history(self):
        project=self.root/'project';project.mkdir()
        self.service.refresh=lambda:{'state':'done'}
        self.service.add_project({'name':'Test project','path':str(project)})
        self.assertFalse(list(project.iterdir()))
        self.assertEqual(self.service.state()['overlay']['events'][0]['kind'],'preview_project')
        with self.assertRaises(ValueError):self.service.add_project({'name':'Again','path':str(project)})

if __name__=='__main__':unittest.main()
