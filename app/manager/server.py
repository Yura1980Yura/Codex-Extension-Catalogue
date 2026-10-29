"""Loopback-only personal manager, backed by the existing catalogue files."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import sys
import threading
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"skill-catalog/scripts"))
from platform_paths import codex_dir
from storage import atomic_json, read_json
from service import Conflict, Manager, digest
from connections import meshy_plan

APP_ID = "codex-skill-catalog-manager-v1"


def make_server(service, port=8768):
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, data, status=200, content_type="application/json; charset=utf-8"):
            raw = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith("application/json") else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def trusted(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected or self.headers.get("Origin", "http://"+expected) != "http://"+expected:
                raise PermissionError("Разрешён только локальный адрес менеджера.")
            if api and not hmac.compare_digest(self.headers.get("X-Catalog-Token", ""), token):
                raise PermissionError("Обновите страницу менеджера.")

        def route(self, post=False):
            parsed = urlsplit(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            self.trusted(api=path.startswith("/api/") and path != "/api/health")
            arg = lambda key: query.get(key, [""])[0]
            if not post:
                if path == "/api/health":
                    return self.send({"app": APP_ID, "data_id": digest(str(service.data.resolve()).encode())})
                if path == "/api/state": return self.send(service.state())
                if path == "/api/projects": return self.send(service.projects())
                if path == "/api/connections": return self.send(service.connections(arg("project")))
                if path == "/api/resources": return self.send(service.resources(arg("project")))
                if path == "/api/connections/meshy-plan": return self.send(meshy_plan(service.home))
                if path == "/api/connections/meshy-status": return self.send(service.meshy_status())
                if path == "/api/skill": return self.send(service.detail(arg("id")))
                if path == "/api/instruction": return self.send(service.instruction(arg("id")))
                if path == "/api/document": return self.send(service.document(arg("name")))
                if path == "/api/job": return self.send(service.job(arg("id")))
                names = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/projects.js": ("projects.js", "text/javascript; charset=utf-8"), "/projects.css": ("projects.css", "text/css; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/icon.svg": ("icon.svg", "image/svg+xml")}
                names.update({"/connections.js": ("connections.js", "text/javascript; charset=utf-8"), "/connections.css": ("connections.css", "text/css; charset=utf-8")})
                names.update({"/resources.js": ("resources.js", "text/javascript; charset=utf-8"), "/resources.css": ("resources.css", "text/css; charset=utf-8")})
                if path not in names:
                    return self.send({"error": "Страница не найдена."}, 404)
                name, kind = names[path]
                raw = (ROOT/"manager/web"/name).read_bytes()
                if name == "index.html": raw = raw.replace(b"__CATALOG_TOKEN__", token.encode())
                return self.send(raw, content_type=kind)
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                raise ValueError("Ожидается запрос менеджера.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= (4096 if path == "/api/connections/meshy-key" else 140000):
                raise ValueError("Слишком большой запрос.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict): raise ValueError("Неверный запрос.")
            if path == "/api/note": result = service.note(data.get("id"), data.get("text"))
            elif path == "/api/projects": result = service.change_projects(data)
            elif path == "/api/connections": result = service.change_connections(data)
            elif path == "/api/resources": result = service.change_resources(data)
            elif path == "/api/skill-organization": result = service.change_skill_organization(data)
            elif path == "/api/connections/probe": result = service.probe_connection(data.get("id"))
            elif path == "/api/connections/meshy-key":
                try:
                    result = service.save_meshy_key(data)
                finally:
                    data.pop("api_key", None)
            elif path == "/api/favorite": result = service.favorite(data.get("id"), data.get("enabled"))
            elif path == "/api/directions": result = service.change_directions(data)
            elif path == "/api/origin": result = service.change_origin(data)
            elif path == "/api/author": result = service.change_author(data)
            elif path == "/api/activation": result = service.change_activation(data)
            elif path == "/api/document": result = service.save_document(data.get("name", ""), data.get("text"), data.get("revision"))
            elif path == "/api/wish": result = service.create_wish(data.get("title"), data.get("text"), data.get("skill_id"), data.get("request_id"))
            elif path == "/api/wish-update": result = service.update_wish(data.get("id", ""), data.get("revision"), data.get("state"), data.get("comment", ""), data.get("next_step"))
            elif path == "/api/recover": result = service.recover()
            elif path == "/api/search": return self.send(service.start_job("search", data.get("query")), 202)
            elif path == "/api/refresh": return self.send(service.start_job("refresh"), 202)
            elif path == "/api/export": result = service.saved({"saved": True})
            elif path == "/api/stop":
                self.send({"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else: return self.send({"error": "Действие не найдено."}, 404)
            self.send(result)

        def handle_route(self, post=False):
            try:
                self.route(post)
            except Conflict as error: self.send({"error": str(error)}, 409)
            except PermissionError as error: self.send({"error": str(error)}, 403)
            except (ValueError, KeyError, TypeError) as error: self.send({"error": str(error)}, 400)
            except FileNotFoundError: self.send({"error": "Файл пока недоступен. Проверьте подключение папки документов."}, 404)
            except (OSError, RuntimeError) as error:
                message = "Действие прервалось. Откройте карточку повторно: менеджер перечитает настройку Codex и восстановит историю. " if urlsplit(self.path).path == "/api/activation" else "Не удалось завершить действие. Ваши прежние данные сохранены. "
                self.send({"error": message+str(error)}, 503)

        def do_GET(self): self.handle_route()
        def do_POST(self): self.handle_route(True)
    class LocalHTTPServer(ThreadingHTTPServer):
        # HTTPServer's address reuse allows two listeners on one port on Windows.
        # Exclusive ownership makes the existing occupied-port fallback reliable.
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = LocalHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=codex_dir()/"skill-catalog")
    parser.add_argument("--docs-root", type=Path)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--state-file", type=Path, default=ROOT/".local/manager.json")
    args = parser.parse_args()
    settings = read_json(args.data_dir/"settings.json", {})
    docs = args.docs_root or settings.get("documentation_root") or (ROOT/"docs-root.txt").read_text("utf-8-sig").strip()
    service = Manager(args.data_dir, docs, ROOT, args.home)
    try:
        server = make_server(service, args.port)
    except OSError:
        if args.port == 0: raise
        # A double click may start a second launcher before the first writes its state.
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/health", timeout=2) as response:
                health = json.load(response)
            if health.get("app") == APP_ID and health.get("data_id") == digest(str(args.data_dir.resolve()).encode()):
                print(f"http://127.0.0.1:{args.port}", flush=True)
                raise SystemExit(0)
        except (OSError, ValueError):
            pass
        server = make_server(service, 0)
    import os
    url = f"http://127.0.0.1:{server.server_port}"
    atomic_json(args.state_file, {"app": APP_ID, "url": url, "pid": os.getpid(), "data_id": digest(str(args.data_dir.resolve()).encode())})
    print(url, flush=True)
    try: server.serve_forever()
    finally: server.server_close()
