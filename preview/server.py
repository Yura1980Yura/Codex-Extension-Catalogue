"""Current catalogue: read Codex, keep personal annotations separate from facts."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
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

APP = 'codex-catalog-overview-preview'
WEB = Path(__file__).parent/'web'

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
        self.job = {'state': 'idle'}
        self.watch_state = {'local_seconds': 15, 'account_minutes': 5, 'enabled': False}
        self.stop_watch = threading.Event()

    def start_watch(self):
        from watch import signature
        self.watch_state['enabled'] = True
        def monitor():
            previous = None
            last = 0
            while not self.stop_watch.is_set():
                try:
                    current = signature(self.settings, self.work)
                    if not self.refresh_lock.locked() and (current != previous or time.monotonic()-last >= 300):
                        self.refresh()
                        previous, last = current, time.monotonic()
                except (OSError, ValueError):
                    pass  # A partially written file will be read on the next tick.
                self.stop_watch.wait(15)
        threading.Thread(target=monitor, daemon=True).start()

    def open_project(self, payload):
        project = next((p for p in read(self.work/'snapshot.json', {}).get('projects', []) if p['id'] == payload.get('id')), None)
        if not project or not Path(project['path']).is_dir():
            raise ValueError('Папка проекта не найдена.')
        os.startfile(str(Path(project['path']).resolve()))
        return {'opened': True}

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
        if self.refresh_lock.locked():
            raise ValueError('Дождитесь окончания текущей сверки и повторите добавление.')
        name, raw = payload.get('name'), payload.get('path')
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(raw, str):
            raise ValueError('Укажите название и папку проекта.')
        path = Path(raw)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError('Укажите существующую папку абсолютным путём.')
        with self.lock:
            existing = self.settings.setdefault('projects', [])
            normalized = os.path.normcase(str(path.resolve()))
            if any(os.path.normcase(str(Path(p['path']).resolve())) == normalized for p in existing):
                raise ValueError('Эта папка уже добавлена.')
            existing.append({'name': name.strip(), 'path': str(path.resolve())})
            write(self.work/'settings.json', self.settings)
            data = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
            self.event(data, 'project', 'workspace', name.strip()+' — '+str(path.resolve()))
            write(self.work/'annotations.json', data)
        return self.refresh()

    @staticmethod
    def event(data, action, key, value):
        event = {'id': secrets.token_hex(12), 'at': datetime.now(timezone.utc).isoformat(), 'kind': 'preview_'+action, 'extension_id': key, 'value': value}
        event['previous_hash'] = data['events'][-1].get('hash', '') if data['events'] else ''
        event['hash'] = hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        data['events'].append(event)
        data['revision'] += 1

    def state(self):
        snapshot = read(self.work/'snapshot.json')
        if snapshot is None:
            return {'loading': True, 'job': self.job}
        with self.lock:
            overlay = read(self.work/'annotations.json', {'revision': 0, 'items': {}, 'events': []})
        return {**snapshot, 'overlay': overlay, 'job': self.job, 'watch': self.watch_state}

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            return self.job
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
                if parsed.path == '/api/legacy': return self.send(service.open_legacy())
                if parsed.path == '/api/order': return self.send(service.reorder(payload))
                if parsed.path == '/api/shutdown':
                    self.send({'stopped': True})
                    service.stop_watch.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                if parsed.path == '/api/annotate': return self.send(service.annotate(payload))
                return self.send({'error': 'Изменение рабочего Codex в пробной версии недоступно.'}, 403)
            if parsed.path == '/api/health': return self.send({'app': APP, 'pid': os.getpid(), 'data': str(service.work)})
            if parsed.path == '/api/state': return self.send(service.state())
            if parsed.path == '/api/instruction':
                key = parse_qs(parsed.query).get('id', [''])[0]
                value = read(service.work/'instructions.json', {}).get(key)
                return self.send(value or {'error': 'Инструкция не подтверждена в текущей установке.'}, 200 if value else 404)
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/model.js': ('model.js', 'text/javascript'), '/styles.css': ('styles.css', 'text/css'), '/icon.svg': ('icon.svg', 'image/svg+xml')}
            files.update({'/'+name: (name, 'text/javascript') for name in ('markdown.js', 'vendor/marked.js', 'vendor/purify.js')})
            if parsed.path not in files: return self.send({'error': 'Страница не найдена.'}, 404)
            name, mime = files[parsed.path]
            raw = (WEB/name).read_bytes().replace(b'__TOKEN__', token.encode()) if name == 'index.html' else (WEB/name).read_bytes()
            return self.send(raw, kind=mime+'; charset=utf-8')
        def handle_route(self, post=False):
            try: self.route(post)
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', type=Path, default=ROOT/'.local/catalog-current/settings.json')
    parser.add_argument('--work', type=Path, default=ROOT/'.local/catalog-current')
    parser.add_argument('--port', type=int, default=8772)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    service = Preview(read(args.settings, {}), args.work.resolve())
    try:
        server = make_server(service, args.port)
    except OSError:
        import urllib.request
        try:
            url = f'http://127.0.0.1:{args.port}'
            health = json.load(urllib.request.urlopen(url+'/api/health', timeout=2))
            if health.get('app') == APP and health.get('data') == str(service.work):
                if args.open: webbrowser.open(url)
                return
        except (OSError, ValueError): pass
        server = make_server(service, 0)
    url = f'http://127.0.0.1:{server.server_port}'
    write(service.work/'server.json', {'app': APP, 'url': url, 'pid': os.getpid()})
    service.start_watch()
    if args.open: webbrowser.open(url)
    print(url, flush=True)
    try: server.serve_forever()
    finally:
        service.stop_watch.set()
        server.server_close()

if __name__ == '__main__': main()
