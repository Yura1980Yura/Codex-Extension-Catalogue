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
        return [], 'Список проектов Codex сейчас недоступен; сохранены папки каталога.'
    values = state.get('local-projects', {})
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
    by_path = {norm(p['path']): {**p, 'source': 'catalog', 'available': Path(p['path']).is_dir()} for p in existing}
    for p in registry:
        by_path[norm(p['path'])] = {**by_path.get(norm(p['path']), {}), **p}
    # Preserve distinct folders even when their human names coincide.
    names = {p['name'].casefold() for p in registry}
    for p in by_path.values():
        if p['source'] != 'codex' and p['name'].casefold() in names:
            p['name'] += ' · ' + Path(p['path']).name
            p['name_note'] = 'Отдельная папка каталога. У одноимённого проекта в Codex другой путь.'
    ordered = [by_path[norm(p['path'])] for p in registry]
    ordered.extend(p for p in by_path.values() if p['source'] != 'codex')
    return ordered
