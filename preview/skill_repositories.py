"""Optional read-only indexes of user-configured repositories, outside public bundles."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
import re
import shutil
import subprocess

REPOSITORY=re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
REVISION=re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})')


def write_cache(path,result):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def indexes(settings,work):
    cache=Path(work)/'skill-repositories.json'
    try:previous=json.loads(cache.read_text('utf-8'))
    except (OSError,ValueError):previous={}
    if not isinstance(previous,dict):previous={}
    previous={key:value for key,value in previous.items() if isinstance(value,dict) and REPOSITORY.fullmatch(key)}
    entries=settings.get('skill_repositories',[]) if isinstance(settings,dict) else None
    if not isinstance(entries,list):
        warning='Настройки репозиториев должны быть списком. Остальные данные каталога сверены независимо.'
        result={key:{**value,'repository':key,'status':'cached','warning':warning} for key,value in previous.items()}
        if not result:result={'_configuration':{'repository':None,'status':'unavailable','warning':warning}}
        write_cache(cache,result)
        return result
    result={};executable=shutil.which('gh')
    for position,entry in enumerate(entries[:10]):
        repository=entry.get('repository') if isinstance(entry,dict) else None
        branch=entry.get('branch','HEAD') if isinstance(entry,dict) else None
        if not isinstance(repository,str) or not REPOSITORY.fullmatch(repository) or not isinstance(branch,str) or not re.fullmatch(r'[A-Za-z0-9_./-]+',branch) or {'.','..'}.intersection(branch.split('/')):
            result[f'_configuration_{position}']={'repository':None,'status':'unavailable','warning':'Некорректная запись репозитория пропущена; остальные источники проверяются.'}
            continue
        author=entry.get('author','')
        if not isinstance(author,str) or len(author)>160:author=''
        item={**previous.get(repository,{}),'repository':repository,'author':author,'status':'unavailable'}
        try:
            if not executable:raise ValueError('Для проверки репозитория нужен GitHub CLI с доступом к нему.')
            process=subprocess.run([executable,'api',f'repos/{repository}/git/trees/{quote(branch,safe="")}','--method','GET','-f','recursive=1'],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if process.returncode:raise ValueError('GitHub не подтвердил доступ к репозиторию; сохранён предыдущий индекс.')
            tree=json.loads(process.stdout)
            if not isinstance(tree,dict) or not isinstance(tree.get('tree'),list) or not isinstance(tree.get('sha'),str) or not REVISION.fullmatch(tree['sha']):
                raise ValueError('GitHub вернул некорректный индекс; сохранены предыдущие сведения.')
            if tree.get('truncated'):raise ValueError('GitHub вернул неполный индекс; сохранены предыдущие сведения.')
            skills={}
            for row in tree['tree']:
                if not isinstance(row,dict):continue
                path=row.get('path');sha=row.get('sha')
                if row.get('type')=='blob' and isinstance(path,str) and path.endswith('/SKILL.md') and not any(x in path for x in ('..','\\',':')) and isinstance(sha,str) and REVISION.fullmatch(sha):
                    name=Path(path).parent.name
                    skills.setdefault(name,[]).append({'path':str(Path(path).parent).replace('\\','/'),'sha':sha})
            item.update(skills=skills,revision=tree['sha'],checked_at=datetime.now(timezone.utc).isoformat(),status='verified')
            item.pop('warning',None)
        except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
            item.update(status='cached' if isinstance(item.get('skills'),dict) and item['skills'] else 'unavailable',warning=str(error) if isinstance(error,ValueError) else 'Не удалось обновить индекс репозитория.')
        result[repository]=item
    write_cache(cache,result)
    return result


def match(skill,instruction,index):
    repository=index.get('repository');revision=index.get('revision');checked=index.get('checked_at');skills=index.get('skills')
    if not isinstance(repository,str) or not REPOSITORY.fullmatch(repository) or not isinstance(revision,str) or not REVISION.fullmatch(revision) or not isinstance(checked,str) or not isinstance(skills,dict):return None
    rows=skills.get(skill['name'],[])
    if not isinstance(rows,list):return None
    try:raw=Path(instruction).read_bytes()
    except OSError:return None
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    source=skill.get('source')
    declared=isinstance(source,dict) and source.get('repository')==repository
    matches=[row for row in rows if isinstance(row,dict) and isinstance(row.get('path'),str) and row['path'] and not row['path'].startswith('/') and not any(part in row['path'] for part in ('..','\\',':')) and (declared or row.get('sha')==blob)]
    if len(matches)!=1:return None
    row=matches[0]
    return {'label':'Навык в репозитории','url':f"https://github.com/{repository}/tree/{revision}/{quote(row['path'],safe='/')}",
        'evidence':('Проверено в GitHub' if index.get('status')=='verified' else 'По сохранённому индексу GitHub')+' · '+checked[:10]+('. Инструкция совпадает.' if row.get('sha')==blob else '. Установленная инструкция отличается от версии в репозитории.')}
