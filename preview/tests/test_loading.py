import json, sys, threading, urllib.request, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_server
import server

class Loading(unittest.TestCase):
    setUp = test_server.Isolation.setUp
    tearDown = test_server.Isolation.tearDown
    request = test_server.Isolation.request
    def test_frontend_module_graph_is_served(self):
        import re
        queue=['/bootstrap.js']; seen=set()
        while queue:
            path=queue.pop()
            if path in seen: continue
            seen.add(path)
            response=self.request(path)
            self.assertIn('javascript',response.headers['Content-Type'])
            source=response.read().decode()
            for name in re.findall(r"(?:from\s*|import\s*\()\s*['\"](\./[^'\"]+)",source):
                from posixpath import dirname, normpath
                queue.append(normpath(dirname(path).rstrip('/')+'/'+name))
        self.assertTrue({'/app.js','/markdown.js','/vendor/marked.js','/vendor/purify.js'} <= seen)

    def test_running_server_keeps_its_frontend_and_build(self):
        before=self.request('/app.js').read()
        health=json.load(self.request('/api/health'))
        with patch.object(server,'WEB',Path('not-the-running-build')):
            self.assertEqual(self.request('/app.js').read(),before)
            self.assertEqual(json.load(self.request('/api/health'))['build'],health['build'])
        self.assertEqual(len(health['build']),20)

    def test_same_build_reuses_server(self):
        self.assertIsNone(server.connect_or_upgrade(self.service,self.server.server_port))

    def test_stale_build_restarts_at_same_port(self):
        threading.Thread(target=lambda:(self.thread.join(),self.server.server_close()),daemon=True).start()
        with patch.object(server,'build_id',return_value='new-build'):
            replacement=server.connect_or_upgrade(self.service,self.server.server_port)
            replacement.server_close()

if __name__=='__main__':unittest.main()
