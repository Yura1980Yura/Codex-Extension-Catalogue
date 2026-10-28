"""A cheap local change signature. Never read secrets into the response or log."""
from pathlib import Path
import hashlib
import json

def signature(settings, work):
    home = Path(settings.get('home') or Path.home())
    paths = {home/'.codex/config.toml', home/'.codex/AGENTS.md'}
    # Desktop state contains chat activity; watch only the project registry.
    try:
        state = json.loads((home/'.codex/.codex-global-state.json').read_text('utf-8-sig'))
        registry = state.get('local-projects', {})
        projects = [(k, p.get('name'), p.get('rootPaths', [])) for k, p in registry.items()]
    except (OSError, ValueError):
        projects = []
    roots = {Path(p['path']) for p in settings.get('projects', [])}
    roots.update(Path(roots[0]) for _, _, roots in projects if roots)
    try:
        snapshot = json.loads((Path(work)/'snapshot.json').read_text('utf-8'))
        roots.update(Path(p['path']) for p in snapshot.get('projects', []))
        paths.update(Path(d['path']) for d in snapshot.get('documents', []) if d.get('path'))
    except (OSError, ValueError):
        pass
    skill_roots = [home/'.agents/skills', home/'.codex/skills', home/'.codex/plugins/cache']
    for root in roots:
        paths.update([root/'AGENTS.md', root/'.codex/config.toml'])
        skill_roots.extend([root/'.agents/skills', root/'.codex/skills'])
    for root in skill_roots:
        if root.exists():
            paths.update(root.rglob('SKILL.md'))
            if root.name == 'cache':
                paths.update(root.rglob('plugin.json'))
    data = Path(settings.get('source_data') or home/'.codex/skill-catalog')
    paths.update(data/n for n in ('inventory.json', 'user.json', 'settings.json', 'history.jsonl', 'connection-checks.json'))
    if settings.get('session'):
        paths.add(Path(settings['session']))
    stats = []
    for p in sorted(paths, key=str):
        try:
            s = p.stat(); stats.append((str(p), s.st_mtime_ns, s.st_size))
        except OSError:
            stats.append((str(p), None, None))
    return hashlib.sha256(json.dumps([projects, stats], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
