"""Personal classification and stable dates, kept outside discovery snapshots."""
from datetime import datetime, timezone

ORIGINS = {'asemic', 'builtin', 'personal', 'third_party', 'unknown'}
BILLINGS = {'free', 'included', 'paid', 'mixed', 'unknown'}


def selection(value, allowed):
    if not isinstance(value, list) or len(value) > 100 or any(not isinstance(x, str) or x not in allowed for x in value):
        raise ValueError('Выберите значения из предложенного списка.')
    return list(dict.fromkeys(value))


def metadata(payload, directions):
    return {key: selection(payload.get(key), allowed) for key, allowed in (
        ('origins', ORIGINS), ('billings', BILLINGS), ('directions', {d['id'] for d in directions}))}


def tags(text):
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError('Введите теги через запятую, до 20 000 символов.')
    result = list(dict.fromkeys(t.strip() for t in text.split(',') if t.strip()))
    if len(result) > 100 or any(len(t) > 120 for t in result):
        raise ValueError('Допустимо до 100 тегов, каждый до 120 символов.')
    return result


def valid_date(value):
    try:
        if not isinstance(value, str): return None
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def addition_dates(addons, registry, inventory, stamp):
    """Migrate only proven skill dates. Unknown historical dates stay unknown."""
    initial = not registry.get('initialized')
    items = registry.setdefault('items', {})
    changed = False
    for addon in addons:
        key = addon['id']
        if key not in items:
            if initial:
                parts = addon.get('components', [])
                dates = [valid_date(inventory.get(c.get('skill_id'), {}).get('first_seen')) for c in parts if c.get('kind') == 'skill']
                known = bool(dates) and all(c.get('kind') in ('skill', 'program') for c in parts) and all(dates)
                at = min(dates) if known else None
                basis = 'skill_first_seen' if known else 'unknown'
            else:
                at, basis = valid_date(stamp), 'catalog_first_seen'
            items[key] = {'at': at, 'basis': basis}
            changed = True
        addon['added_at'] = items[key]['at']
        addon['added_basis'] = items[key]['basis']
    if addons and initial:
        registry.update(schema=1, initialized=True)
        changed = True
    return changed
