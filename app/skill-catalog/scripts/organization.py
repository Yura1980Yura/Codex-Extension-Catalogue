"""Catalogue-only classification and recoverable migration. No Codex settings writes."""
from copy import deepcopy
from pathlib import Path
import re
import uuid

import directions as transactions
import journal
from storage import locked, now, read_json

ASSET=Path(__file__).resolve().parents[1]/'assets/organization.json'

def rules():
    return read_json(ASSET, {'schema':1,'skills':{},'origins':{},'directions':[]})

def strings(values, label, maximum=20, length=80):
    if not isinstance(values,list) or len(values)>maximum or any(not isinstance(x,str) or not x.strip() or len(x)>length or any(ord(c)<32 for c in x) for x in values):
        raise ValueError('Проверьте поле «'+label+'».')
    if any(re.search(r'msy(?:sk|_[A-Za-z0-9])|Bearer\s|sk-[A-Za-z0-9]{12}',x,re.I) for x in values):
        raise ValueError('Не сохраняйте ключи и пароли в классификации каталога.')
    return list(dict.fromkeys(x.strip() for x in values))

def skill_metadata(card,user):
    default=rules()['skills'].get(card['name'].casefold(),{})
    saved=user.get('skills',{}).get(card['id'],{})
    value={'tags':saved.get('catalog_tags',default.get('tags',[])), 'resource_ids':saved.get('resource_ids',default.get('resource_ids',[]))}
    return {**value,'revision':transactions.checksum({'id':card['id'],**value})}

def change_skill(directory,request):
    key=request.get('skill_id');tags=strings(request.get('tags',[]),'Теги');ids=strings(request.get('resource_ids',[]),'Ресурсы',40,160)
    from resources import descriptors
    allowed={x['id'] for x in descriptors()}
    if any(x not in allowed for x in ids):raise ValueError('Выберите ресурсы из каталога.')
    with locked(directory):
        transactions.recover_locked(directory)
        user=read_json(Path(directory)/'user.json',{'schema':1,'skills':{}});inventory=read_json(Path(directory)/'inventory.json')
        if key not in inventory['skills']:raise ValueError('Навык не найден.')
        card={**inventory['skills'][key],'id':key};before=skill_metadata(card,user)
        if before['revision']!=request.get('revision'):raise transactions.Conflict('Связи навыка изменились. Откройте форму заново.')
        updated=deepcopy(user);overlay=updated.setdefault('skills',{}).setdefault(key,{})
        overlay.update(catalog_tags=tags,resource_ids=ids)
        transactions.commit_locked(directory,user,updated,'skill_organization_changed',{'skill_id':key,'skill_name':card['name'],'tags':tags,'resource_ids':ids})
    return {'saved':True}

def migrate(directory):
    """Fill missing classification; preserve explicit choices, notes and unknown fields."""
    from resources import registry, descriptors, resource_for_connection
    directory=Path(directory)
    with locked(directory):
        transactions.recover_locked(directory)
        user=read_json(directory/'user.json',{'schema':1,'skills':{}});inventory=read_json(directory/'inventory.json')
        updated=deepcopy(user);spec=rules();view=transactions.state(updated,inventory)
        directions={k:deepcopy(view[k]) for k in ('schema','items','assignments')}
        known={x['id'] for x in directions['items']}
        for item in spec['directions']:
            if item['id'] not in known:directions['items'].append(item);known.add(item['id'])
        classified=[];origins=[]
        for key,card in inventory['skills'].items():
            if card.get('state')!='present':continue
            name=card['name'].casefold();default=spec['skills'].get(name,{})
            overlay=updated.setdefault('skills',{}).setdefault(key,{})
            if not directions['assignments'].get(key) and key not in user.get('directions',{}).get('assignments',{}):
                chosen=default.get('direction_ids') or transactions.initial_ids(card) or ['organization']
                directions['assignments'][key]=[x for x in chosen if x in known];classified.append(key)
            if 'catalog_tags' not in overlay:overlay['catalog_tags']=default.get('tags',[])
            if 'resource_ids' not in overlay:overlay['resource_ids']=default.get('resource_ids',[])
            detected=overlay.get('origin') or card.get('origin','unknown')
            if detected=='unknown' and 'origin' not in overlay and name in spec['origins']:
                entry=spec['origins'][name]
                overlay.update(origin=entry['origin'],origin_evidence=entry['evidence'])
                if 'author_profile' not in overlay and entry.get('author'):
                    overlay.update(author_profile=entry['author'],author_evidence=entry['evidence'])
                origins.append(key)
        updated['directions']=directions
        data=registry(updated);legacy=updated.get('service_catalog',{});migrated=0
        for pid,bindings in legacy.get('bindings',{}).items():
            for cid,binding in bindings.items():
                rid=resource_for_connection(cid)
                if rid and rid not in data['bindings'].setdefault(pid,{}):
                    data['bindings'][pid][rid]={**binding,'role':'recommended','evidence':'','confirmed':False};migrated+=1
        seeded=[]
        from connections import project_id
        projects={project_id(path):{'name':Path(path).name,'path':path} for path in inventory.get('projects',[]) if isinstance(path,str) and Path(path).is_absolute()}
        projects.update(updated.get('project_catalog',{}).get('projects',{}))
        for pid,project in projects.items():
            links=data['bindings'].setdefault(pid,{})
            selected={}
            for recommendation in project.get('recommendations',[]):
                skill=inventory['skills'].get(recommendation['skill_id'],{})
                for rid in spec['skills'].get(skill.get('name','').casefold(),{}).get('resource_ids',[]):
                    selected[rid]='Рекомендован для задач, связанных с навыком «'+skill.get('name','')+'»; применение ещё не подтверждено.'
            name=project.get('name','').casefold()
            if name=='rea':selected.update({'resource:rea':'Разбор готовых программ по отдельному поручению.','resource:catalog':'Организация навыков и ресурсов этого рабочего пространства.','resource:github':'Хранение и проверка изменений исходного кода.'})
            if 'zoo' in name:selected.update({'resource:blender':'Подготовка и проверка 3D-ассетов игры.','resource:imagegen':'Подготовка графических материалов по отдельному поручению.','resource:github':'Хранение изменений игры и проверка результатов.','resource:meshy':'Возможный способ подготовки 3D; платные операции только по отдельной команде.'})
            for rid,purpose in selected.items():
                if rid not in links:
                    links[rid]={'purpose':purpose,'role':'recommended','policy':'explicit','evidence':'','confirmed':False,'updated_at':now()};seeded.append({'project_id':pid,'resource_id':rid})
        updated['resource_catalog']=data
        if updated==user:return {'saved':True,'unchanged':True,'classified':0,'origins':0,'project_links':0}
        transactions.commit_locked(directory,user,updated,'catalog_organization_migrated',{'version':2,'classified_skill_ids':classified,'origin_skill_ids':origins,'project_links':seeded,'legacy_links_migrated':migrated})
    return {'saved':True,'classified':len(classified),'origins':len(origins),'project_links':len(seeded),'legacy_links_migrated':migrated}
