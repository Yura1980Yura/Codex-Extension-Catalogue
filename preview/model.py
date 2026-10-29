"""Projection of evidence into extensions. No config writes, no inferred usage."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import os
from pathlib import Path

TYPE_NAMES = {'skill': 'Навык', 'mcp': 'MCP', 'plugin': 'Плагин', 'app': 'Приложение', 'program': 'Программа'}

def norm(path):
    return os.path.normcase(os.path.abspath(path))

def within(path, root):
    try:
        return os.path.commonpath([norm(path), norm(root)]) == norm(root)
    except ValueError:
        return False

def scope_of(sources):
    applied = [x for x in sources if x.get('applied', True)]
    scopes = {x.get('scope') for x in applied}
    if scopes & {'project', 'repo'}:
        return 'local'
    if scopes & {'user', 'system', 'account', 'cloud', 'managed', 'admin', 'legacyManagedConfigTomlFromFile'}:
        return 'global'
    return 'unknown'

def connection_facts(c):
    return {'installed': bool(c.get('configured')), 'enabled': c.get('enabled'),
            'scope': scope_of(c.get('sources', [])), 'sources': deepcopy(c.get('sources', [])),
            'connection': deepcopy(c.get('connection', {})), 'checked_at': c.get('checked_at'),
            'approval': c.get('approval'), 'policy': c.get('policy'), 'transport': c.get('transport'), 'last_check': deepcopy(c.get('last_check'))}

def build(cards, views, resources, projects, installation_fn, overrides=None):
    overrides = overrides or {}
    resources = deepcopy(resources)
    defs = {r['id']: r for r in resources}
    alias = {cid: r['id'] for r in resources for cid in r.get('connection_ids', [])}
    alias.update(overrides.get('connections', {}))
    # Bundle membership is evidence of composition; a generic "related skill" is not.
    plugin_alias = {}
    for cid, rid in alias.items():
        if cid.startswith('plugin:'):
            plugin_alias[cid.split(':', 1)[1].split('@')[0]] = rid
    # The package manifest explicitly declares its connector dependencies.
    for s in cards:
        if not s['id'].startswith('plugin:'):
            continue
        short = s['id'].split(':')[1].split('@')[0]
        targets = {alias['app:'+x] for x in s.get('bundle', {}).get('apps', []) if 'app:'+x in alias}
        if len(targets) == 1 and short not in plugin_alias:
            plugin_alias[short] = next(iter(targets))
    plugin_alias.update(overrides.get('plugins', {}))
    groups = {}
    def group(key, title='', description=''):
        if key not in groups:
            r = defs.get(key, {})
            p = r.get('profile', {})
            groups[key] = {'id': key, 'title': p.get('title') or title or key,
                'description': p.get('description') or description, 'profile': p,
                'components': [], 'skills': [], 'directions': r.get('direction_ids', []),
                'tags': r.get('tags', []), 'origin': p.get('origin', 'unknown'),
                'billing': r.get('billing', 'unknown'), 'bindings': r.get('bindings', []),
                'notes': [r['notes']] if r.get('notes') else [], 'related': [], 'favorite': False}
        return groups[key]
    for context, view in views.items():
        for c in view.get('services', []):
            if not c.get('configured'):
                continue
            rid = alias.get(c['id'], 'extension:'+c['id'])
            a = group(rid, c.get('profile', {}).get('title') or c['name'], c.get('profile', {}).get('description', ''))
            if not a['profile']:
                a['profile'] = deepcopy(c.get('profile', {}))
                a['origin'] = a['profile'].get('origin', 'unknown')
            existing = next((x for x in a['components'] if x['id'] == c['id']), None)
            if existing is None:
                existing = {'id': c['id'], 'kind': c['kind'], 'name': c['name'], 'config_name':c.get('server_name') or (c['id'].split(':',1)[1] if c['id'].startswith(c['kind']+':') else c['name']), 'contexts': {}, 'scope': 'unknown'}
                a['components'].append(existing)
            existing['contexts'][context] = connection_facts({**c, 'checked_at': view.get('checked_at')})
    skill_groups = {}
    for s in cards:
        if s.get('state') == 'cache_only' and not s.get('has_user_annotations'):
            continue
        plugin = s.get('source', {}).get('plugin_id') if isinstance(s.get('source'), dict) else None
        if not plugin and s['id'].startswith('plugin:'):
            plugin = s['id'].split(':')[1]
        short = (plugin or '').split('@')[0]
        rid = overrides.get('skills', {}).get(s['name'])
        if not rid:
            rid = plugin_alias.get(short, 'extension:plugin:'+short) if plugin else 'extension:'+s['id']
        skill_groups[s['id']] = rid
        description = s.get('helps') or s.get('description_ru') or s.get('description_original') or s.get('description', '')
        a = group(rid, s.get('title_ru') or s['name'], description)
        if rid.startswith('extension:plugin:') and s.get('bundle', {}).get('title'):
            a['title'] = s['bundle']['title']
        bundle_label = overrides.get('bundle_labels', {}).get(short)
        if bundle_label:
            a.update(title=bundle_label['title'], description=bundle_label['description'])
        a['favorite'] |= bool(s.get('favorite'))
        a['skills'].append(deepcopy(s))
        a['directions'] = sorted(set(a['directions'] + s.get('direction_ids', [])))
        a['tags'] = sorted(set(a['tags'] + s.get('catalog_tags', [])))
        a['notes'].extend(s.get('notes') or [])
        if a['origin'] == 'unknown':
            a['origin'] = s.get('origin', 'unknown')
        entries = installation_fn(s)['entries']
        if not entries:
            entries = [{'kind': 'unknown', 'present': False, 'installation_path': '', 'project_path': ''}]
        for e in entries:
            loc = next((l for l in s.get('locations', []) if norm(Path(l['path']).parent) == norm(e['installation_path'] or '.')), {})
            scope = {'user': 'global', 'system': 'global', 'project': 'local'}.get(e['kind'], 'unknown')
            # Codex may report the junction target while inventory keeps the
            # installed alias. Both paths identify this location, not another
            # copy of a skill with the same name.
            location_paths = {norm(p) for p in (loc.get('path'), loc.get('resolved_path')) if p}
            observations = [o for o in s.get('observations', []) if not loc or norm(o.get('path', '.')) in location_paths]
            discovered = [o for o in observations if o['kind'] == 'discovery']
            session = [o for o in observations if o['kind'] == 'session']
            # A plugin discovered for a cwd is inherited there; a bare cache is not installed.
            if plugin and (discovered or session):
                scope = 'global'
            enabled = s.get('activation', {}).get('enabled') if s.get('activation', {}).get('supported') else None
            if enabled is None and discovered:
                enabled = any(o.get('enabled') is True for o in discovered)
            installed = bool(e['present']) and (not plugin or bool(discovered or session))
            component = {'id': s['id']+':'+hashlib.sha256(e['installation_path'].encode()).hexdigest()[:10],
                'skill_id': s['id'], 'kind': 'skill', 'name': s['name'], 'title': s.get('title_ru') or s['name'],
                'scope': scope, 'installed': installed, 'enabled': enabled,
                'project_path': e['project_path'], 'path': loc.get('path', ''),
                'version': loc.get('package_version') or s.get('declared_version'),
                'fingerprint': loc.get('skill_sha256') or loc.get('sha256'),
                'observations': observations, 'restriction': overrides.get('restrictions', {}).get(s['name'], ''),
                'basis': 'Обнаружение Codex' if discovered else 'Метаданные чата' if session else 'Файл инструкции' if installed else 'Прежняя запись; установка не подтверждена',
                'checked_at': s.get('last_seen')}
            a['components'].append(component)
        for related in s.get('resource_ids', []):
            if related != rid:
                a['related'].append(related)
    # A plugin observed in the chat is a supplied bundle even if desktop config omits it.
    for a in groups.values():
        plugin_skills = [s for s in a['skills'] if s['id'].startswith('plugin:')]
        if plugin_skills and not any(c['kind'] == 'plugin' for c in a['components']):
            installed = any(c['installed'] for c in a['components'] if c['kind'] == 'skill')
            a['components'].insert(0, {'id': a['id']+':bundle', 'kind': 'plugin',
                'name': plugin_skills[0]['id'].split(':')[1], 'scope': 'global' if installed else 'unknown',
                'installed': installed, 'enabled': None, 'basis': 'Пакет навыка; отдельная настройка включения не получена'})
        for s in plugin_skills:
            for app_id in s.get('bundle', {}).get('apps', []):
                cid = 'app:'+app_id
                if cid in alias and alias[cid] != a['id'] and alias[cid] in groups:
                    a['related'].append(alias[cid])
                    continue
                if not any(c['id'] == cid for c in a['components']):
                    a['components'].append({'id': cid, 'kind': 'app', 'name': s['bundle'].get('title') or app_id,
                        'scope': 'unknown', 'installed': False, 'enabled': None,
                        'basis': 'Зависимость из описания пакета; подключение аккаунта отдельно не подтверждено'})
    for r in resources:
        ids = r.get('connection_ids', [])
        if ids and all(alias.get(cid, r['id']) != r['id'] for cid in ids):
            continue
        if r['id'] not in groups:
            a = group(r['id'])
            a['suggested'] = True
        groups[r['id']]['related'] += [skill_groups[s['id']] for s in r.get('skills', []) if s['id'] in skill_groups and skill_groups[s['id']] != r['id']]
    for a in groups.values():
        a['related'] = sorted(set(a['related']) - {a['id']})
        a['notes'] = list(dict.fromkeys(str(n) for n in a['notes']))
    return sorted(groups.values(), key=lambda a: a['title'].casefold())
