"""Reconcile independent discovery inputs against the final displayed inventory."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from model import norm

def audit(inventory, views, addons, session, projects, home=None):
    components = [c for a in addons for c in a['components']]
    represented_paths = {norm(c['path']) for c in components if c.get('path') and c.get('installed')}
    expected_paths = set()
    for skill in inventory.get('skills', {}).values():
        observed = {norm(o['path']) for o in skill.get('observations', []) if o.get('path')}
        for loc in skill.get('locations', []):
            if loc.get('kind') != 'cache' or norm(loc['path']) in observed:
                expected_paths.add(norm(loc['path']))
    session_paths = {norm(s['path']) for s in session.get('skills', [])}
    filesystem_paths = set()
    if home is not None:
        roots = [Path(home)/'.agents/skills', Path(home)/'.codex/skills']
        roots += [Path(p['path'])/sub for p in projects for sub in ('.agents/skills', '.codex/skills')]
        for root in roots:
            if root.is_dir():
                filesystem_paths.update(norm(p) for p in root.rglob('SKILL.md') if p.is_file())
        expected_paths.update(filesystem_paths)
    expected_connections = {(key, c['id']) for key, v in views.items() for c in v.get('services', []) if c.get('configured')}
    represented_connections = {(key, c['id']) for c in components for key, facts in c.get('contexts', {}).items() if facts.get('installed')}
    ids = Counter(c['id'] for c in components)
    missing = sorted(expected_paths - represented_paths)
    connection_missing = sorted(expected_connections - represented_connections)
    session_missing = sorted(session_paths - represented_paths)
    duplicates = sorted(k for k, n in ids.items() if n > 1)
    source_failures = [key for key, view in views.items() if view.get('status') != 'effective' or view.get('apps_status') != 'reported']
    if inventory.get('discovery_status') != 'ok':
        source_failures.append('skills/list')
    return {'at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Файлы навыков, обнаружение Codex, настройки каждой зарегистрированной папки, приложения аккаунта и переданный список текущего чата.',
        'skill_paths': len(expected_paths), 'session_skills': len(session_paths),
        'filesystem_paths': len(filesystem_paths),
        'connections': len({cid for _, cid in expected_connections}), 'project_contexts': len(projects),
        'missing_skill_paths': missing, 'missing_connections': connection_missing,
        'missing_session_paths': session_missing, 'duplicate_component_ids': duplicates,
        'source_failures': source_failures,
        'complete': not (missing or connection_missing or session_missing or duplicates or source_failures),
        'limits': 'Другие компьютеры, незарегистрированные папки, все открытые чаты и успешность сервисных операций не проверяются. Программы — только явно указанные исполняемые файлы.'}
