"""Refresh package documents, source links and initial semantic tags for every addon."""
from pathlib import Path
import re

TAG_RULES=[
 ('исследование',r'research|исслед|product-workshop'),('техническое задание',r'product-workshop|spec|требован|техническое задание'),
 ('инфраструктура проекта',r'bootstrap|развёртывание проекта'),('ведение проекта',r'workflow|new-product-docs|zoo-cafe|agent-first'),
 ('литература',r'novel|reader|character|continuity|editor|dialogue|prose|psychic|scene-architecture|workshop-critique'),
 ('редактура',r'editor|reader|critique'),('персонажи',r'character|psychic'),('диалоги',r'dialogue'),
 ('разработка',r'aria-|code-analysis|code-review|review-agent|\brea\b|reverse-engineer|serena|semgrep|github'),('код-ревью',r'code-review|aria-review|review-agent|code-analysis|semgrep'),
 ('анализ программ',r'reverse-engineer|\brea\b|code-analysis'),('документация',r'docs|documents|documentation|документ|new-product'),
 ('навыки Codex',r'skill|catalog|каталог надстроек'),('настройки',r'plugin-management|safety|подключен'),
 ('браузер',r'browser|chrome|edge|браузер'),('автоматизация',r'computer-use|windows|monitor|automation|schedule'),
 ('3D',r'blender|meshy|3d'),('изображения',r'imagegen|изображен'),('визуализация',r'visualiz|диаграмм|power-bi'),
 ('таблицы',r'spreadsheet|sheets|таблиц|excel|csv'),('презентации',r'presentation|slides|слайд'),('PDF',r'\bpdf\b'),
 ('сайты',r'sites|cloudflare|хостинг'),('облачные файлы',r'drive|google-docs'),('почта',r'gmail'),
 ('коммуникации',r'slack|сообщен'),('база знаний',r'pages|space|organize-space|maintain-space'),
 ('шаблоны',r'template|шаблон'),('финансы',r'financial|budget|investment|forecast'),('правовые документы',r'legal|юридическ'),('дизайн',r'design|дизайн'),('планирование',r'calendar|operating|kickoff|tracker|schedule|календар'),
 ('отчёты',r'report|review|memorandum|analytics'),('безопасность',r'security|safety|defense|semgrep'),
 ('игровые ассеты',r'blender|zoo|midnight|game|pet'),('материалы компании',r'expo-prepare'),('анимация',r'pet|animat')]


def initial_tags(addon,directions):
    text=' '.join([addon['title'],addon['id'],*[s['name'] for s in addon.get('skills',[])] ]).casefold()
    tags=list(addon.get('tags',[]))
    for skill in addon.get('skills',[]):tags.extend(skill.get('package_tags',[]))
    semantic=[name for name,pattern in TAG_RULES if re.search(pattern,text,re.I)]
    tags.extend(semantic[:5])
    if not tags:
        tags.extend(d['title'] for d in directions if d['id'] in addon.get('directions',[]))
    if not tags:tags.append({'skill':'навыки','mcp':'интеграция','plugin':'расширение','app':'сервис','program':'локальная программа'}.get(next((c['kind'] for c in addon['components']),''),'инструменты'))
    return list(dict.fromkeys(tags))[:12]


def initial_directions(addon,directions):
    if addon.get('directions'):return addon['directions']
    tags=set(addon.get('tags',[]));available={d['id'] for d in directions};result=[]
    groups={'literature':{'литература','редактура','диалоги','персонажи'},'development':{'разработка','код-ревью','анализ кода','статический анализ'},
        'reverse':{'анализ программ'},'design':{'изображения','3D','визуализация','дизайн','игровые ассеты'},
        'documents':{'документация','таблицы','презентации','PDF','шаблоны','отчёты','правовые документы'},
        'research':{'исследование','техническое задание','данные'},'organization':{'навыки Codex','настройки','ведение проекта','планирование'},
        'infrastructure':{'сайты','инфраструктура проекта','хостинг'},'communication':{'почта','коммуникации'}}
    for key,values in groups.items():
        if key in available and tags&values:result.append(key)
    return result


def enrich(addons,instructions,package,repositories,directions):
    report={'addons':len(addons),'skills':0,'instructions':0,'documents':0,'issues':[],'repository_links':0}
    for addon in addons:
        for skill in addon.get('skills',[]):
            report['skills']+=1
            instruction=instructions.get(skill['id'])
            skill['instruction_available']=bool(instruction)
            if not instruction:continue
            path=Path(instruction['path']);info=package.load(path,skill['name'])
            # Metadata is re-read from the selected installation, never from another same-name cache.
            for field in ('documentation','documentation_issues','default_prompt','prompts','package_tags'):
                skill.pop(field,None)
                if field in info:skill[field]=info[field]
            docs=package.documents(path,skill.get('documentation',[]));instruction['documents']=docs
            available=set(docs)
            for doc in skill.get('documentation',[]):
                if doc['id'] not in available:skill.setdefault('documentation_issues',[]).append({'id':doc['id'],'reason':'Документ недоступен или превышен общий лимит чтения.'})
            skill['documentation']=[d for d in skill.get('documentation',[]) if d['id'] in available]
            report['instructions']+=1;report['documents']+=len(docs)
            report['issues'].extend({'skill':skill['name'],**issue} for issue in skill.get('documentation_issues',[]))
            profile=skill.setdefault('author_profile',{'name':'','links':[]})
            source=info.get('source') or skill.get('source') or {}
            if not profile.get('name') and source.get('author'):profile['name']=source['author']
            links=profile.setdefault('links',[])
            for key,label in (('url','Источник навыка'),):
                if source.get(key) and not any(row['url']==source[key] for row in links):links.append({'label':label,'url':source[key]})
            for index in repositories.values():
                hit=__import__('skill_repositories').match({**skill,'source':source},path,index)
                if hit:
                    if not any(row['url']==hit['url'] for row in links):links.append({'label':hit['label'],'url':hit['url']})
                    skill['repository_evidence']=hit['evidence'];report['repository_links']+=1
                    if not profile.get('name') and index.get('author'):profile['name']=index['author']
        addon['tags']=initial_tags(addon,directions)
        addon['directions']=initial_directions(addon,directions)
        profile=addon.setdefault('profile',{})
        if not profile.get('provider') or profile['provider']=='Не уточнён':
            authors=list(dict.fromkeys(s.get('author_profile',{}).get('name') for s in addon.get('skills',[]) if s.get('author_profile',{}).get('name')))
            if authors:profile['provider']=', '.join(authors)
        if not addon.get('description'):
            addon['description']=profile.get('description') or next((s.get('helps') or s.get('description_original') for s in addon.get('skills',[]) if s.get('helps') or s.get('description_original')),'Описание не предоставлено поставщиком.')
    return report
