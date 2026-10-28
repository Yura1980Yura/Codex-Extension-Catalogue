from pathlib import Path
import json, sys, tempfile, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'preview'),str(ROOT/'app/skill-catalog/scripts'),str(ROOT/'app/manager')]
from collect import collect
from server import write
import connections


class RegistryCollection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.work=self.root/'work';self.source=self.root/'legacy'
        self.home.mkdir();self.extra=self.root/'old-extra';self.extra.mkdir();self.game=self.root/'game';self.game.mkdir()
        self.settings={'home':str(self.home),'source_data':str(self.source),'runtime':str(ROOT/'app'),'projects':[{'name':'Manual extra','path':str(self.extra)}]}
        write(self.source/'settings.json',{'project_roots':[str(self.extra)]})
        write(self.source/'inventory.json',{'skills':{},'projects':[str(self.extra)]})
        self.registry=self.home/'.codex/.codex-global-state.json'
        self.roots=[]

    def run_collect(self):
        def refresh(directory,home,cwd,roots,*args):
            self.roots=list(roots)
            self.assertNotIn(str(self.extra),json.loads((directory/'settings.json').read_text())['project_roots'])
            return {'skills':{},'discovery_status':'ok'}
        view={'services':[],'status':'effective','apps_status':'reported'}
        with patch('catalog.refresh',side_effect=refresh),patch('catalog.load_cards',return_value=({},[])),patch('connections.view',return_value=view),patch('resources.view',return_value={'resources':[],'directions':[]}),patch('journal.read_events',return_value=[]):
            return collect(self.settings,self.work)

    def test_current_registry_excludes_legacy_manual_roots_and_tracks_rename_and_delete(self):
        write(self.registry,{'local-projects':{'native':{'name':'Game','rootPaths':[str(self.game)]}}})
        result=self.run_collect();self.assertEqual([p['name'] for p in result['projects']],['Game']);self.assertEqual(self.roots,[str(self.game)])
        write(self.registry,{'local-projects':{'native':{'name':'Renamed','rootPaths':[str(self.game)]}}})
        self.assertEqual(self.run_collect()['projects'][0]['name'],'Renamed')
        write(self.registry,{'local-projects':{}})
        self.assertEqual(self.run_collect()['projects'],[]);self.assertEqual(self.roots,[])

    def test_native_project_stays_with_missing_folder_marker(self):
        write(self.registry,{'local-projects':{'native':{'name':'Missing','rootPaths':[str(self.root/'missing')]}}})
        result=self.run_collect();self.assertEqual(len(result['projects']),1);self.assertFalse(result['projects'][0]['available'])

    def test_registry_error_preserves_only_last_native_projects_and_reports_stale_source(self):
        write(self.registry,{'local-projects':{'native':{'name':'Game','rootPaths':[str(self.game)]}}})
        self.run_collect();self.registry.write_text('incomplete write')
        result=self.run_collect();self.assertEqual([p['name'] for p in result['projects']],['Game'])
        self.assertTrue(result['coverage']['project_registry_warning'])

if __name__=='__main__':unittest.main()
