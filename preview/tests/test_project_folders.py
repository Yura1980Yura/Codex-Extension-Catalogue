from pathlib import Path
import sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Preview, read, write


class ProjectFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.codex=self.root/'Codex Empty';self.actual=self.root/'Файлы игры'
        self.codex.mkdir();self.actual.mkdir();self.work=self.root/'work'
        self.settings={'home':str(self.root/'home'),'source_data':str(self.root/'source')}
        self.projects=[{'id':'game','codex_id':'stable-zoo','name':'Зоо-Кафе','source':'codex','path':str(self.codex)},
                       {'id':'other','codex_id':'other-zoo','name':'Зоо-Кафе','source':'codex','path':str(self.codex)}]
        self.snapshot={'projects':self.projects,'addons':[]}
        write(self.work/'snapshot.json',self.snapshot)
        self.service=Preview(self.settings,self.work)
        refreshing=patch.object(self.service,'refresh',return_value={'state':'running'})
        self.refreshing=refreshing.start();self.addCleanup(refreshing.stop)
    def tearDown(self):self.tmp.cleanup()
    def save(self,path,revision=0):
        return self.service.set_project_folder({'id':'game','path':path,'revision':revision})

    def test_manual_folder_controls_opening_but_not_codex_scope(self):
        state=self.save(str(self.actual))
        self.assertEqual(state['projects'][0]['file_path'],str(self.actual.resolve()))
        self.assertEqual(state['projects'][0]['path'],str(self.codex))
        self.assertEqual(state['projects'][0]['skill_path'],str(self.actual.resolve()))
        self.refreshing.assert_called_once()
        self.assertEqual(state['projects'][0]['file_path_source'],'user')
        self.assertEqual(state['projects'][1]['file_path'],str(self.codex))
        self.assertEqual(read(self.work/'snapshot.json'),self.snapshot)
        with patch('server.open_folder',return_value={'opened':True,'foreground':True}) as open_window:
            self.service.open_project({'id':'game','path':'C:/untrusted'})
            open_window.assert_called_once_with(self.actual.resolve())

    def test_saved_folder_survives_restart_refresh_and_codex_root_change(self):
        self.save(str(self.actual))
        self.snapshot['projects'][0].update(id='new-context',path=str(self.root),name='Renamed')
        write(self.work/'snapshot.json',self.snapshot)
        project=Preview(self.settings,self.work).state()['projects'][0]
        self.assertEqual(project['file_path'],str(self.actual.resolve()))
        self.assertEqual(project['path'],str(self.root))

    def test_history_and_reset_are_explicit_without_duplicate_events(self):
        first=self.save(str(self.actual));event=first['overlay']['events'][0]
        self.assertEqual(event['kind'],'preview_project_folder')
        self.assertEqual(event['value']['before'],str(self.codex))
        self.assertEqual(event['value']['after'],str(self.actual.resolve()))
        repeated=self.save(str(self.actual),1)
        self.assertEqual(repeated['overlay']['revision'],1)
        reset=self.save(None,1)
        self.assertEqual(reset['projects'][0]['file_path'],str(self.codex))
        self.assertEqual(reset['projects'][0]['file_path_source'],'codex')
        self.assertEqual(len(reset['overlay']['events']),2)

    def test_stale_revision_does_not_replace_user_choice(self):
        self.save(str(self.actual))
        with self.assertRaises(ValueError):self.save(None,0)
        self.assertEqual(self.service.state()['projects'][0]['file_path'],str(self.actual.resolve()))

    def test_missing_manual_folder_never_falls_back_to_empty_codex_folder(self):
        self.save(str(self.actual));self.actual.rmdir()
        self.assertFalse(self.service.state()['projects'][0]['file_path_available'])
        with patch('server.open_folder') as open_window:
            with self.assertRaises(ValueError):self.service.open_project({'id':'game'})
            open_window.assert_not_called()

    def test_invalid_path_or_unknown_project_is_not_saved(self):
        for path in ['', 'relative', str(self.root/'missing'), 42]:
            with self.subTest(path=path),self.assertRaises(ValueError):self.save(path)
        with self.assertRaises(ValueError):
            self.service.set_project_folder({'id':'absent','path':str(self.actual),'revision':0})
        self.assertFalse((self.work/'annotations.json').exists())
