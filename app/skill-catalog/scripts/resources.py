"""Logical resources, observed connection instances and catalogue-only project links."""
from copy import deepcopy
from pathlib import Path
import hashlib
import re

import catalog
import connections
import directions as transactions
import journal
import organization
import service_profiles
from storage import locked, now, read_json

ASSET=Path(__file__).resolve().parents[1]/'assets/resources.json'
KEY='resource_catalog'
KINDS={'external','local','builtin','unknown'}
BILLING={'free','included','paid','mixed','unknown'}
ROLES={'recommended','codex_use','runtime'}

def descriptors():return read_json(ASSET,{'resources':[]})['resources']

def resource_for_connection(identifier):
    return next((x['id'] for x in descriptors() if identifier in x['aliases']),None)

def registry(user):
    value=user.get(KEY,{'schema':1,'profiles':{},'bindings':{}})
    if not isinstance(value,dict) or value.get('schema')!=1 or any(not isinstance(value.get(k),dict) for k in ('profiles','bindings')):raise ValueError('Повреждены сведения ресурсов; прежние данные сохранены.')
    for bindings in value['bindings'].values():
        if not isinstance(bindings,dict) or any(not isinstance(x,dict) or x.get('role','recommended') not in ROLES for x in bindings.values()):raise ValueError('Повреждены назначения ресурсов.')
    return deepcopy(value)

def summaries(user=None):
    saved=registry(user or {})['profiles'];profiles=read_json(service_profiles.ASSET)['profiles'];result=[]
    for item in descriptors():
        p={**profiles.get(item['profile_id'],{}),**saved.get(item['id'],{})}
        result.append({'id':item['id'],'title':p.get('title',item['id']),'kind':p.get('resource_kind',item['kind']),'origin':p.get('origin','unknown')})
    return result

def project_bindings(user,pid):
    names={x['id']:x['title'] for x in summaries(user)}
    bindings=registry(user)['bindings'].get(pid,{})
    return [{'id':rid,'name':names.get(rid,rid),**deepcopy(value)} for rid,value in bindings.items()]

def _public_connection(card):
    fields=('id','name','kind','enabled','transport','approval','sources','connection','last_check','tool_limit','server_name')
    return {k:deepcopy(card[k]) for k in fields if k in card}

def _availability(item,instances,components,skills):
    states=[x['connection'] for x in instances]
    connected=next((x for x in states if x['state']=='connected'),None)
    if connected:return deepcopy(connected)
    if not item.get('requires_connection'):
        usable=[x for x in skills if x.get('state')=='present' and x.get('activation',{}).get('enabled') is not False]
        disabled=components and all(x.get('enabled') is False for x in components)
        if usable and not disabled:
            return {'state':'connected','label':'Доступен навык','reason':'Найдена действующая установка связанного навыка. Готовность конкретной операции проверяется при использовании.','basis':'Обнаружение навыков Codex','checked_at':None}
    if states:
        if all(x['state']=='disabled' for x in states):return deepcopy(states[0])
        return deepcopy(next((x for x in states if x['state']=='needs_check'),states[0]))
    if components:
        if all(x.get('enabled') is False for x in components):return {'state':'disabled','label':'Отключено','reason':'Компоненты отключены в настройках Codex.','basis':'Настройки Codex','checked_at':None}
        return {'state':'needs_check','label':'Требует проверки','reason':'Есть компонент в настройках; доступность возможности не подтверждена.','basis':'Запись компонента','checked_at':None}
    return {'state':'available','label':'Можно подключить','reason':'Есть описание способа работы; действующее подключение или готовность программы не подтверждены.','basis':'Справочник ресурсов','checked_at':None}

def view(directory,home,project=None,request_fn=None):
    args={} if request_fn is None else {'request_fn':request_fn}
    observed=connections.view(directory,home,project,**args)
    with locked(directory):
        transactions.recover_locked(directory)
        user=read_json(Path(directory)/'user.json',{'schema':1,'skills':{}})
        inventory,all_skills=catalog.load_cards(Path(directory),str(home))
        saved=registry(user);directions=transactions.state(user,inventory)['items']
    cards=observed['services'];defs=deepcopy(descriptors());covered={cid for d in defs for cid in d['aliases']}
    for card in cards:
        if card['id'] in covered:continue
        defs.append({'id':'resource:connection-'+hashlib.sha256(card['id'].encode()).hexdigest()[:16],'profile_id':card['id'],'aliases':[card['id']],'kind':'unknown','direction_ids':[],'tags':[],'methods':[],'billing':'unknown','skill_names':[],'technical':False,'requires_connection':True})
    visible_skills=[s for s in all_skills if s.get('state')!='cache_only' or s.get('has_user_annotations')]
    resources=[]
    for item in defs:
        matches=[c for c in cards if c['id'] in item['aliases']]
        profile=deepcopy(next((c['profile'] for c in matches if c['id']==item['profile_id']),None) or service_profiles.describe({'id':item['profile_id'],'name':item['id']}))
        profile.update(deepcopy(saved['profiles'].get(item['id'],{})))
        if item['id'] in saved['profiles']:
            profile.update(customized=True,evidence='Описание и классификация изменены пользователем в каталоге; разрешения подключения не менялись.')
        linked=[s for s in visible_skills if item['id'] in organization.skill_metadata(s,user)['resource_ids']]
        if not matches and not linked and not profile.get('suggest_when_missing'):continue
        instances=[_public_connection(c) for c in matches if c['configured'] and c['kind'] in ('app','mcp')]
        components=[_public_connection(c) for c in matches if c['configured'] and c['kind']=='plugin']
        bindings=[]
        for pid,entries in saved['bindings'].items():
            if item['id'] in entries:bindings.append({'project_id':pid,'project_name':next((p['name'] for p in observed['projects'] if p['id']==pid),pid),**deepcopy(entries[item['id']])})
        scopes=sorted({s['scope'] for c in matches for s in c.get('sources',[])})
        availability=_availability(item,instances,components,linked)
        resources.append({'id':item['id'],'profile':profile,'kind':profile.get('resource_kind',item['kind']),'billing':profile.get('billing',item['billing']),'direction_ids':profile.get('direction_ids',item['direction_ids']),'tags':profile.get('tags',item['tags']),'methods':profile.get('methods',item['methods']),'technical':item.get('technical',False),'connections':instances,'components':components,'availability':availability,'scopes':scopes,'bindings':bindings,'project_binding':next((b for b in bindings if b['project_id']==project),None),'skills':[{'id':s['id'],'name':s.get('title_ru') or s['name']} for s in linked],'notes':profile.get('notes',''),'configured':bool(instances),'connection_ids':[c['id'] for c in matches]})
    return {'revision':transactions.checksum(saved),'resources':sorted(resources,key=lambda x:x['profile']['title'].casefold()),'projects':observed['projects'],'directions':directions,'project_id':project,'checked_at':observed['checked_at'],'source':observed['source'],'warning':observed['warning'],'connection_count':sum(len(x['connections']) for x in resources),'component_count':sum(len(x['components']) for x in resources)}

def change(directory,home,request,request_fn=None):
    action=request.get('action');rid=request.get('id');request_id=request.get('request_id','')
    if action not in ('profile','bind','unbind'):raise ValueError('Неизвестное действие ресурса.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',request_id):raise ValueError('Неверный идентификатор запроса.')
    current=view(directory,home,request_fn=request_fn);card=next((x for x in current['resources'] if x['id']==rid),None)
    if card is None:raise ValueError('Ресурс не найден.')
    fingerprint=transactions.checksum({k:v for k,v in request.items() if k!='revision'})
    with locked(directory):
        transactions.recover_locked(directory);user=read_json(Path(directory)/'user.json',{'schema':1,'skills':{}});saved=registry(user)
        previous=next((e for e in journal.read_events(directory) if e['data'].get('resource_request_id')==request_id),None)
        if previous:
            if previous['data'].get('resource_request_sha256')!=fingerprint:raise transactions.Conflict('Запрос уже сохранён с другим содержимым.')
            return {'saved':True,'replayed':True}
        if request.get('revision')!=transactions.checksum(saved):raise transactions.Conflict('Сведения ресурсов изменились. Перечитайте каталог.')
        payload={'resource_id':rid,'resource_name':card['profile']['title'],'action':action,'resource_request_id':request_id,'resource_request_sha256':fingerprint}
        if action=='profile':
            raw=request.get('profile',{});profile=service_profiles.validate(raw,connections.text)
            kind=raw.get('resource_kind',card['kind']);billing=raw.get('billing',card['billing'])
            if kind not in KINDS or billing not in BILLING:raise ValueError('Выберите тип ресурса и стоимость.')
            ids=organization.strings(raw.get('direction_ids',[]),'Направления',12,100);allowed={x['id'] for x in current['directions']}
            if any(x not in allowed for x in ids):raise ValueError('Неизвестное направление.')
            tags=organization.strings(raw.get('tags',[]),'Теги')
            profile.update(resource_kind=kind,billing=billing,direction_ids=ids,tags=tags,notes=connections.text(raw.get('notes',''),'Заметка',2000,optional=True))
            saved['profiles'][rid]={**saved['profiles'].get(rid,{}),**profile};payload['profile']=profile
        else:
            pid=request.get('project_id');project=next((p for p in current['projects'] if p['id']==pid),None)
            if project is None:raise ValueError('Выберите существующий проект.')
            links=saved['bindings'].setdefault(pid,{})
            if action=='unbind':links.pop(rid,None)
            else:
                role=request.get('role','recommended');policy=request.get('policy','explicit')
                if role not in ROLES or policy not in connections.POLICIES:raise ValueError('Выберите назначение и правило.')
                evidence=connections.text(request.get('evidence',''),'Основание',2000,optional=True)
                if role!='recommended' and (request.get('confirmed') is not True or not evidence):raise ValueError('Для фактического использования нужны подтверждение и ссылка или путь к результату.')
                links[rid]={'purpose':connections.text(request.get('purpose'),'Назначение',2000),'role':role,'policy':policy,'evidence':evidence,'confirmed':request.get('confirmed') is True if role!='recommended' else False,'updated_at':now()}
            payload.update(project_id=pid,project_name=project['name'])
        updated=deepcopy(user);updated[KEY]=saved
        transactions.commit_locked(directory,user,updated,'resource_catalog_changed',payload)
    return {'saved':True,'resource_id':rid}
