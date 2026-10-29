"""One backlog: reuse the existing Markdown cards and recoverable writer."""
import hashlib
import json
import re
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

    def prompt(self, manager, key):
        """Read one fresh card. Preparing a handoff never changes its state/history."""
        if not isinstance(key, str) or not re.fullmatch(r'BK-\d{4}-\d{3,6}', key):
            raise BacklogError('Выберите существующее пожелание.')
        doc = manager.document(key)
        text = doc['markdown'].replace('\r\n', '\n')
        heading = re.search(r'^# (.+)$', text, re.M)
        title = re.sub(r'^BK-\d+-\d+\s*[—–-]\s*', '', heading[1]) if heading else key
        state = re.search(r'^- Состояние: (.+?)[.]?$', text, re.M)
        state = state[1] if state else 'Не указано'
        section = re.search(r'^## Исходная формулировка\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
        original = re.sub(r'^> ?', '', section[1], flags=re.M).strip() if section else ''
        path = manager.document_path(key).resolve()
        instructions = Path(__file__).with_name('WISHES-CODEX.md').resolve()
        prompt = f'''Работай с существующим пожеланием {key} «{title}» из моего каталога навыков.

Карточка: {path}
Состояние при подготовке запроса: {state}.

Исходное пожелание:
{original or 'Прочитай формулировку в самой карточке: стандартный раздел в ней не найден.'}

1. Прочитай свежую карточку целиком, включая прежние результаты и комментарии. Это существующая задача; новую карточку вместо неё не создавай. Если путь недоступен, найди мой каталог через skill-catalog и его папку документов. Сверь номер и название; если карточка недоступна, сообщи об этом, не создавая копию.
2. Определи проект по карточке и контексту этого чата. Если нужный проект или ожидаемый результат неясен, уточни их. Если пожелание уже «Проверено», учти выполненное; не повторяй завершённую работу без нового поручения.
3. Когда задача ясна и работа начинается, сохрани «В работе» через механизм каталога. Выполни поручение и необходимые проверки.
4. Допиши в ЭТУ ЖЕ карточку датированный результат: что сделано, что проверено, ссылки на файлы и результаты, ограничения и оставшиеся шаги. Исходную формулировку и прежние комментарии сохрани. Поставь «Проверено» только по фактическому результату; незавершённую работу так и опиши.
5. Обнови вместе карточку, строку общего бэклога и историю через существующее действие обновления пожелания. Перед записью перечитай свежую версию, чтобы сохранить чужие правки. Не ограничивайся ответом в чате. Проверь сохранение и сообщи мне номер карточки и результат.

Порядок сохранения для Codex: {instructions}
Рабочие данные каталога: {self.work}
Исходные данные каталога: {self.source}
'''
        return {'id': key, 'title': title, 'state': state, 'revision': doc['revision'],
                'path': str(path), 'prompt': prompt}

    def handle(self, payload):
        action = payload.get('action')
        if action not in ('load', 'create', 'read', 'update', 'prompt'):
            raise BacklogError('Неизвестное действие с пожеланием.')
        try:
            manager = self.manager()
            if action == 'prompt':
                return self.prompt(manager, payload.get('id'))
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
