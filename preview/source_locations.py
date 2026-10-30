"""Known local source paths. Browser requests select an ID, never a raw path."""
import hashlib
import os
from pathlib import Path


def locations(addon, component):
    candidates = [(component.get('path'), 'Файл' if component.get('kind') != 'program' else 'Программа')]
    candidates += [(s.get('path'), 'Настройка Codex') for s in component.get('sources', []) if isinstance(s, dict)]
    if component.get('kind') == 'plugin':
        name = component.get('config_name') or component.get('name', '')
        for skill in addon.get('skills', []):
            owner = skill.get('id', '').split(':')[1:2]
            if owner and owner[0] == name:
                candidates.append((skill.get('bundle', {}).get('path'), 'Описание плагина'))
    result, seen = [], set()
    for raw, label in candidates:
        if not isinstance(raw, str) or not raw or not Path(raw).is_absolute(): continue
        path = Path(raw)
        key = os.path.normcase(os.path.abspath(path))
        if key in seen: continue
        seen.add(key)
        available = path.is_file() or path.is_dir()
        result.append({'id': hashlib.sha256(key.encode()).hexdigest()[:24], 'path': str(path),
                       'label': label, 'available': available})
    return result


def decorate(snapshot):
    for addon in snapshot.get('addons', []):
        for component in addon.get('components', []):
            if component.get('contexts'):
                for facts in component['contexts'].values():
                    facts['source_locations'] = locations(addon, {**component, **facts})
            else:
                component['source_locations'] = locations(addon, component)
    return snapshot


def folder(snapshot, payload):
    addon = next((a for a in snapshot.get('addons', []) if a['id'] == payload.get('id')), None)
    component = next((c for c in (addon or {}).get('components', []) if c['id'] == payload.get('component_id')), None)
    if not component: raise ValueError('Источник не найден. Обновите каталог.')
    if component.get('contexts'):
        facts = component['contexts'].get(payload.get('context', 'all'))
        if facts is None: raise ValueError('Источник не найден в выбранном проекте.')
        component = {**component, **facts}
    entry = next((x for x in locations(addon, component) if x['id'] == payload.get('source_id')), None)
    if not entry: raise ValueError('Путь не принадлежит выбранной записи каталога.')
    path = Path(entry['path'])
    if not entry['available']: raise ValueError('Файл или папка уже недоступны. Сверьте каталог с Codex.')
    return path.resolve() if path.is_dir() else path.resolve().parent
