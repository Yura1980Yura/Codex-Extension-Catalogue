"""Read the installed catalogue and Codex into an isolated, replaceable snapshot."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile

from model import build, norm
from project_registry import registered_projects, merge_projects
from project_folders import file_folder
from skill_sources import definitions, scan, integrate

ROOT = Path(__file__).resolve().parents[1]

def read(path, default=None):
    try:
        return json.loads(Path(path).read_text('utf-8-sig'))
    except FileNotFoundError:
        return default

def runtime_path(settings):
    if settings.get('runtime'):
        return Path(settings['runtime']).resolve()
    installation = read(Path.home()/'.agents/skills/skill-catalog/installation.json', {})
    source = installation.get('source_directory')
    return Path(source).parent if source else ROOT/'app'

def bundle_metadata(card):
    if not card['id'].startswith('plugin:'):
        return {}
    locations = sorted(card.get('locations', []), key=lambda x: x.get('kind') == 'cache')
    for location in locations:
        path = Path(location['path'])
        if not path.is_file() or len(path.parents) < 3:
            continue
        root = path.parents[2]
        meta = read(root/'plugin.json') or read(root/'.codex-plugin/plugin.json', {})
        if not meta:
            continue
        apps = meta.get('apps', {})
        if isinstance(apps, str):
            target = (root/apps).resolve()
            apps = read(target, {}).get('apps', {}) if target.is_relative_to(root.resolve()) else {}
        ids = [v['id'] for v in apps.values() if isinstance(v, dict) and isinstance(v.get('id'), str)] if isinstance(apps, dict) else []
        return {'title': meta.get('interface', {}).get('displayName') or meta.get('name'),
                'version': meta.get('version'), 'apps': ids, 'path': str(root/'.codex-plugin/plugin.json')}
    return {}

def collect(settings, work):
    home = Path(settings.get('home') or Path.home()).resolve()
    data = Path(settings.get('source_data') or home/'.codex/skill-catalog').resolve()
    runtime = runtime_path(settings)
    sys.path[:0] = [str(runtime/'skill-catalog/scripts'), str(runtime/'manager')]
    import catalog, connections, resources, installation, journal, localization
    from storage import atomic_json
    work = Path(work).resolve()
    if work == data or data in work.parents or work in data.parents:
        raise ValueError('Пробная папка должна находиться отдельно от рабочего каталога.')
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='collect-', dir=work) as temp:
        snapshot = Path(temp)
        # Never copy pending activation/recovery transactions into a working service.
        for name in ('inventory.json', 'user.json', 'settings.json', 'history.jsonl', 'connection-checks.json'):
            if (data/name).exists():
                shutil.copy2(data/name, snapshot/name)
        registry, registry_warning = registered_projects(home, connections.project_id)
        previous = read(work/'snapshot.json', {})
        projects = ([dict(p) for p in previous.get('projects', []) if p.get('source') == 'codex']
                    if registry_warning else merge_projects([], registry))
        for project in projects:
            project['available'] = Path(project['path']).is_dir()
        overlay = read(work/'annotations.json', {})
        for project in projects:
            project['skill_path'] = file_folder(project, overlay)
            project['file_path_available'] = Path(project['skill_path']).is_dir()
        session_path = settings.get('session')
        session = read(session_path, {}) if session_path else {}
        roots = list(dict.fromkeys(path for p in projects for path in (p['path'],p['skill_path'])))
        # Legacy inventories/settings are inputs for annotations, never project membership.
        old_settings = read(snapshot/'settings.json', {})
        old_settings['project_roots'] = roots
        atomic_json(snapshot/'settings.json', old_settings)
        old_inventory = read(snapshot/'inventory.json', {'skills': {}})
        old_inventory['projects'] = roots
        atomic_json(snapshot/'inventory.json', old_inventory)
        inventory = catalog.refresh(snapshot, home, str(home), roots, Path(session_path) if session_path else None)
        user = read(snapshot/'user.json', {})
        _, cards = catalog.load_cards(snapshot, home)
        composition = read(Path(__file__).parent/'composition.json', {})
        for key, values in settings.get('composition', {}).items():
            composition.setdefault(key, {}).update(values)
        for c in cards:
            c['favorite'] = bool(user.get('skills', {}).get(c['id'], {}).get('manager_favorite'))
            c['bundle'] = bundle_metadata(c)
            label = composition.get('labels', {}).get(c['name'])
            if label:
                c.update(title_ru=label['title'], helps=label['description'])
            hashes = {l.get('skill_sha256') for l in c.get('locations', []) if l.get('kind') != 'cache' and l.get('skill_sha256')}
            c['verified_experience'] = [e for e in c.get('experience', []) if e.get('skill_sha256') in hashes]
            c['historical_experience'] = [e for e in c.get('experience', []) if e not in c['verified_experience']]
        # Each cwd gets its own effective config; overrides cannot be inferred from a name.
        contexts = [('all', None)] + [(p['id'], p['id']) for p in projects]
        def inspect(pair):
            key, pid = pair
            # The legacy adapter takes an exclusive storage lock even when
            # reading. Give each parallel context its own temporary store.
            with tempfile.TemporaryDirectory(prefix='context-', dir=work) as context:
                context = Path(context)
                for name in ('inventory.json', 'user.json', 'settings.json', 'connection-checks.json'):
                    if (snapshot/name).exists():
                        shutil.copy2(snapshot/name, context/name)
                return key, connections.view(context, home, pid)
        with ThreadPoolExecutor(max_workers=3) as pool:
            views = dict(pool.map(inspect, contexts))
        # The legacy resource adapter has valuable curated descriptions and user overlays.
        resource_view = resources.view(snapshot, home)
        addons = build(cards, views, resource_view['resources'], projects, installation.describe, composition)
        # Programs are reported only when an explicitly configured executable exists.
        for program in settings.get('programs', []):
            path = Path(program['path'])
            if path.is_file():
                a = next((a for a in addons if a['id'] == program['extension']), None)
                if a:
                    a['components'].append({'id': 'program:'+program['name'], 'kind': 'program',
                        'name': program['name'], 'path': str(path), 'scope': 'global', 'installed': True,
                        'enabled': None, 'basis': 'Найден исполняемый файл; запуск не проверялся'})
        settings_old = read(data/'settings.json', {})
        docs_root = Path(settings_old.get('documentation_root') or runtime/'notes-template')
        documents = []
        for key, title, path in [('inbox', 'Наблюдения', 'Заметки/Наблюдения.md'), ('backlog', 'Пожелания', 'Бэклог навыков.md'), ('journal', 'Журнал разработки', 'Журнал разработки.md'), ('guide', 'Инструкция прежнего каталога', 'Менеджер навыков.md')]:
            file = docs_root/path
            if file.is_file():
                documents.append({'id': key, 'title': title, 'path': str(file), 'text': file.read_text('utf-8-sig')})
        # Instructions are looked up by known skill id, never by a path from the browser.
        instructions = {}
        for c in cards:
            if c.get('state') == 'cache_only' and not c.get('has_user_annotations'):
                continue
            loc = catalog.select_location(c, home)
            if not loc:
                loc = next((l for l in c.get('locations', []) if l.get('kind') != 'cache' and Path(l['path']).is_file()), None)
            if loc:
                original = Path(loc['path']).read_text('utf-8-sig')
                instructions[c['id']] = {'text': original, 'language': 'Оригинал', 'path': loc['path']}
            try:
                result = localization.read(c, home)
                if result.get('markdown'):
                    instructions[c['id']]['translation'] = result['markdown']
            except (AttributeError, KeyError, TypeError, ValueError, OSError):
                pass
        directions = resource_view['directions']
        sources, source_documents = scan(definitions(settings, projects, overlay))
        integrate(addons, projects, sources['rows'], source_documents, instructions)
        # A file is a finding until a fresh Codex discovery confirms this path.
        for addon in addons:
            for component in addon['components']:
                if component['kind'] == 'skill':
                    confirmed = any(o.get('kind') == 'discovery' for o in component.get('observations', []))
                    component['installed'] = bool(component.get('installed') and confirmed)
                    if component.get('file_found') and not confirmed and not component.get('managed_package'):
                        component['basis'] = 'Файл найден. Codex не подтвердил доступность при последней сверке.'
        stamp = datetime.now(timezone.utc).isoformat()
        from audit import audit
        reconciliation = audit(inventory, views, addons, session, projects, home)
        atomic_json(work/'reconciliation.json', reconciliation)
        result = {'version': '3.5.1', 'updated_at': stamp, 'source_updated_at': read(data/'inventory.json', {}).get('updated_at'),
            'addons': addons, 'projects': projects, 'directions': directions, 'skill_sources':sources,
            'events': journal.read_events(data), 'documents': documents,
            'project_notes': user.get('project_catalog', {}).get('projects', {}),
            'coverage': {'discovery': inventory.get('discovery_status'), 'session_at': session.get('observed_at'), 'reconciliation': reconciliation,
                'project_registry_warning': registry_warning,
                'session_label': session.get('label'), 'views': {key: {k: v.get(k) for k in ('checked_at', 'status', 'apps_status', 'warning', 'coverage')} for key, v in views.items()},
                'limits': ['Проверены зарегистрированные папки этого компьютера.', 'Снимок метаданных чата имеет отдельную дату; остальные чаты автоматически не просматриваются.', 'Наличие файла или включение не доказывает успешное выполнение задачи.']},
            'legacy_url': settings.get('legacy_url', 'http://127.0.0.1:8768'),
            'paths': {'data': str(data), 'preview': str(work), 'runtime': str(runtime)}}
        atomic_json(work/'instructions.json', instructions)
        atomic_json(work/'snapshot.json', result)
        return result
