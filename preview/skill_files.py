"""Explicit local skill operations. Known ids only; never run skill instructions."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid
import stat
from datetime import datetime, timezone

from skill_sources import instruction


class SkillFileError(ValueError):
    pass


def identity(info):
    return {'device':info.st_dev, 'inode':info.st_ino, 'size':info.st_size,
            'modified_ns':info.st_mtime_ns}


def directory_identity(path):
    info = path.stat()
    return {'device':info.st_dev, 'inode':info.st_ino}


def save_receipt(path, value):
    temporary = path.with_name('receipt-'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.flush(); os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class LockedInstruction:
    """Windows denies writers/replacements; deletion targets the opened file handle."""
    def __init__(self, path, create=False):
        self.path, self.create, self.deleted = Path(path), create, False

    def __enter__(self):
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            self.kernel.CreateFileW.restype = wintypes.HANDLE
            handle = self.kernel.CreateFileW(str(self.path), 0x80000000 | 0x10000 | (0x40000000 if self.create else 0),
                1, None, 1 if self.create else 3, 0x200000, None)  # CREATE_NEW / OPEN_EXISTING, no reparse following
            if handle == ctypes.c_void_p(-1).value:
                raise SkillFileError('Файл занят, недоступен или уже заменён. Закройте редактор и откройте подтверждение заново.')
            try: descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if self.create else os.O_RDONLY))
            except Exception:
                self.kernel.CloseHandle(wintypes.HANDLE(handle)); raise
            self.file = os.fdopen(descriptor, 'w+b' if self.create else 'rb')
            self.handle = msvcrt.get_osfhandle(self.file.fileno())
        else:
            import fcntl
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL if self.create else os.O_RDONLY
            self.file = os.fdopen(os.open(self.path, flags | getattr(os, 'O_NOFOLLOW', 0), 0o600), 'w+b' if self.create else 'rb')
            try: fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception:
                self.file.close(); raise SkillFileError('Файл занят другой операцией.')
        self.info = os.fstat(self.file.fileno())
        if not stat.S_ISREG(self.info.st_mode) or self.info.st_nlink != 1:
            self.file.close()
            raise SkillFileError('Инструкция должна быть обычным файлом без жёстких ссылок.')
        return self

    def mark_delete(self, enabled=True):
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            self.kernel.SetFileInformationByHandle.restype = wintypes.BOOL
            flag = ctypes.c_ubyte(1 if enabled else 0)
            if not self.kernel.SetFileInformationByHandle(self.handle, 4, ctypes.byref(flag), ctypes.sizeof(flag)):
                raise SkillFileError('Не удалось изменить состояние выбранного файла. Резервная копия сохранена.')
        self.deleted = enabled

    def __exit__(self, kind, error, trace):
        try:
            if self.deleted and os.name != 'nt':
                if identity(self.path.stat()) != identity(os.fstat(self.file.fileno())):
                    raise SkillFileError('Файл заменён другой операцией. Удаление отменено.')
                self.path.unlink()
        finally:
            self.file.close()


def component(snapshot, payload):
    addon = next((a for a in snapshot.get('addons', []) if a['id'] == payload.get('id')), {})
    result = next((c for c in addon.get('components', []) if c['id'] == payload.get('component_id') and c['kind'] == 'skill'), None)
    if not result or not result.get('path'):
        raise SkillFileError('Файл навыка не найден в последней сверке.')
    return result


def bundle_digest(folder):
    """Bounded, no links/junctions, all support files included in the preview revision."""
    digest, count, size = hashlib.sha256(), 0, 0
    for base, dirs, files in os.walk(folder, followlinks=False):
        dirs.sort()
        for name in sorted([*dirs, *files]):
            path = Path(base)/name
            if path.is_symlink() or path.is_junction():
                raise SkillFileError('В папке навыка есть ссылки. Управляйте этой установкой вручную.')
        for name in sorted(files):
            path = Path(base)/name
            count += 1
            size += path.stat().st_size
            if count > 2000 or size > 50*1024*1024:
                raise SkillFileError('Комплект слишком большой для операции каталога: предел 2000 файлов и 50 МБ.')
            digest.update(path.relative_to(folder).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest(), count


class SkillFiles:
    def __init__(self, settings, work):
        self.home = Path(settings.get('home') or Path.home()).resolve()
        self.work = Path(work).resolve()

    def roots(self, snapshot):
        roots = [self.home/'.agents/skills', self.home/'.codex/skills']
        roots += [Path(p['path'])/sub for p in snapshot.get('projects', [])
                  for sub in ('.agents/skills', '.codex/skills')]
        return roots

    def removable(self, snapshot, c):
        if not c.get('installed') or c.get('managed_package') or c.get('skill_id', '').startswith('plugin:'):
            return False
        path = Path(c.get('path', ''))
        return self.allowed_instruction(snapshot, path)

    def allowed_instruction(self, snapshot, path):
        if path.name != 'SKILL.md' or not path.is_absolute(): return False
        for root in self.roots(snapshot):
            try: relative = path.relative_to(root)
            except ValueError: continue
            if len(relative.parts) >= 2 and relative.parts[0] != '.system' and '..' not in relative.parts:
                return True
        return False

    def safe_instruction(self, snapshot, path):
        if not self.allowed_instruction(snapshot, path) or path.resolve() != path.absolute() or path.is_symlink():
            raise SkillFileError('Путь инструкции изменён или перенаправлен ссылкой. Сверьте каталог с Codex.')
        if not path.parent.is_dir(): raise SkillFileError('Исходная папка навыка недоступна.')

    def removed(self):
        result = []
        root = self.work/'removed-skills'
        if not root.is_dir(): return result
        for file in sorted(root.glob('*/receipt.json')):
            try:
                row = self.receipt(file.parent.name)
                result.append({key:row.get(key) for key in ('operation_id','id','name','source','target','status','at','restored_at')})
            except (SkillFileError, OSError, ValueError): continue
        return result

    def receipt(self, operation_id):
        if not isinstance(operation_id,str) or not re.fullmatch(r'[a-f0-9]{32}',operation_id):
            raise SkillFileError('Неизвестная резервная копия навыка.')
        directory = self.work/'removed-skills'/operation_id
        if directory.resolve() != directory.absolute(): raise SkillFileError('Папка резервной копии перенаправлена ссылкой.')
        file = directory/'receipt.json'
        if file.is_symlink(): raise SkillFileError('Недопустимая ссылка на запись операции.')
        try: result = json.loads(file.read_text(encoding='utf-8'))
        except (OSError, ValueError): raise SkillFileError('Запись резервной копии недоступна.')
        if result.get('kind') != 'instruction_only' or result.get('operation_id') != operation_id:
            raise SkillFileError('Формат резервной копии не поддерживается.')
        return result

    def restore_plan(self, snapshot, payload):
        row = self.receipt(payload.get('operation_id'))
        if row.get('status') not in ('removed', 'prepared'):
            raise SkillFileError('Эта инструкция уже восстановлена или удаление было отменено.')
        target = Path(row['source'])
        self.safe_instruction(snapshot, target)
        if target.exists() or target.is_symlink():
            raise SkillFileError('По исходному пути уже есть файл. Восстановление не заменяет существующие инструкции.')
        if directory_identity(target.parent) != row.get('parent_identity'):
            raise SkillFileError('Исходная папка была заменена. Автоматическое восстановление отменено.')
        backup = self.work/'removed-skills'/row['operation_id']/'SKILL.md'
        if backup.is_symlink() or not backup.is_file(): raise SkillFileError('Резервная инструкция недоступна.')
        raw = backup.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row.get('sha256'):
            raise SkillFileError('Резервная инструкция изменилась. Восстановление отменено.')
        result = {key:row[key] for key in ('id','component_id','name','description','target','operation_id','sha256','parent_identity')}
        result.update(action='restore',kind='instruction_only',source=str(backup),destination=str(target),files=1,
                      source_identity=identity(backup.stat()), preserved_directory=str(target.parent))
        result['revision'] = hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
        return result

    def decorate(self, snapshot):
        for addon in snapshot.get('addons', []):
            for c in addon.get('components', []):
                if c['kind'] != 'skill': continue
                c['file_actions'] = {
                    'remove': self.removable(snapshot, c),
                    'install': bool(c.get('file_found') and not c.get('installed') and not c.get('managed_package') and not c.get('skill_id', '').startswith('plugin:')),
                    'reason': 'Встроенные навыки, ссылки и части плагинов обслуживаются вместе с их пакетом.'}
        return snapshot

    def plan(self, snapshot, payload):
        if payload.get('action') == 'restore': return self.restore_plan(snapshot, payload)
        c = component(snapshot, payload)
        path = Path(c['path'])
        if path.name != 'SKILL.md' or not path.is_file():
            raise SkillFileError('Файл навыка уже недоступен. Сверьте каталог с Codex.')
        source = path.parent
        if source.is_symlink() or source.is_junction():
            raise SkillFileError('Это ссылка на папку навыка. Управляйте ею вручную.')
        source = source.resolve()
        name, description, _ = instruction(path)
        action = payload.get('action')
        if action == 'remove':
            if not self.removable(snapshot, c):
                raise SkillFileError('Удалять можно отдельные личные и проектные установки. Встроенные навыки и части плагинов здесь не удаляются.')
            self.safe_instruction(snapshot, path)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SkillFileError('Инструкция должна быть обычным файлом без жёстких ссылок.')
            project = next((p for p in snapshot.get('projects', []) if path.is_relative_to(Path(p['path']))), None)
            target = 'Проект · '+project['name'] if project else 'Лично · все проекты этого пользователя'
            raw = path.read_bytes()
            result = {'action':'remove','kind':'instruction_only','id':payload['id'],'component_id':c['id'],
                'name':name,'description':description,'source':str(path),'destination':None,'target':target,'files':1,
                'sha256':hashlib.sha256(raw).hexdigest(),'source_identity':identity(info),
                'parent_identity':directory_identity(path.parent),'preserved_directory':str(path.parent)}
            result['revision'] = hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
            return result
        elif action == 'install':
            if c.get('installed') or c.get('managed_package') or c.get('skill_id', '').startswith('plugin:'):
                raise SkillFileError('Этот навык уже подтверждён Codex или управляется плагином.')
            project_id = payload.get('project_id')
            project = next((p for p in snapshot.get('projects', []) if p['id'] == project_id), None)
            if project_id and (not project or project.get('source') != 'codex' or not Path(project['path']).is_dir()):
                raise SkillFileError('Папка выбранного проекта недоступна. Сверьте список с Codex.')
            root = (Path(project['path']) if project else self.home)/'.agents/skills'
            leaf = re.sub(r'[^a-zA-Z0-9_-]+', '-', name).strip('-')[:80]
            if not leaf: raise SkillFileError('В инструкции нет подходящего имени для папки установки.')
            destination = root/leaf
            if destination.exists() or destination.is_symlink():
                raise SkillFileError('В выбранной области уже есть такая папка. Каталог не заменяет существующие навыки.')
            # Resolve the parent too, so a junction cannot silently redirect installation.
            if root.resolve() != root.absolute():
                raise SkillFileError('Папка установки перенаправлена ссылкой. Управляйте этой установкой вручную.')
            target = project['name'] if project else 'Лично · все проекты этого пользователя'
        else:
            raise SkillFileError('Неизвестная операция с файлом навыка.')
        fingerprint, files = bundle_digest(source)
        result = {'action':action, 'id':payload['id'], 'component_id':c['id'], 'name':name,
                  'description':description, 'source':str(source), 'destination':str(destination) if destination else None,
                  'project_id':payload.get('project_id') if action == 'install' else None, 'target':target, 'files':files}
        result['revision'] = hashlib.sha256((json.dumps(result,sort_keys=True)+fingerprint).encode()).hexdigest()
        return result

    def apply(self, snapshot, payload, record):
        if payload.get('confirmed') is not True:
            raise SkillFileError('Подтвердите конкретную операцию после просмотра папки и области.')
        plan = self.plan(snapshot, payload)
        if payload.get('revision') != plan['revision']:
            raise SkillFileError('Файлы или область изменились после просмотра. Откройте подтверждение заново.')
        source = Path(plan['source'])
        op_id = uuid.uuid4().hex
        if plan['action'] == 'remove':
            return self.remove_instruction(plan, op_id, record)
        if plan['action'] == 'restore':
            return self.restore_instruction(plan, record)
        destination = Path(plan['destination'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        # No merge and no overwrite. Preserve the original finding unchanged.
        stage = destination.parent.parent/('catalogue-install-'+op_id)
        try:
            shutil.copytree(source, stage)
            expected = self.plan(snapshot, payload)['revision']
            if expected != plan['revision'] or bundle_digest(source)[0] != bundle_digest(stage)[0]:
                raise SkillFileError('Исходный комплект изменился во время копирования. Установка отменена.')
            if destination.exists(): raise SkillFileError('Папка назначения появилась во время установки. Замена отменена.')
            stage.rename(destination)
            try: record({**plan, 'operation_id':op_id})
            except Exception:
                destination.rename(stage)
                raise
        finally:
            if stage.exists() and stage.parent == destination.parent.parent:
                shutil.rmtree(stage)
        return plan

    def remove_instruction(self, plan, op_id, record):
        source = Path(plan['source'])
        destination = self.work/'removed-skills'/op_id/'SKILL.md'
        if destination.parent.resolve() != destination.parent.absolute():
            raise SkillFileError('Папка резервных копий перенаправлена ссылкой.')
        with LockedInstruction(source) as selected:
            raw = selected.file.read()
            if identity(selected.info) != plan['source_identity'] or hashlib.sha256(raw).hexdigest() != plan['sha256']:
                raise SkillFileError('Выбранная инструкция изменилась. Откройте подтверждение заново.')
            if directory_identity(source.parent) != plan['parent_identity']:
                raise SkillFileError('Папка инструкции была заменена. Удаление отменено.')
            destination.parent.mkdir(parents=True, exist_ok=False)
            with destination.open('xb') as backup:
                backup.write(raw); backup.flush(); os.fsync(backup.fileno())
            receipt_path = destination.parent/'receipt.json'
            receipt = {**plan,'operation_id':op_id,'backup':str(destination),'status':'prepared',
                       'at':datetime.now(timezone.utc).isoformat()}
            save_receipt(receipt_path, receipt)
            try:
                selected.mark_delete()
                receipt['status'] = 'removed'
                save_receipt(receipt_path, receipt)
                record(receipt)
            except Exception:
                selected.mark_delete(False)
                receipt['status'] = 'cancelled'
                save_receipt(receipt_path, receipt)
                raise
        return receipt

    def restore_instruction(self, plan, record):
        row = self.receipt(plan['operation_id'])
        receipt_path = self.work/'removed-skills'/plan['operation_id']/'receipt.json'
        with LockedInstruction(plan['source']) as backup:
            raw = backup.file.read()
            if identity(backup.info) != plan['source_identity'] or hashlib.sha256(raw).hexdigest() != plan['sha256']:
                raise SkillFileError('Резервная инструкция изменилась. Восстановление отменено.')
            with LockedInstruction(plan['destination'], create=True) as restored:
                try:
                    restored.file.write(raw); restored.file.flush(); os.fsync(restored.file.fileno())
                    if directory_identity(Path(plan['destination']).parent) != plan['parent_identity']:
                        raise SkillFileError('Папка назначения была заменена. Восстановление отменено.')
                    updated = {**row,'status':'restored','restored_at':datetime.now(timezone.utc).isoformat()}
                    save_receipt(receipt_path, updated)
                    record(plan)
                except Exception:
                    restored.mark_delete()
                    save_receipt(receipt_path, row)
                    raise
        return plan
