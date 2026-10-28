"""Known-component switches. Native Codex writes, readback, recoverable history.

Browser input never supplies a path or configuration key. The snapshot identifies
the component; the actual user config supplies its current state and revision.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import threading
import uuid

from collect import runtime_path, read

FIELDS = {'mcp':'mcp_servers','plugin':'plugins','app':'apps'}

class ControlError(ValueError): pass
class Conflict(ControlError): pass

class Controls:
    def __init__(self, settings, work, request=None):
        self.home = Path(settings.get('home') or Path.home()).resolve()
        self.source = Path(settings.get('source_data') or self.home/'.codex/skill-catalog').resolve()
        self.work = Path(work)
        runtime = runtime_path(settings)
        sys.path[:0] = [str(runtime/'skill-catalog/scripts')]
        import activation, discovery, journal, storage
        self.activation, self.journal, self.storage = activation, journal, storage
        self.request = request or discovery.request
        self.explicit = read(self.source/'settings.json',{}).get('codex_executable')
        self.lock = threading.Lock()
        self.pending = self.work/'control-pending.json'
        self.recovery_error = False

    def rpc(self, method, params):
        return self.request(method, params, explicit=self.explicit,
            codex_home=self.home/'.codex', process_cwd=str(self.home), timeout=25)[0]

    def descriptor(self, addon, component, facts, config):
        disabled = lambda message: {'supported':False,'message':message}
        if not facts.get('installed'):
            return disabled('Установка этой части не подтверждена. Переключение недоступно.')
        if component['kind']=='skill':
            card = next((s for s in addon.get('skills',[]) if s['id']==component.get('skill_id')),None)
            if not card: return disabled('Инструкция не найдена.')
            result = self.activation.state(card,self.home,config)
            return {**result,'scope':'global','component_id':component['id']}
        field = FIELDS.get(component['kind'])
        if not field:
            return disabled('Это установленная программа. Её запуском управляют Windows и использующее её подключение, а не переключатель Codex.')
        if facts.get('scope')!='global':
            return disabled('Эта настройка принадлежит проекту. Измените её в настройках проекта Codex; глобальный переключатель её не заменяет.')
        if any(s.get('applied') and s.get('scope') not in ('user','account') for s in facts.get('sources',[])):
            return disabled('Есть настройки проекта или организации. Используйте настройки Codex, чтобы не подменить их глобальным значением.')
        name = component.get('config_name') or component['id'].removeprefix(component['kind']+':')
        parsed,fingerprint = config
        row = parsed.get(field,{}).get(name)
        if row is None and field=='apps' and component['id'].startswith('app:') and not name.startswith('_') and any(s.get('scope')=='account' and s.get('path')=='Codex app/installed' for s in facts.get('sources',[])):
            # A confirmed account connector may inherit the documented default.
            # Write a local use preference, never disconnect or authorize an account.
            row = {}
        if not isinstance(row,dict):
            # Account-only/built-in bundles cannot be equated with a local plugin.
            return disabled('Отдельная пользовательская настройка этой части не найдена. Управление доступно в настройках Codex.')
        enabled = row.get('enabled',parsed.get('apps',{}).get('_default',{}).get('enabled',True) if field=='apps' else True)
        if type(enabled) is not bool: return disabled('Неоднозначная настройка включения; проверьте настройки Codex.')
        key = field+'.'+json.dumps(name,ensure_ascii=False)+'.enabled'
        revision = hashlib.sha256((fingerprint+'\0'+key).encode()).hexdigest()
        return {'supported':True,'enabled':enabled,'revision':revision,'scope':'global',
            'component_id':component['id'],'field':field,'name':name,'key':key,
            'message':'На этом компьютере, для всех проектов без собственного переопределения. После изменения перезапустите Codex.'}

    def decorate(self, snapshot):
        snapshot = deepcopy(snapshot)
        try: config = self.activation.configuration(self.home)
        except (OSError,ValueError): config = None
        config_path = self.home/'.codex/config.toml'
        changed_at = config_path.stat().st_mtime*1000 if config_path.exists() else 0
        try: inventory = read(self.source/'inventory.json',{}).get('skills',{})
        except (OSError,ValueError): inventory = {}
        for addon in snapshot.get('addons',[]):
            for component in addon.get('components',[]):
                if component['kind']=='skill':
                    observations = {}
                    for observed in [*component.get('observations',[]),*inventory.get(component.get('skill_id'),{}).get('observations',[])]:
                        key = (observed.get('kind'),str(observed.get('cwd','')).lower(),str(observed.get('path','')).lower())
                        if observed.get('at','')>=observations.get(key,{}).get('at',''):
                            observations[key] = observed
                    component['observations'] = list(observations.values())
                    component['config_changed_at'] = changed_at
                for facts in component.get('contexts',{'all':component}).values():
                    control = self.descriptor(addon,component,facts,config) if config and not self.recovery_error else {'supported':False,'message':'Настройки или незавершённая запись истории требуют проверки. Переключение временно недоступно.'}
                    facts['control'] = {k:v for k,v in control.items() if k not in ('field','name','key')}
                    if control.get('supported'):
                        facts['enabled'] = control['enabled']
                        facts['config_authoritative'] = True
        try:
            snapshot['events'] = self.journal.read_events(self.source)
        except (OSError,ValueError): pass
        snapshot['control_revision'] = config[1] if config else None
        return snapshot

    def resolve(self, snapshot, payload):
        addon = next((a for a in snapshot.get('addons',[]) if a['id']==payload.get('id')),None)
        component = next((c for c in (addon or {}).get('components',[]) if c['id']==payload.get('component_id')),None)
        if not component: raise ControlError('Часть надстройки не найдена. Обновите каталог.')
        context = payload.get('context','all')
        if context!='all' and context not in {p['id'] for p in snapshot.get('projects',[])}:
            raise ControlError('Проект не найден.')
        facts = component.get('contexts',{}).get(context) if 'contexts' in component else component
        if not facts: raise ControlError('Часть не найдена в выбранном проекте.')
        control = self.descriptor(addon,component,facts,self.activation.configuration(self.home))
        if not control.get('supported'): raise ControlError(control['message'])
        return addon,component,control

    def finish(self, pending, recovered=False, verified=None):
        config,_ = self.activation.configuration(self.home)
        actual = config.get(pending['field'],{}).get(pending['name'],{}).get('enabled')
        confirmed = actual is pending['enabled']
        with self.storage.locked(self.source):
            events = self.journal.read_events(self.source)
            event = next((e for e in events if e.get('data',{}).get('activation_id')==pending['activation_id']),None)
            if not event:
                event = self.journal.record_locked(self.source,
                    'extension_activation_changed' if confirmed else 'extension_activation_unconfirmed',
                    {**pending,'actual_enabled':actual,'verification':verified or 'config_readback',
                     'recovered':recovered,'restart_required':confirmed})
        self.pending.unlink(missing_ok=True)
        return confirmed,event

    def recover(self):
        # Called at startup; never repeat the write after an interrupted response.
        try:
            with self.lock:
                pending = read(self.pending)
                if pending: self.finish(pending,recovered=True)
            if (self.source/self.activation.PENDING).exists():
                with self.storage.locked(self.source):
                    self.activation.recover_locked(self.source,self.home)
        except (OSError,ValueError):
            self.recovery_error = True

    def change(self, snapshot, payload):
        if self.recovery_error: raise ControlError('Незавершённая запись истории требует проверки; переключение временно недоступно.')
        if type(payload.get('enabled')) is not bool or not isinstance(payload.get('revision'),str):
            raise ControlError('Неверные параметры переключателя.')
        if not self.lock.acquire(blocking=False):
            raise Conflict('Уже сохраняется другое переключение. Дождитесь результата.')
        try:
            pending = read(self.pending)
            if pending: self.finish(pending,recovered=True)
            addon,component,control = self.resolve(snapshot,payload)
            if payload['revision']!=control['revision']:
                raise Conflict('Настройки уже изменились в другом окне. Состояние обновлено; повторите действие при необходимости.')
            if payload['enabled'] is control['enabled']:
                return {'saved':True,'unchanged':True,'restart_required':False}
            if component['kind']=='skill':
                try:
                    return self.activation.change(self.source,self.home,str(self.home),component['skill_id'],payload['enabled'],payload['revision'],request_fn=self.request)
                except self.activation.Conflict as error: raise Conflict(str(error)) from None
                except Exception: raise ControlError('Не удалось подтвердить переключение навыка. Состояние перечитано; повторите после проверки.') from None
            # Ask Codex for its own version immediately before the compare-and-swap.
            response = self.rpc('config/read',{'includeLayers':True,'cwd':str(self.home)})
            layer = next((x for x in response.get('layers',[]) if x['name'].get('type')=='user' and not x['name'].get('profile') and Path(x['name']['file']).resolve()==self.home/'.codex/config.toml'),None)
            _,_,again = self.resolve(snapshot,payload)
            if again['revision']!=control['revision'] or not layer or not layer.get('version'):
                raise Conflict('Конфигурация изменилась или её версия не подтверждена. Обновите состояние.')
            pending = {'activation_id':uuid.uuid4().hex,'extension_id':addon['id'],'component_id':component['id'],
                'resource_name':addon['title'],'component_name':component['name'],'field':control['field'],'name':control['name'],
                'before_enabled':control['enabled'],'enabled':payload['enabled'],'scope':'global'}
            self.storage.atomic_json(self.pending,pending)
            verification = 'config_readback'
            try:
                result = self.rpc('config/value/write',{'keyPath':control['key'],'value':payload['enabled'],'mergeStrategy':'upsert',
                    'expectedVersion':layer['version'],'filePath':str(self.home/'.codex/config.toml')})
                effective = self.rpc('config/read',{'includeLayers':False,'cwd':str(self.home)})
                value = effective['config'].get(control['field'],{}).get(control['name'],{}).get('enabled')
                verification = 'codex_config_read' if value is payload['enabled'] and result.get('status')=='ok' else 'overridden'
            except Exception:
                pass  # A lost response can follow a successful write. Read back, never replay.
            confirmed,event = self.finish(pending,verified=verification)
            if not confirmed: raise ControlError('Codex не подтвердил изменение. Прежнее состояние перечитано, попытка записана в историю.')
            return {'saved':True,'restart_required':True,'event_id':event['id'],'verification':verification,
                'warning':'Настройка сохранена, но действующее значение не подтверждено Codex. Проверьте ограничения в его настройках.' if verification!='codex_config_read' else None}
        except (ControlError,Conflict): raise
        except Exception: raise ControlError('Не удалось изменить настройку Codex. Состояние перечитано; подробности конфигурации скрыты.') from None
        finally: self.lock.release()
