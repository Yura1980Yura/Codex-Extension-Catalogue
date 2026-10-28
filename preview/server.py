"""Current catalogue: read Codex, keep personal annotations separate from facts."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import webbrowser

from collect import collect, read, ROOT, runtime_path
from controls import Controls, ControlError, Conflict
from folder_window import open_folder
from project_folders import folder_key, file_folder, decorate_projects
from skill_sources import change as change_sources, settings_view, SettingsError
from skill_files import SkillFiles, SkillFileError, component as skill_component

APP = 'codex-catalog-overview-preview'
WEB = Path(__file__).parent/'web'

def build_id():
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.ps1', '.js', '.css', '.html', '.json') and not any(p in path.parts for p in ('node_modules', '__pycache__', 'tests')):
            digest.update(path.relative_to(WEB.parent).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:20]

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(tmp, path)

class Preview:
    def __init__(self, settings, work):
        self.settings, self.work = settings, Path(work).resolve()
        source = Path(settings.get('source_data') or Path.home()/'.codex/skill-catalog').resolve()
        if self.work == source or self.work.is_relative_to(source) or source.is_relative_to(self.work):
            raise ValueError('Пробные записи должны храниться отдельно от рабочего каталога.')
        self.lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.refresh_again = threading.Event()
        self.job = {'state': 'idle'}
        self.watch_state = {'enabled': False, 'mode': 'manual'}
        self.stop_watch = threading.Event()
        self.controls = Controls(settings,self.work)
        self.skill_files = SkillFiles(settings, self.work)

    def start_watch(self):
        # Kept as a compatibility hook. Discovery is explicitly user-triggered.
        return None

    def open_project(self, payload):
        project = next((p for p in read(self.work/'snapshot.json', {}).get('projects', []) if p['id'] == payload.get('id')), None)
        if not project:
            raise ValueError('Проект не найден. Обновите каталог.')
        with self.lock:
            overlay = read(self.work/'annotations.json', {})
            path = Path(file_folder(project, overlay))
        if not path.is_dir():
            raise ValueError('Папка файлов не найдена. Укажите её через «Изменить папку».')
        result = open_folder(path.resolve())
        write(self.work/'last-folder-open.json', {**result, 'project_id': project['id'], 'at': datetime.now(timezone.utc).isoformat()})
        return {'opened': True, 'foreground': True}

    def set_project_folder(self, payload):
        project = next((p for p in read(self.work/'snapshot.json', {}).get('projects', []) if p['id'] == payload.get('id')), None)
        if not project or 'path' not in payload:
            raise SettingsError('Укажите проект и папку файлов.')
        raw = payload['path']
        if raw is not None:
            if not isinstance(raw, str) or not raw.strip():
                raise SettingsError('Укажите существующую папку абсолютным путём.')
            path = Path(raw.strip())
            if not path.is_absolute() or not path.is_dir():
                raise SettingsError('Укажите существующую папку абсолютным путём.')
            raw = str(path.resolve())
        changed = False
        with self.lock:
            overlay = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
            if payload.get('revision') != overlay['revision']:
                raise SettingsError('Настройки изменились в другом окне. Обновите каталог и повторите сохранение.')
            folders = overlay.setdefault('project_folders', {})
            key = folder_key(project)
            old = folders.get(key)
            if (raw is None and old) or (raw is not None and (not old or old['path'] != raw)):
                before = file_folder(project, overlay)
                if raw is None:
                    folders.pop(key)
                else:
                    folders[key] = {'path': raw, 'at': datetime.now(timezone.utc).isoformat()}
                self.event(overlay, 'project_folder', project['id'],
                    {'project': project['name'], 'before': before, 'after': file_folder(project, overlay),
                     'source': 'user' if raw else project.get('source', 'catalog')})
                write(self.work/'annotations.json', overlay)
                changed = True
        return self.state()

    def set_skill_sources(self, payload):
        projects = read(self.work/'snapshot.json', {}).get('projects', [])
        with self.lock:
            overlay = read(self.work/'annotations.json', {'revision':0,'items':{},'events':[]})
            if payload.get('revision') != overlay['revision']:
                raise SettingsError('Настройки изменились в другом окне. Обновите страницу и повторите действие.')
            before = overlay.get('skill_sources', [])
            after = change_sources(overlay, payload, projects)
            if before != after:
                overlay['skill_sources'] = after
                self.event(overlay, 'skill_sources', 'workspace', {'action':payload['action'], 'before':before, 'after':after})
                write(self.work/'annotations.json', overlay)
        return self.state()

    def open_legacy(self):
        entry = runtime_path(self.settings)/'manager/launch.py'
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(entry), '--no-browser'],
            capture_output=True, text=True, encoding='utf-8', timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        url = result.stdout.strip().splitlines()[-1]
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username or parsed.password:
            raise ValueError('Не получен локальный адрес прежнего каталога.')
        return {'url': url}

    def reorder(self, payload):
        snapshot = read(self.work/'snapshot.json', {})
        ids = {a['id'] for a in snapshot.get('addons', [])}
        context = payload.get('context')
        valid_contexts = {'all'} | {p['id'] for p in snapshot.get('projects', [])}
        order = payload.get('order')
        if context not in valid_contexts or not isinstance(order, list) or any(not isinstance(x, str) or x not in ids for x in order) or len(set(order)) != len(order):
            raise ValueError('Неверный порядок карточек.')
        with self.lock:
            data = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
            if payload.get('revision') != data['revision']:
                raise ValueError('Порядок изменился в другом окне. Обновите сведения.')
            data.setdefault('orders', {})[context] = order
            self.event(data, 'order', 'workspace', {'context': context, 'order': order})
            write(self.work/'annotations.json', data)
        return data

    def add_project(self, payload):
        raise SettingsError('Добавьте проект в Codex, затем нажмите «Сверить с Codex».')

    @staticmethod
    def event(data, action, key, value):
        event = {'id': secrets.token_hex(12), 'at': datetime.now(timezone.utc).isoformat(), 'kind': 'preview_'+action, 'extension_id': key, 'value': value}
        event['previous_hash'] = data['events'][-1].get('hash', '') if data['events'] else ''
        event['hash'] = hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        data['events'].append(event)
        data['revision'] += 1

    def state(self):
        # Capture before the snapshot: refresh may finish while we decorate it.
        # An older snapshot must keep polling instead of reporting completion.
        job = dict(self.job)
        snapshot = read(self.work/'snapshot.json')
        if snapshot is None:
            return {'loading': True, 'job': job}
        with self.lock:
            overlay = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
        decorated = self.skill_files.decorate(self.controls.decorate(snapshot))
        return {**decorated, 'projects': decorate_projects(snapshot.get('projects', []), overlay),
                'source_settings':settings_view(self.settings,snapshot.get('projects', []),overlay,snapshot),
                'overlay': overlay, 'job': job, 'watch': self.watch_state,
                'removed_skills':self.skill_files.removed()}

    def skill_plan(self, payload):
        return self.skill_files.plan(read(self.work/'snapshot.json', {}), payload)

    def skill_change(self, payload):
        if not self.refresh_lock.acquire(blocking=False):
            raise SkillFileError('Дождитесь завершения сверки.')
        try:
            with self.lock:
                snapshot = read(self.work/'snapshot.json', {})
                def record(operation):
                    overlay = read(self.work/'annotations.json', {'revision':0, 'items':{}, 'events':[]})
                    self.event(overlay, 'skill_'+operation['action'], operation['id'], operation)
                    write(self.work/'annotations.json', overlay)
                result = self.skill_files.apply(snapshot, payload, record)
                if result['action'] == 'remove':
                    # This is a known filesystem operation, not a discovery pass.
                    path = skill_component(snapshot, payload)['path']
                    for addon in snapshot.get('addons', []):
                        for c in addon.get('components', []):
                            if c.get('path') == path:
                                c.update(installed=False, enabled=None, file_found=False, basis='Инструкция SKILL.md удалена. Папка и остальные файлы сохранены. Выполните новую сверку.')
                    for row in snapshot.get('skill_sources', {}).get('rows', []):
                        row['files'] = [f for f in row.get('files', []) if f['path'] != path]
                        if row.get('status') == 'ok' and not row['files']: row['status'] = 'empty'
                    write(self.work/'snapshot.json', snapshot)
            return {'result':result, 'state':self.state()}
        finally:
            self.refresh_lock.release()

    def reveal_skill(self, payload):
        c = skill_component(read(self.work/'snapshot.json', {}), payload)
        path = Path(c['path'])
        if not path.is_file(): raise SkillFileError('Файл уже недоступен. Сверьте каталог с Codex.')
        return open_folder(path.resolve().parent)

    def activation(self, payload):
        result = self.controls.change(read(self.work/'snapshot.json',{}),payload)
        return {'result':result,'state':self.state()}

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            self.refresh_again.set()
            return self.job
        self.refresh_again.clear()
        self.job = {'state': 'running', 'started_at': datetime.now(timezone.utc).isoformat()}
        def run():
            try:
                result = collect(self.settings, self.work)
                self.job = {'state': 'done', 'updated_at': result['updated_at']}
            except Exception as error:
                # Avoid returning native RPC/config errors, which may contain credentials.
                self.job = {'state': 'error', 'message': 'Сверка не завершена. Предыдущий снимок сохранён.', 'error_type': type(error).__name__}
                (self.work/'last-error.txt').write_text(type(error).__name__+': '+str(error), encoding='utf-8')
            finally:
                self.refresh_lock.release()
                if self.refresh_again.is_set() and not self.stop_watch.is_set(): self.refresh()
        threading.Thread(target=run, daemon=True).start()
        return self.job

    def annotate(self, payload):
        key = payload.get('id')
        ids = {a['id'] for a in read(self.work/'snapshot.json', {}).get('addons', [])}
        if key not in ids and key != 'workspace':
            raise ValueError('Надстройка не найдена. Обновите страницу.')
        action = payload.get('action')
        if action not in ('note', 'favorite', 'tags', 'wish'):
            raise ValueError('Действие не поддерживается в пробном варианте.')
        with self.lock:
            data = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
            if payload.get('revision') != data['revision']:
                raise ValueError('Запись изменилась в другом окне. Обновите страницу; введённый текст сохранён в форме.')
            item = data['items'].setdefault(key, {})
            stamp = datetime.now(timezone.utc).isoformat()
            if action == 'favorite':
                if type(payload.get('value')) is not bool:
                    raise ValueError('Неверное значение избранного.')
                item['favorite'] = payload['value']
                value = payload['value']
            else:
                value = payload.get('text', '')
                if not isinstance(value, str) or not value.strip() or len(value) > 20000:
                    if not (action == 'tags' and value == ''):
                        raise ValueError('Введите текст до 20 000 символов.')
                if action == 'tags':
                    item['tags'] = list(dict.fromkeys(t.strip() for t in value.split(',') if t.strip()))[:30]
                else:
                    item.setdefault('notes' if action == 'note' else 'wishes', []).append({'text': value.strip(), 'at': stamp})
            self.event(data, action, key, value)
            write(self.work/'annotations.json', data)
            return data

def make_server(service, port):
    token = secrets.token_urlsafe(32)
    # One process serves one immutable frontend build, even while sources are updated.
    assets = {p.relative_to(WEB).as_posix(): p.read_bytes() for p in WEB.rglob('*') if p.is_file()}
    build = build_id()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def send(self, value, status=200, kind='application/json; charset=utf-8'):
            raw = json.dumps(value, ensure_ascii=False).encode() if kind.startswith('application/json') else value
            self.send_response(status)
            for k, v in {'Content-Type': kind, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)
        def route(self, post=False):
            parsed = urlsplit(self.path)
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected or self.headers.get('Origin', 'http://'+expected) != 'http://'+expected:
                return self.send({'error': 'Доступ разрешён только локальному каталогу.'}, 403)
            if parsed.path.startswith('/api/') and parsed.path != '/api/health' and not hmac.compare_digest(self.headers.get('X-Catalog-Token', ''), token):
                return self.send({'error': 'Обновите страницу каталога.'}, 403)
            if post:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json' or not 0 < size < 100000:
                    raise ValueError('Неверный формат запроса.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict): raise ValueError('Неверный запрос.')
                if parsed.path == '/api/refresh': return self.send(service.refresh(), 202)
                if parsed.path == '/api/project': return self.send(service.add_project(payload), 202)
                if parsed.path == '/api/open-project': return self.send(service.open_project(payload))
                if parsed.path == '/api/project-folder': return self.send(service.set_project_folder(payload))
                if parsed.path == '/api/skill-sources': return self.send(service.set_skill_sources(payload))
                if parsed.path == '/api/legacy': return self.send(service.open_legacy())
                if parsed.path == '/api/order': return self.send(service.reorder(payload))
                if parsed.path == '/api/activation': return self.send(service.activation(payload))
                if parsed.path == '/api/skill-plan': return self.send(service.skill_plan(payload))
                if parsed.path == '/api/skill-change': return self.send(service.skill_change(payload))
                if parsed.path == '/api/reveal-skill': return self.send(service.reveal_skill(payload))
                if parsed.path == '/api/shutdown':
                    self.send({'stopped': True})
                    service.stop_watch.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                if parsed.path == '/api/annotate': return self.send(service.annotate(payload))
                return self.send({'error': 'Это действие не поддерживается каталогом.'}, 403)
            if parsed.path == '/api/health': return self.send({'app': APP, 'pid': os.getpid(), 'data': str(service.work), 'build': build})
            if parsed.path == '/api/state': return self.send(service.state())
            if parsed.path == '/api/instruction':
                key = parse_qs(parsed.query).get('id', [''])[0]
                value = read(service.work/'instructions.json', {}).get(key)
                return self.send(value or {'error': 'Инструкция не подтверждена в текущей установке.'}, 200 if value else 404)
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/model.js': ('model.js', 'text/javascript'), '/styles.css': ('styles.css', 'text/css'), '/icon.svg': ('icon.svg', 'image/svg+xml')}
            files.update({'/'+name: (name, 'text/javascript') for name in ('bootstrap.js', 'dialog.js', 'markdown.js', 'settings.js', 'state.js', 'skill-actions.js', 'reconciliation.js', 'vendor/marked.js', 'vendor/purify.js')})
            if parsed.path not in files: return self.send({'error': 'Страница не найдена.'}, 404)
            name, mime = files[parsed.path]
            raw = assets[name].replace(b'__TOKEN__', token.encode()) if name == 'index.html' else assets[name]
            return self.send(raw, kind=mime+'; charset=utf-8')
        def handle_route(self, post=False):
            try: self.route(post)
            except Conflict as error: self.send({'error':str(error)},409)
            except ControlError as error: self.send({'error':str(error)},400)
            except SettingsError as error: self.send({'error':str(error)},400)
            except SkillFileError as error: self.send({'error':str(error)},400)
            except (ValueError, TypeError, KeyError): self.send({'error': 'Не удалось сохранить. Проверьте поля или обновите сведения; текст остался в форме.'}, 400)
            except OSError: self.send({'error': 'Файл сейчас недоступен. Предыдущие записи сохранены.'}, 503)
            except subprocess.SubprocessError: self.send({'error': 'Прежний каталог не запустился. Его файлы сохранены.'}, 503)
        def do_GET(self): self.handle_route()
        def do_POST(self): self.handle_route(True)
    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False
        daemon_threads = True
        def server_bind(self):
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
    return LocalServer(('127.0.0.1', port), Handler)

def connect_or_upgrade(service, port):
    """Reuse the same build, or gracefully replace our own older server."""
    import urllib.request
    try:
        return make_server(service, port)
    except OSError as occupied:
        url = f'http://127.0.0.1:{port}'
        try:
            health = json.load(urllib.request.urlopen(url+'/api/health', timeout=3))
            if health.get('app') != APP or health.get('data') != str(service.work):
                raise ValueError('Адрес занят другой программой. Каталог не создаёт вторую копию на случайном адресе.')
            if health.get('build') == build_id(): return None
            html = urllib.request.urlopen(url, timeout=3).read().decode()
            token = re.search('name="catalog-token" content="([^"]+)"', html)[1]
            request = urllib.request.Request(url+'/api/shutdown', data=b'{}', headers={'Content-Type':'application/json','X-Catalog-Token':token})
            urllib.request.urlopen(request, timeout=5).close()
        except (OSError, ValueError, TypeError) as error:
            raise RuntimeError('Не удалось обновить запущенный каталог. Закройте его прежний сервер и запустите ярлык снова.') from error
        deadline = time.monotonic()+6
        while time.monotonic() < deadline:
            try: return make_server(service, port)
            except OSError: time.sleep(.15)
        raise RuntimeError('Прежний сервер ещё завершает работу. Повторите запуск каталога.') from occupied

def old_address_redirect(port, destination):
    """Preserve the addresses used by earlier previews; fragments survive redirects."""
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{port}':
                self.send_error(403); return
            self.send_response(302)
            self.send_header('Location', destination+'/')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length','0')
            self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1',port),Redirect)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, default=ROOT/'.local/catalog-current/settings.json')
    parser.add_argument('--work', type=Path, default=ROOT/'.local/catalog-current')
    parser.add_argument('--port', type=int, default=8772)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    service = Preview(read(args.settings, {}), args.work.resolve())
    server = connect_or_upgrade(service, args.port)
    if server is None:
        if args.open: webbrowser.open(f'http://127.0.0.1:{args.port}')
        return
    url = f'http://127.0.0.1:{server.server_port}'
    write(service.work/'server.json', {'app': APP, 'url': url, 'pid': os.getpid()})
    redirects = []
    if args.port == 8772:
        for old in (8770,8771):
            deadline = time.monotonic()+3
            while True:
                try:
                    redirects.append(old_address_redirect(old,url)); break
                except OSError:
                    if time.monotonic()>=deadline:
                        print(f'Прежний адрес {old} занят; актуальный каталог: {url}',file=sys.stderr); break
                    time.sleep(.15)
    service.controls.recover()
    service.start_watch()
    if args.open: webbrowser.open(url)
    print(url, flush=True)
    try: server.serve_forever()
    finally:
        service.stop_watch.set()
        for redirect in redirects:
            redirect.shutdown(); redirect.server_close()
        server.server_close()

if __name__ == '__main__': main()
