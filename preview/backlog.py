"""One backlog: reuse the existing Markdown cards and recoverable writer."""
import hashlib
import json
from pathlib import Path
import sys

from collect import ROOT, read, runtime_path


class BacklogError(ValueError):
    pass


class Backlog:
    def __init__(self, settings, work):
        self.settings, self.work = settings, Path(work)
        home = Path(settings.get('home') or Path.home()).resolve()
        self.source = Path(settings.get('source_data') or home/'.codex/skill-catalog').resolve()
        runtime = runtime_path(settings)
        manager_root = ROOT/'app/manager' if (ROOT/'app/manager/service.py').is_file() else runtime/'manager'
        sys.path[:0] = [str(manager_root), str(runtime/'skill-catalog/scripts')]
        from service import Manager

        class DocumentsOnly(Manager):
            # The two Markdown documents and journal are already saved atomically
            # by the manager. Do not export unrelated catalogue representations.
            def saved(self, result):
                return result

        self.manager_class, self.home = DocumentsOnly, home

    def manager(self):
        root = read(self.source/'settings.json', {}).get('documentation_root')
        if not root or not Path(root).is_dir():
            raise BacklogError('Папка документов недоступна. Подключите диск с бэклогом и повторите. Введённый текст остаётся в форме.')
        manager = self.manager_class(self.source, root, ROOT, self.home)
        if not manager.document_path('backlog').is_file():
            raise BacklogError('Файл «Бэклог навыков.md» не найден в папке документов. Введённый текст остаётся в форме.')
        return manager

    def migrate(self, manager):
        """Old local wishes stay intact as evidence; deterministic IDs prevent copies."""
        overlay = read(self.work/'annotations.json', {})
        import journal
        imported = {e.get('data', {}).get('request_id') for e in journal.read_events(self.source)
                    if e.get('kind') == 'wish_created'}
        for owner, item in overlay.get('items', {}).items():
            for index, wish in enumerate(item.get('wishes', [])):
                raw = json.dumps([owner, index, wish], ensure_ascii=False, sort_keys=True)
                key = hashlib.sha256(('catalog-wish:'+raw).encode()).hexdigest()[:32]
                if key in imported:
                    continue
                text = wish.get('text', '')
                title = text.strip().splitlines()[0] if text.strip() else ''
                title = ''.join(' ' if c in '|[]' else c for c in title)[:140]
                manager._create_wish(title, text, request_id=key)
                imported.add(key)

    def view(self, manager):
        import journal
        return {'items': manager.wishes(), 'document': manager.document('backlog'),
                'events': journal.read_events(self.source), 'path': str(manager.docs)}

    def handle(self, payload):
        action = payload.get('action')
        if action not in ('load', 'create', 'read', 'update'):
            raise BacklogError('Неизвестное действие с пожеланием.')
        try:
            manager = self.manager()
            manager.recover()
            self.migrate(manager)
            if action == 'read':
                return manager.document(payload.get('id', ''))
            if action == 'create':
                if not payload.get('request_id'):
                    raise BacklogError('Обновите страницу перед сохранением пожелания.')
                result = manager._create_wish(payload.get('title'), payload.get('text'), request_id=payload['request_id'])
            elif action == 'update':
                result = manager.update_wish(payload.get('id', ''), payload.get('revision'),
                    payload.get('state'), payload.get('comment', ''), payload.get('next_step'))
            else:
                result = {}
            return {**self.view(manager), 'result': result}
        except (OSError, ValueError, RuntimeError) as error:
            raise BacklogError(str(error)) from error
