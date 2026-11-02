"""Read-only GitHub source discovery. Local instructions are never uploaded."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
import hashlib
import json
import re
import shutil
import subprocess
import threading

from skill_repositories import REPOSITORY, REVISION, write_cache

OFFICIAL = ('openai/codex', 'openai/skills')


def github_repository(value, shorthand=False):
    if not isinstance(value, str): return None
    match = re.fullmatch(r'git@github\.com:([\w.-]+/[\w.-]+?)(?:\.git)?', value)
    if match: return match[1]
    if shorthand and REPOSITORY.fullmatch(value): return value.removesuffix('.git')
    try:
        url = urlsplit(value)
        parts = url.path.strip('/').split('/')
        repository = '/'.join(parts[:2]).removesuffix('.git')
        if url.hostname == 'github.com' and url.port in (None, 443, 22) and url.scheme in ('https', 'http', 'ssh') and parts[0].lower() not in ('topics', 'orgs', 'settings', 'search', 'login', 'apps') and REPOSITORY.fullmatch(repository):
            return repository
    except ValueError: pass
    return None


def valid_path(value):
    return isinstance(value, str) and value and not value.startswith('/') and not any(p in ('.', '..') for p in value.split('/')) and not re.search(r'[\\:\x00-\x1f\x7f]', value)


def valid_rows(rows):
    if not isinstance(rows, list): return []
    return [row for row in rows if isinstance(row, dict) and valid_path(row.get('path')) and Path(row['path']).name == 'SKILL.md' and isinstance(row.get('sha'), str) and REVISION.fullmatch(row['sha'])]


def instruction_hashes(raw):
    normalized = raw.removeprefix(b'\xef\xbb\xbf').replace(b'\r\n', b'\n')
    return {hashlib.sha1(b'blob '+str(len(text)).encode()+b'\0'+text).hexdigest() for text in (raw, normalized)}


def git_source(path):
    options = dict(capture_output=True, text=True, encoding='utf-8', timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        result = subprocess.run(['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'], **options)
        if result.returncode: return None
        root = Path(result.stdout.strip()).resolve()
        relative = path.resolve().relative_to(root).as_posix()
        remotes = subprocess.run(['git', '-C', str(root), 'remote'], **options).stdout.splitlines()
        repository = None
        for remote_name in sorted(remotes, key=lambda name: name != 'origin'):
            remote = subprocess.run(['git', '-C', str(root), 'remote', 'get-url', remote_name], **options)
            repository = github_repository(remote.stdout.strip()) if not remote.returncode else None
            if repository: break
        if not repository: return None
        branch = subprocess.run(['git', '-C', str(root), 'branch', '--show-current'], **options).stdout.strip()
        return {'repository': repository, 'path': relative, 'branch': branch}
    except (OSError, ValueError, subprocess.SubprocessError): return None


class GitHub:
    def __init__(self, previous=None, request=None):
        self.previous = previous if isinstance(previous, dict) else {}
        self.request = request
        self.executable = shutil.which('gh')
        self.available = bool(request or self.executable)
        self.lock = threading.Lock()
        self.calls = 0

    def api(self, endpoint, params=None):
        with self.lock:
            if self.calls >= 120: raise ValueError('Достигнут лимит запросов этой сверки.')
            self.calls += 1
        if self.request: return self.request(endpoint, params or {})
        if not self.executable: raise ValueError('Для проверки GitHub нужен gh с доступом к репозиторию.')
        command = [self.executable, 'api', endpoint, '--method', 'GET']
        for key, value in (params or {}).items(): command += ['-f', f'{key}={value}']
        process = subprocess.run(command, capture_output=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode: raise ValueError('GitHub не подтвердил доступ. Репозиторий может быть приватным или недоступным.')
        return json.loads(process.stdout)

    def index(self, repository, ref=None):
        key = repository+'@'+(ref or 'HEAD')
        previous = self.previous.get(key, {})
        if not isinstance(previous, dict): previous = {}
        repository_checked = None
        try:
            metadata = self.api('repos/'+repository)
            repository_checked = datetime.now(timezone.utc).isoformat()
            branch = ref or metadata['default_branch']
            if not isinstance(branch, str) or not re.fullmatch(r'[\w./-]{1,200}', branch) or '..' in branch.split('/'):
                raise ValueError('Не удалось определить ветку репозитория.')
            commit = self.api('repos/'+repository+'/commits/'+quote(branch, safe=''))
            revision = commit.get('sha')
            if not isinstance(revision, str) or not REVISION.fullmatch(revision): raise ValueError('GitHub не вернул ревизию коммита.')
            files = previous.get('files') if previous.get('revision') == revision else None
            if not isinstance(files, list):
                tree = self.api('repos/'+repository+'/git/trees/'+revision, {'recursive': '1'})
                if tree.get('truncated') or not isinstance(tree.get('tree'), list): raise ValueError('Индекс GitHub неполный.')
                files = [{'path': row['path'], 'sha': row['sha']} for row in valid_rows(tree['tree']) if row.get('type') == 'blob']
            files = valid_rows(files)
            return key, {'repository': repository, 'branch': branch, 'revision': revision, 'files': files,
                         'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'verified'}
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            if previous.get('repository') == repository and isinstance(previous.get('files'), list) and REVISION.fullmatch(str(previous.get('revision', ''))):
                return key, {**previous, 'files': valid_rows(previous['files']), 'status': 'cached', 'warning': 'GitHub недоступен; показана дата сохранённой проверки.'}
            if repository_checked:
                return key, {'repository': repository, 'status': 'repository_only', 'files': [], 'checked_at': repository_checked,
                             'warning': 'Репозиторий доступен; индекс файлов не подтверждён.'}
            return key, {'repository': repository, 'status': 'unavailable', 'files': [], 'warning': 'Доступ к GitHub или ревизия не подтверждены.'}


def source_match(index, row, method, hashes):
    repository = index['repository']; path = row.get('path') if row else None
    folder = path.rsplit('/', 1)[0] if path and '/' in path else None
    revision = index.get('revision')
    exact = bool(row and row.get('sha') in hashes)
    evidence = {'content': 'Найдена публикация с совпадающей инструкцией; это не устанавливает первичное авторство.', 'git': 'Репозиторий подтверждён Git-привязкой установки.',
                'declared': 'Репозиторий указан в метаданных навыка и доступен в GitHub.',
                'related': 'Связанный проект указан в карточке навыка или ресурса; репозиторий доступен в GitHub.',
                'official': 'Официальный репозиторий OpenAI; опубликованный навык имеет то же имя.'}[method]
    if row: evidence += ' Инструкция совпадает.' if exact else ' Локальная версия отличается от опубликованной.'
    elif method == 'git': evidence += ' Файл этой установки в выбранной ветке не опубликован.' if index['status'] == 'verified' else ' Путь файла в GitHub не подтверждён.'
    if index.get('status') == 'cached': evidence += ' Использован сохранённый индекс.'
    if index.get('status') == 'repository_only': evidence += ' Индекс файлов не подтверждён.'
    return {'repository': repository, 'url': 'https://github.com/'+repository,
            'folder_url': f'https://github.com/{repository}/tree/{revision}/{quote(folder, safe="/")}' if folder else None,
            'file_url': f'https://github.com/{repository}/blob/{revision}/{quote(path, safe="/")}' if path and not folder else None,
            'method': method, 'status': 'verified' if index['status'] == 'repository_only' else index['status'], 'exact_instruction': exact, 'checked_at': index.get('checked_at'), 'evidence': evidence}


def discover(addons, instructions, settings, work, request=None):
    work = Path(work); cache_path = work/'skill-source-discovery.json'
    try: previous = json.loads(cache_path.read_text('utf-8'))
    except (OSError, ValueError): previous = {}
    if not isinstance(previous, dict): previous = {}
    github = GitHub(previous.get('repositories'), request)
    entries = []; candidates = set(OFFICIAL)
    for index in github.previous.values():
        repository = index.get('repository') if isinstance(index, dict) else None
        if isinstance(repository, str) and REPOSITORY.fullmatch(repository): candidates.add(repository)
    configured = settings.get('skill_repositories', []) if isinstance(settings, dict) else []
    for entry in configured if isinstance(configured, list) else []:
        repository = github_repository(entry.get('repository'), shorthand=True) if isinstance(entry, dict) else None
        if repository: candidates.add(repository)
    for addon in addons:
        for skill in addon.get('skills', []):
            installed = any(c.get('skill_id') == skill['id'] and c.get('installed') for c in addon.get('components', []))
            instruction = instructions.get(skill['id'])
            if not installed or not instruction: continue
            path = Path(instruction['path']).resolve()
            try: raw = path.read_bytes()
            except OSError:
                skill['repository_discovery'] = {'status': 'unavailable', 'message': 'Инструкция недоступна для проверки.', 'matches': []}; continue
            source = git_source(path); refs = set()
            profile = skill.get('author_profile') or {}; metadata = skill.get('source') or {}
            declared = github_repository(metadata.get('repository'), shorthand=True) or github_repository(metadata.get('url'))
            if declared: refs.add(declared)
            related = set()
            for value in [metadata.get('url'), (addon.get('profile') or {}).get('website'), *[r.get('url') for r in profile.get('links', []) if isinstance(r, dict)]]:
                repository = github_repository(value)
                if repository: refs.add(repository); related.add(repository)
            if source: candidates.add(source['repository'])
            for file in (path, path.parent/'README.md', path.parent/'installation.json', path.parent/'catalog.json'):
                try:
                    if file.is_file() and file.stat().st_size <= 200000:
                        text = file.read_text('utf-8', errors='replace')
                        refs.update(filter(None, (github_repository(url) for url in re.findall(r'https://github\.com/[^\s<>\)\]"\x27]+', text))))
                except OSError: pass
            candidates.update(refs)
            entries.append({'skill': skill, 'path': path, 'source': source, 'hashes': instruction_hashes(raw), 'references': refs,
                            'declared': declared, 'related': related,
                            'official': skill['id'].startswith('system:') or bool(re.search(r'@openai-[^:]+:', skill['id']))})
    if not entries: return {'checked': 0, 'linked': 0, 'unresolved': 0}
    candidates = set(sorted(r for r in candidates if REPOSITORY.fullmatch(r))[:64])
    indexes = {}
    def load(repositories):
        with ThreadPoolExecutor(max_workers=6) as pool:
            for key, value in pool.map(lambda r: github.index(r), sorted(repositories)): indexes[key] = value
    load(candidates)
    # Resolve current project branches as well as repository default branches.
    for entry in entries:
        origin = entry['source']
        if origin and origin['branch']:
            default = indexes.get(origin['repository']+'@HEAD', {})
            if origin['branch'] != default.get('branch') and origin['repository']+'@'+origin['branch'] not in indexes:
                key, value = github.index(origin['repository'], origin['branch']); indexes[key] = value
    # Personal copies can be published in another accessible repository, without a Git remote beside the installed file.
    try:
        owned = github.api('user/repos', {'affiliation': 'owner', 'per_page': '100', 'sort': 'updated'})
        owned = [r['full_name'] for r in owned if isinstance(r, dict) and not r.get('fork') and isinstance(r.get('full_name'), str) and REPOSITORY.fullmatch(r['full_name'])][:24]
        load(set(owned)-candidates)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError): pass
    searches = 0; linked = 0; unresolved = 0
    for entry in entries:
        skill = entry['skill']; matches = []; origin = entry['source']; hashes = entry['hashes']
        for index in indexes.values():
            if not isinstance(index, dict) or index.get('status') not in ('verified', 'cached', 'repository_only') or not REPOSITORY.fullmatch(str(index.get('repository', ''))): continue
            rows = valid_rows(index.get('files', []))
            exact = [r for r in rows if r.get('sha') in hashes]
            if exact: matches.extend(source_match(index, row, 'content', hashes) for row in exact)
            elif origin and index['repository'] == origin['repository']:
                row = next((r for r in rows if r['path'] == origin['path']), None)
                # Prefer the file's branch; a root-only project link remains useful when the skill is not committed.
                matches.append(source_match(index, row, 'git', hashes))
            elif entry['official'] and index['repository'] in OFFICIAL:
                names = {skill['name'].lower(), entry['path'].parent.name.lower()}
                named = [r for r in rows if Path(r['path']).parent.name.lower() in names]
                if len(named) == 1: matches.append(source_match(index, named[0], 'official', hashes))
            elif entry['declared'] == index['repository']:
                matches.append(source_match(index, None, 'declared', hashes))
            elif index['repository'] in entry['related']:
                matches.append(source_match(index, None, 'related', hashes))
        # Search only names and hashes, never local file contents or machine paths.
        search_status = None
        if not matches and searches < 12 and github.available:
            name = re.sub(r'[^A-Za-z0-9_-]', ' ', skill['name']).strip()[:100]
            if name:
                searches += 1
                try:
                    query = f'"{name}" filename:SKILL.md'+(' user:openai' if entry['official'] else '')
                    found = github.api('search/code', {'q': query, 'per_page': '5'})
                    for hit in found.get('items', []):
                        repository = (hit.get('repository') or {}).get('full_name'); path = hit.get('path')
                        if hit.get('sha') not in hashes or not valid_path(path) or not isinstance(repository, str) or not REPOSITORY.fullmatch(repository): continue
                        key, index = github.index(repository); indexes[key] = index
                        row = next((r for r in index.get('files', []) if r.get('path') == path and r.get('sha') in hashes), None)
                        if row: matches.append(source_match(index, row, 'content', hashes))
                    search_status = 'not_found'
                except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError): search_status = 'partial' if github.calls >= 120 else 'unavailable'
        unique = {}
        for match in matches:
            key = match['repository'].lower()
            rank = (match['status'] == 'verified', match['exact_instruction'], bool(match.get('folder_url') or match.get('file_url')))
            old = unique.get(key)
            if not old or rank > old[0]: unique[key] = (rank, match)
        matches = [value[1] for value in unique.values()][:8]
        status = ('verified' if any(m['status'] == 'verified' for m in matches) else 'cached') if matches else search_status or ('partial' if github.available else 'unavailable')
        message = {'verified': 'Найден доступный репозиторий или подтверждённая публикация навыка.',
                   'cached': 'GitHub не подтвердил текущую доступность. Показаны сохранённые сведения с датой проверки.',
                   'not_found': 'Подтверждённый GitHub-источник не найден. Это не доказывает отсутствия приватного или неиндексируемого проекта.',
                   'partial': 'Поиск GitHub ограничен бюджетом этой сверки; часть источников требует повторной проверки.',
                   'unavailable': 'Проверить GitHub не удалось. Нужен доступ gh к репозиториям.'}[status]
        skill['repository_discovery'] = {'status': status, 'checked_at': datetime.now(timezone.utc).isoformat(), 'message': message, 'matches': matches}
        if matches: linked += 1
        else: unresolved += 1
    write_cache(cache_path, {'repositories': indexes})
    return {'checked': len(entries), 'linked': linked, 'unresolved': unresolved, 'requests': github.calls}
