"""Reconcile independent discovery inputs against the final displayed inventory."""
from runtime_paths import codex_dir
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from model import norm

def audit(inventory, views, addons, session, projects, home=None):
    components = [c for a in addons for c in a['components']]
    skills = [c for c in components if c.get('kind') == 'skill' and c.get('path')]
    # A catalogue record exists even when Codex has not confirmed its availability.
    # Disabled discoveries still confirm presence; execution is never required.
    represented_paths = {norm(c['path']) for c in skills}
    confirmed_paths = {norm(c['path']) for c in skills
                       if any(o.get('kind') == 'discovery' for o in c.get('observations', []))}
    expected_paths = set()
    for skill in inventory.get('skills', {}).values():
        observed = {norm(o['path']) for o in skill.get('observations', []) if o.get('path')}
        for loc in skill.get('locations', []):
            if loc.get('kind') != 'cache' or norm(loc['path']) in observed:
                expected_paths.add(norm(loc['path']))
    session_paths = {norm(s['path']) for s in session.get('skills', [])}
    filesystem_paths = set()
    if home is not None:
        roots = [Path(home)/'.agents/skills', codex_dir(home)/'skills']
        roots += [Path(p['path'])/sub for p in projects for sub in ('.agents/skills', '.codex/skills')]
        for root in roots:
            if root.is_dir():
                filesystem_paths.update(norm(p) for p in root.rglob('SKILL.md') if p.is_file())
        expected_paths.update(filesystem_paths)
    expected_connections = {(key, c['id']) for key, v in views.items() for c in v.get('services', []) if c.get('configured')}
    represented_connections = {(key, c['id']) for c in components for key in c.get('contexts', {})}
    ids = Counter(c['id'] for c in components)
    missing = sorted(expected_paths - represented_paths)
    connection_missing = sorted(expected_connections - represented_connections)
    session_missing = sorted(session_paths - represented_paths)
    compared_paths = expected_paths | session_paths
    missing_record_paths = sorted(compared_paths - represented_paths)
    unconfirmed_paths = sorted((compared_paths & represented_paths) - confirmed_paths)
    # Keep per-source/context diagnostics, but count each missing entity only once.
    missing_connection_ids = sorted({cid for _, cid in connection_missing})
    missing_record_count = len(missing_record_paths) + len(missing_connection_ids)
    duplicates = sorted(k for k, n in ids.items() if n > 1)
    source_failures = [key for key, view in views.items() if view.get('status') != 'effective' or view.get('apps_status') != 'reported']
    if inventory.get('discovery_status') != 'ok':
        source_failures.append('skills/list')
    return {'schema_version': 2, 'at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Файлы навыков, обнаружение Codex, настройки каждой зарегистрированной папки, приложения аккаунта и переданный список текущего чата.',
        'skill_paths': len(expected_paths), 'session_skills': len(session_paths),
        'filesystem_paths': len(filesystem_paths),
        'connections': len({cid for _, cid in expected_connections}), 'project_contexts': len(projects),
        'missing_skill_paths': missing, 'missing_connections': connection_missing,
        'missing_session_paths': session_missing, 'duplicate_component_ids': duplicates,
        'compared_skill_paths': len(compared_paths),
        'missing_record_paths': missing_record_paths, 'missing_connection_ids': missing_connection_ids,
        'missing_record_count': missing_record_count, 'unconfirmed_skill_paths': unconfirmed_paths,
        'source_failures': source_failures,
        'complete': not (missing_record_count or duplicates or source_failures),
        'limits': 'Другие компьютеры, незарегистрированные папки, все открытые чаты и успешность сервисных операций не проверяются. Программы — только явно указанные исполняемые файлы.'}
