from pathlib import Path
import json, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Preview, write
from backlog import BacklogError


class SharedBacklog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = self.root/'vault/project'
        self.docs.mkdir(parents=True)
        self.index = self.docs/'Бэклог навыков.md'
        self.initial = '# Бэклог\n\nЛичная вводная.\n\n| Тема | Состояние | Следующий шаг | Карточка |\n|---|---|---|---|\n\nЛичное послесловие.\n'
        self.index.write_text(self.initial, encoding='utf-8')
        self.source = self.root/'data'
        self.work = self.root/'work'
        write(self.source/'settings.json', {'documentation_root': str(self.docs)})
        self.server = Preview({'runtime':str(Path(__file__).resolve().parents[2]/'app'),
            'source_data':str(self.source), 'home':str(self.root/'home')}, self.work)
        self.backlog = self.server.backlog
        self.legacy = sys.modules['service']
        self.payload = {'action':'create', 'title':'Анимация кафе', 'text':'Моя точная мысль\nс новой строкой', 'request_id':'a'*32}

    def test_create_and_retry_share_card_index_and_one_event(self):
        first = self.backlog.handle(self.payload)
        second = self.backlog.handle(self.payload)
        self.assertEqual(first['result']['id'], second['result']['id'])
        self.assertEqual(len(second['items']), 1)
        self.assertEqual(len(second['events']), 1)
        doc = self.backlog.handle({'action':'read','id':first['result']['id']})
        self.assertIn('> Моя точная мысль\n> с новой строкой', doc['markdown'])
        index = self.index.read_text('utf-8')
        self.assertIn('Личная вводная.', index)
        self.assertIn('Личное послесловие.', index)
        self.assertEqual(index.count('| Анимация кафе |'), 1)
        self.assertEqual(len(self.backlog.manager().wishes()), 1)

    def test_update_changes_same_documents_and_preserves_original(self):
        result = self.backlog.handle(self.payload)
        row = result['items'][0]
        updated = self.backlog.handle({'action':'update', 'id':row['id'], 'revision':row['revision'],
            'state':'Проверено','comment':'Проверили движение в игре.','next_step':'Сохранить результат'})
        self.assertEqual(updated['items'][0]['state'], 'Проверено')
        self.assertIn('| Проверено | Сохранить результат |', self.index.read_text('utf-8'))
        text = self.backlog.handle({'action':'read','id':row['id']})['markdown']
        self.assertIn('> Моя точная мысль\n> с новой строкой', text)
        self.assertIn('Проверили движение в игре.', text)
        self.assertEqual([e['kind'] for e in updated['events']], ['wish_created','wish_updated'])
        with self.assertRaisesRegex(BacklogError,'изменилась'):
            self.backlog.handle({'action':'update','id':row['id'],'revision':row['revision'],'state':'Отложено','comment':'stale'})

    def test_verified_needs_evidence(self):
        row = self.backlog.handle(self.payload)['items'][0]
        with self.assertRaisesRegex(BacklogError,'опишите'):
            self.backlog.handle({'action':'update','id':row['id'],'revision':row['revision'],'state':'Проверено','comment':''})

    def test_prompt_reads_fresh_card_without_changing_any_data(self):
        row = self.backlog.handle(self.payload)['items'][0]
        path = self.docs/'Бэклог'/f"{row['id']}.md"
        path.write_text(path.read_text('utf-8').replace('Моя точная мысль', 'Новая точная мысль'), 'utf-8')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        value = self.backlog.handle({'action':'prompt','id':row['id']})
        self.assertEqual(value['id'], row['id'])
        self.assertEqual(value['path'], str(path.resolve()))
        self.assertIn('Новая точная мысль\nс новой строкой', value['prompt'])
        self.assertNotIn('Моя точная мысль', value['prompt'])
        self.assertIn(str(self.work), value['prompt'])
        self.assertIn('ту же карточку', value['prompt'].lower())
        self.assertIn('историю', value['prompt'])
        self.assertIn('WISHES-CODEX.md', value['prompt'])
        self.assertEqual(before, {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_prompt_to_codex_update_keeps_one_card_and_history(self):
        row = self.backlog.handle(self.payload)['items'][0]
        handoff = self.backlog.handle({'action':'prompt','id':row['id']})
        self.backlog.handle({'action':'update','id':handoff['id'],'revision':handoff['revision'],
            'state':'В работе','comment':'Читаем задачу'})
        fresh = self.backlog.handle({'action':'read','id':handoff['id']})
        self.backlog.handle({'action':'update','id':handoff['id'],'revision':fresh['revision'],
            'state':'Проверено','comment':'Выполнено и проверено','next_step':'Прочитать результат'})
        done = self.backlog.handle({'action':'prompt','id':handoff['id']})
        self.assertEqual(done['state'], 'Проверено')
        self.assertIn('не повторяй завершённую работу', done['prompt'])
        self.assertEqual(len(list((self.docs/'Бэклог').glob('BK-*.md'))),1)
        self.assertEqual(self.index.read_text('utf-8').count('| Анимация кафе |'),1)
        self.assertIn('Моя точная мысль', done['prompt'])
        events=self.backlog.handle({'action':'load'})['events']
        self.assertEqual([e['kind'] for e in events],['wish_created','wish_updated','wish_updated'])

    def test_prompt_rejects_non_wish_documents_and_unavailable_cards(self):
        for key in ('backlog', '../settings.json', 'journal', None):
            with self.subTest(key=key), self.assertRaises(BacklogError):
                self.backlog.handle({'action':'prompt','id':key})
        with self.assertRaises(BacklogError):
            self.backlog.handle({'action':'prompt','id':'BK-2026-999'})

    def test_old_browser_wishes_migrate_once_without_rewriting_overlay(self):
        write(self.work/'annotations.json', {'items':{'workspace':{'wishes':[{'text':'Старое пожелание','at':'2026-01-01'}]}}})
        original = (self.work/'annotations.json').read_bytes()
        self.backlog.handle({'action':'load'})
        result = self.backlog.handle({'action':'load'})
        self.assertEqual(len(result['items']),1)
        self.assertEqual(len(result['events']),1)
        self.assertEqual((self.work/'annotations.json').read_bytes(),original)

    def test_unavailable_docs_do_not_claim_success_or_lose_existing_data(self):
        write(self.source/'settings.json', {'documentation_root':str(self.root/'disconnected')})
        with self.assertRaisesRegex(BacklogError,'недоступна'):
            self.backlog.handle(self.payload)
        self.assertEqual(self.index.read_text('utf-8'), self.initial)
        self.assertFalse((self.source/'history.jsonl').exists())

    def test_interrupted_pair_recovers_without_duplicate_card_or_event(self):
        real = self.legacy.atomic_text
        def fail_index(path, text):
            if Path(path) == self.index: raise OSError('disk disconnected')
            return real(path,text)
        with patch.object(self.legacy,'atomic_text',side_effect=fail_index):
            with self.assertRaises(BacklogError): self.backlog.handle(self.payload)
        self.assertTrue((self.source/'manager-pending.json').exists())
        result = self.backlog.handle(self.payload)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(len(result['events']),1)
        self.assertFalse((self.source/'manager-pending.json').exists())

    def test_external_edit_visible_without_codex_reconciliation(self):
        row=self.backlog.handle(self.payload)['items'][0]
        path=self.docs/'Бэклог'/(row['id']+'.md')
        path.write_text(path.read_text('utf-8').replace('Анимация кафе','Новое название'),encoding='utf-8')
        self.assertEqual(self.backlog.handle({'action':'load'})['items'][0]['title'],'Новое название')

    def test_arbitrary_file_and_changed_retry_are_rejected(self):
        with self.assertRaises(BacklogError): self.backlog.handle({'action':'read','id':'../../secret'})
        self.backlog.handle(self.payload)
        with self.assertRaisesRegex(BacklogError,'Первая версия'):
            self.backlog.handle({**self.payload,'text':'другой текст'})
        self.assertEqual(len(self.backlog.handle({'action':'load'})['items']),1)

if __name__ == '__main__': unittest.main()
