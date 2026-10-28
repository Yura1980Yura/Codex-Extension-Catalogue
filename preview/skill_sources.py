"""Explicit catalogue search roots. File discovery never grants Codex access."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from project_folders import folder_key, file_folder

SKIP = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}

class SettingsError(ValueError):
    """Only explicit, user-facing validation text may cross the HTTP boundary."""

def canonical(path):
    return os.path.normcase(str(Path(path).resolve()))

def source_id(scope, key, path):
    return hashlib.sha256((scope+'\0'+key+'\0'+canonical(path)).encode()).hexdigest()[:20]

def definitions(settings, projects, overlay):
    home = Path(settings.get('home') or Path.home())
    rows = []
    def add(path, title, scope='global', project=None, category='standard'):
        key = folder_key(project) if project else ''
        rows.append({'id':source_id(scope,key,path), 'path':str(path), 'title':title,
            'context_path':str(file_folder(project,overlay)) if project else str(home),
            'scope':scope, 'project_key':key, 'project_id':project['id'] if project else None,
            'project_name':project.get('name', '') if project else '',
            'category':category, 'enabled':True, 'editable':False})
    add(home/'.agents/skills', 'Личные навыки Codex')
    add(home/'.codex/skills', 'Навыки в папке Codex')
    add(home/'.codex/skills/.system', 'Встроенные навыки', category='system')
    add(home/'.codex/plugins/cache', 'Файлы плагинов', category='plugins')
    for project in projects:
        root = Path(file_folder(project, overlay))
        add(root/'.agents/skills', 'Навыки проекта', 'local', project)
        add(root/'.codex/skills', 'Дополнительное расположение в проекте', 'local', project)
        # Repository ancestors are inherited only inside an actual repository.
        chain = [root, *root.parents]
        repo = next((p for p in chain if (p/'.git').exists()), None)
        if repo and repo != root:
            for parent in root.parents:
                add(parent/'.agents/skills', 'Навыки родительской папки', 'local', project)
                if parent == repo: break
    by_key = {folder_key(p):p for p in projects}
    for raw in overlay.get('skill_sources', []):
        project = by_key.get(raw.get('project_key'))
        rows.append({**raw, 'title':'Дополнительная папка', 'category':'custom', 'editable':True,
            'context_path':str(file_folder(project,overlay)) if project else str(home),
            'project_id':project['id'] if project else None,
            'project_name':project.get('name', '') if project else '',
            'orphaned':raw.get('scope')=='local' and project is None})
    return rows

def config_key(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def discover_files(root, max_dirs=6000, max_files=2000):
    """Bounded traversal, follows skill links once; never traverses build trees."""
    found, errors, visited, stack = [], [], set(), [Path(root)]
    while stack:
        folder = stack.pop()
        try:
            key = canonical(folder)
            if key in visited: continue
            if len(visited) >= max_dirs or len(found) >= max_files:
                errors.append('Достигнут предел проверки. Укажите более точную папку.'); break
            visited.add(key)
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name == 'SKILL.md' and entry.is_file(): found.append(Path(entry.path))
                    elif entry.name not in SKIP and entry.name != '.system' and entry.is_dir(): stack.append(Path(entry.path))
        except OSError:
            errors.append('Часть папки недоступна для чтения.')
    return sorted(found, key=str), list(dict.fromkeys(errors))

def instruction(path):
    if path.stat().st_size > 1024*1024:
        raise ValueError('Инструкция больше 1 МБ; проверьте файл отдельно.')
    text = path.read_text(encoding='utf-8-sig')
    head = re.match(r'\A---\s*\n(.*?)\n---(?:\s*\n|$)', text, re.S)
    if not head: raise ValueError('Нет описания навыка в начале SKILL.md.')
    def field(name):
        match = re.search(r'^'+name+r':\s*([^\n]*)', head[1], re.M)
        value = match[1].strip().strip('\"\'') if match else ''
        if value in ('|', '>', '|-', '>-'):
            tail = head[1][match.end():]
            value = ' '.join(x.strip() for x in re.findall(r'^ +(.+)$', tail.split('\n\n')[0], re.M))
        return value
    name, description = field('name'), field('description')
    if not name or not description: raise ValueError('В инструкции нужны name и description.')
    return name, description, text

def scan(rows):
    stamp = datetime.now(timezone.utc).isoformat()
    results, documents, cache = [], {}, {}
    for source in rows:
        row = {**source, 'checked_at':stamp, 'files':[], 'errors':[]}
        path = Path(row['path'])
        if not row.get('enabled', True): row['status']='disabled'
        elif row.get('orphaned'): row['status']='orphaned'
        elif not path.exists(): row['status']='missing'
        elif not path.is_dir(): row['status']='invalid'
        else:
            key = canonical(path)
            if key not in cache: cache[key] = discover_files(path)
            files, errors = cache[key]
            row['errors'] = list(errors)
            seen = set()
            for file in files:
                file_key = canonical(file)
                if file_key in seen: continue
                seen.add(file_key)
                try:
                    if file_key not in documents:
                        name, description, text = instruction(file)
                        documents[file_key] = {'name':name, 'description':description, 'text':text, 'path':str(file.resolve())}
                    doc = documents[file_key]
                    row['files'].append({'key':file_key, 'path':doc['path'], 'name':doc['name']})
                except (OSError, UnicodeError, ValueError) as error:
                    row['files'].append({'key':file_key, 'path':str(file), 'name':file.parent.name,
                        'error':str(error) if isinstance(error, ValueError) else 'Не удалось прочитать инструкцию.'})
            row['status'] = 'partial' if row['errors'] or any(f.get('error') for f in row['files']) else 'ok' if row['files'] else 'empty'
        results.append(row)
    return {'key':config_key(rows), 'checked_at':stamp, 'rows':results}, documents

def integrate(addons, projects, rows, documents, instructions):
    """Reuse canonical paths, preserve native grouping and native enablement."""
    known = {}
    for addon in addons:
        for component in addon.get('components', []):
            if component.get('kind') == 'skill' and component.get('path'):
                known.setdefault(canonical(component['path']), (addon, component))
    for row in rows:
        for file in row['files']:
            if file.get('error'): continue
            key = file['key']
            if key not in known:
                doc = documents[key]
                sid = 'source:'+hashlib.sha256(key.encode()).hexdigest()[:24]
                card = {'id':sid, 'name':doc['name'], 'description':doc['description'], 'locations':[], 'observations':[]}
                component = {'id':sid+':file', 'skill_id':sid, 'name':doc['name'], 'kind':'skill',
                    'path':doc['path'], 'scope':row['scope'], 'installed':False, 'file_found':True,
                    'enabled':None, 'project_ids':[], 'observations':[], 'checked_at':row['checked_at'],
                    'managed_package':row['category']=='plugins',
                    'basis':'Файл в кеше плагина. Подключение пакета Codex не подтверждено.' if row['category']=='plugins' else 'Файл найден. Доступность Codex не подтверждена.'}
                addon = {'id':'extension:'+sid, 'title':doc['name'], 'description':doc['description'],
                    'profile':{}, 'components':[component], 'skills':[card], 'directions':[], 'tags':[],
                    'origin':'unknown', 'billing':'unknown', 'bindings':[], 'notes':[], 'related':[], 'favorite':False}
                addons.append(addon); known[key]=(addon,component)
                instructions[sid] = {'text':doc['text'], 'path':doc['path'], 'language':'Оригинал'}
            pair = known.get(key)
            if not pair:
                file['availability']='cache'; continue
            addon, component = pair
            component['file_found'] = True
            component.setdefault('search_sources', []).append({k:row[k] for k in ('id','title','path','scope','project_id','project_name','category')})
            if component['id'].startswith('source:'):
                if row['scope']=='global': component['scope']='global'
                elif row.get('project_id') not in component['project_ids']: component['project_ids'].append(row['project_id'])
            file.update(addon_id=addon['id'], component_id=component['id'])
            observed = [o for o in component.get('observations', []) if o.get('kind')=='discovery']
            observed=[o for o in observed if o.get('cwd') and canonical(o['cwd'])==canonical(row['context_path'])]
            file['availability'] = 'enabled' if any(o.get('enabled') is True for o in observed) else 'disabled' if observed and all(o.get('enabled') is False for o in observed) else 'cache' if component.get('managed_package') else 'unconfirmed'
    return addons

def settings_view(settings, projects, overlay, snapshot):
    rows = definitions(settings, projects, overlay)
    scanned = snapshot.get('skill_sources', {})
    by_id = {row['id']:row for row in scanned.get('rows', [])}
    result = []
    for row in rows:
        previous = by_id.get(row['id'])
        same = previous and all(previous.get(k)==row.get(k) for k in ('path','enabled','scope','project_key'))
        result.append({**(previous if same else {}), **row, 'pending':not same})
    return {'rows':result, 'checked_at':scanned.get('checked_at'), 'pending':config_key(rows)!=scanned.get('key')}

def change(overlay, payload, projects):
    rows = deepcopy(overlay.get('skill_sources', []))
    action = payload.get('action')
    index = next((i for i,r in enumerate(rows) if r['id']==payload.get('id')), None)
    if action in ('remove','toggle'):
        if index is None: raise SettingsError('Дополнительная папка не найдена.')
        if action=='remove': rows.pop(index)
        else:
            if type(payload.get('enabled')) is not bool: raise SettingsError('Неверное состояние папки.')
            rows[index]['enabled']=payload['enabled']
    elif action=='save':
        raw, scope = payload.get('path'), payload.get('scope')
        if not isinstance(raw,str) or not raw.strip() or not Path(raw.strip()).is_absolute() or not Path(raw.strip()).is_dir():
            raise SettingsError('Укажите существующую папку абсолютным путём.')
        if scope not in ('global','local'): raise SettingsError('Выберите общую папку или проект.')
        project = next((p for p in projects if p['id']==payload.get('project_id')),None)
        if scope=='local' and not project: raise SettingsError('Выберите существующий проект.')
        key = folder_key(project) if scope=='local' else ''
        path = str(Path(raw.strip()).resolve())
        if payload.get('id') and index is None: raise SettingsError('Папка изменена в другом окне. Обновите страницу.')
        if any(i!=index and r['scope']==scope and r.get('project_key','')==key and canonical(r['path'])==canonical(path) for i,r in enumerate(rows)):
            raise SettingsError('Эта папка уже добавлена в выбранную область.')
        row = {'id':rows[index]['id'] if index is not None else 'custom:'+source_id(scope,key,path),
            'path':path, 'scope':scope, 'project_key':key, 'enabled':rows[index]['enabled'] if index is not None else True}
        if index is None: rows.append(row)
        else: rows[index]=row
    else: raise SettingsError('Неизвестное действие с папкой.')
    return rows
