"""Optional read-only indexes of user-configured repositories, outside public bundles."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess


def indexes(settings,work):
    cache=Path(work)/'skill-repositories.json'
    try:previous=json.loads(cache.read_text('utf-8'))
    except (OSError,ValueError):previous={}
    result={};executable=shutil.which('gh')
    for entry in settings.get('skill_repositories',[])[:10]:
        if not isinstance(entry,dict):continue
        repository=entry.get('repository','');branch=entry.get('branch','HEAD')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository) or not re.fullmatch(r'[A-Za-z0-9_./-]+',branch):continue
        item={**previous.get(repository,{}),'repository':repository,'author':entry.get('author',''),'status':'unavailable'}
        try:
            if not executable:raise ValueError('Для проверки репозитория нужен GitHub CLI с доступом к нему.')
            process=subprocess.run([executable,'api',f'repos/{repository}/git/trees/{branch}','--method','GET','-f','recursive=1'],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if process.returncode:raise ValueError('GitHub не подтвердил доступ к репозиторию; сохранён предыдущий индекс.')
            tree=json.loads(process.stdout)
            if tree.get('truncated'):raise ValueError('GitHub вернул неполный индекс; сохранены предыдущие сведения.')
            skills={}
            for row in tree['tree']:
                path=row.get('path','')
                if row.get('type')=='blob' and path.endswith('/SKILL.md') and not any(x in path for x in ('..','\\',':')):
                    name=Path(path).parent.name
                    skills.setdefault(name,[]).append({'path':str(Path(path).parent).replace('\\','/'),'sha':row['sha']})
            item.update(skills=skills,revision=tree['sha'],checked_at=datetime.now(timezone.utc).isoformat(),status='verified')
            item.pop('warning',None)
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
            item.update(status='cached' if item.get('skills') else 'unavailable',warning=str(error) if isinstance(error,ValueError) else 'Не удалось обновить индекс репозитория.')
        result[repository]=item
    cache.parent.mkdir(parents=True,exist_ok=True)
    temporary=cache.with_suffix('.tmp');temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(cache)
    return result


def match(skill,instruction,index):
    raw=Path(instruction).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    owned=skill.get('origin') in ('asemic','personal') or (skill.get('source') or {}).get('repository')==index['repository']
    matches=[row for row in index.get('skills',{}).get(skill['name'],[]) if owned or row['sha']==blob]
    if len(matches)!=1:return None
    row=matches[0]
    return {'label':'Навык в репозитории','url':f"https://github.com/{index['repository']}/tree/{index['revision']}/{row['path']}",
        'evidence':('Проверено в GitHub' if index['status']=='verified' else 'По сохранённому индексу GitHub')+' · '+index['checked_at'][:10]+('. Инструкция совпадает.' if row['sha']==blob else '. Установленная инструкция отличается от версии в репозитории.')}
