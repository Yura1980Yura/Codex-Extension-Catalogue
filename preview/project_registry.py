"""Read only public-facing names and primary folders from Codex desktop state.

This is a local adapter, not a supported Codex API. Extra rootPaths are access
permissions, not proof that all those folders are the project's source tree.
"""
from pathlib import Path
import json
from model import norm

def registered_projects(home, project_id):
    path = Path(home)/'.codex/.codex-global-state.json'
    try:
        state = json.loads(path.read_text('utf-8-sig'))
    except (OSError, ValueError):
        return [], 'Список проектов Codex сейчас недоступен. Показан последний подтверждённый список.'
    values = state.get('local-projects')
    if not isinstance(values, dict):
        return [], 'Формат списка проектов Codex изменился.'
    order = state.get('project-order', [])
    result = []
    for key in list(dict.fromkeys([*order, *values])):
        raw = values.get(key, {})
        roots = raw.get('rootPaths', [])
        if not roots or not isinstance(roots[0], str):
            continue
        folder = Path(roots[0])
        if not folder.is_absolute():
            continue
        result.append({'id': project_id(str(folder)), 'name': raw.get('name') or folder.name,
            'path': str(folder), 'codex_id': key, 'source': 'codex',
            'available': folder.is_dir(), 'additional_folders': [r for r in roots[1:] if isinstance(r, str)]})
    return result, None

def merge_projects(existing, registry):
    # Only the native registry establishes project membership, names and order.
    return [dict(p) for p in registry]
