"""Read declarative skill presentation; metadata never grants installation or access."""
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

MAX_META=64*1024
MAX_DOC=512*1024
TEXT_FIELDS=('title_ru','helps','output','choose_when','prepare','dependencies','portability','instruction_language','origin_evidence','capability_limits')


def scalar(text,key):
    matches=list(re.finditer(r'^  '+re.escape(key)+r':\s*([^\n]*)$',text,re.M))
    if len(matches)!=1:return None
    value=matches[0][1].strip()
    if value.startswith('"'):
        try:value=json.loads(value)
        except ValueError:return None
    elif value.startswith("'") and value.endswith("'"):value=value[1:-1].replace("''", "'")
    elif value in ('>','>-','|','|-'):
        lines=[]
        for line in text[matches[0].end():].splitlines():
            if line and not line.startswith('    '):break
            if line.strip():lines.append(line.strip())
        value=('\n' if value.startswith('|') else ' ').join(lines)
    return value if isinstance(value,str) and 0<len(value)<=8000 else None


def safe_document(root,relative):
    if not isinstance(relative,str) or len(relative)>240 or '\\' in relative or ':' in relative or '\x00' in relative:return None
    value=Path(relative)
    if value.is_absolute() or '..' in value.parts or value.suffix.lower() not in ('.md','.txt'):return None
    path=(root/value).resolve()
    return path if path.is_relative_to(root) and path.is_file() and path.stat().st_size<=MAX_DOC else None


def load(instruction,name):
    root=Path(instruction).resolve().parent;result={};raw={}
    try:
        meta=root/'catalog.json'
        if meta.is_file() and meta.stat().st_size<=MAX_META:
            value=json.loads(meta.read_text('utf-8-sig'))
            if isinstance(value,dict) and value.get('schema')==1 and value.get('name',name)==name:raw=value
        for key in TEXT_FIELDS:
            if isinstance(raw.get(key),str) and 0<len(raw[key])<=8000:result[key]=raw[key]
        if raw.get('origin') in ('third_party','asemic','unknown'):result['origin']=raw['origin']
        if isinstance(raw.get('tasks'),list):result['tasks']=[t for t in raw['tasks'][:30] if isinstance(t,str) and len(t)<=160]
        if isinstance(raw.get('capability_groups'),list):
            result['capability_groups']=[{'title':g['title'],'text':g['text']} for g in raw['capability_groups'][:12] if isinstance(g,dict) and all(isinstance(g.get(k),str) and len(g[k])<=8000 for k in ('title','text'))]
        if isinstance(raw.get('prompts'),list):
            prompts=[]
            for row in raw['prompts'][:24]:
                if not isinstance(row,dict):continue
                if not all(isinstance(row.get(k),str) and row[k].strip() for k in ('title','text')):continue
                if len(row['title'])>160 or len(row['text'])>8000:continue
                prompt={'title':row['title'].strip(),'text':row['text'].strip()}
                if not any(p['text']==prompt['text'] for p in prompts):prompts.append(prompt)
            if prompts:result['prompts']=prompts
        if isinstance(raw.get('version'),str) and len(raw['version'])<=80:result['declared_version']=raw['version']
        source=raw.get('source',{});source=source if isinstance(source,dict) else {};clean={}
        if isinstance(source.get('author'),str) and len(source['author'])<=160:clean['author']=source['author']
        if isinstance(source.get('repository'),str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',source['repository']):clean['repository']=source['repository']
        if isinstance(source.get('url'),str):
            url=urlsplit(source['url'])
            if url.scheme=='https' and url.hostname and not (url.username or url.password or url.query):clean['url']=source['url']
        if clean:result['source']=clean
        ui=root/'agents/openai.yaml'
        if ui.is_file() and ui.stat().st_size<=MAX_META:
            text=ui.read_text('utf-8-sig')
            title=scalar(text,'display_name');prompt=scalar(text,'default_prompt')
            if title and 'title_ru' not in result:result['title_ru']=title
            if prompt and '$'+name in prompt:result['default_prompt']=prompt
        docs=raw.get('documentation',[])
        docs=docs if isinstance(docs,list) else []
        if not docs and (root/'README.md').is_file():docs=[{'id':'README.md','title':'README — о навыке'}]
        entries=[]
        for row in docs[:8]:
            if not isinstance(row,dict):continue
            path=safe_document(root,row.get('id'));title=row.get('title')
            if path and isinstance(title,str) and 0<len(title)<=160:
                entries.append({'id':row['id'],'title':title,'path':str(path)})
        if entries:result['documentation']=entries
    except (OSError,ValueError,TypeError):
        # Invalid optional metadata must not hide a valid instruction.
        return result
    return result


def documents(instruction,entries):
    root=Path(instruction).resolve().parent;result={};total=0
    for row in entries[:8]:
        path=safe_document(root,row.get('id'))
        if path:
            raw=path.read_bytes();total+=len(raw)
            if total>2*1024*1024:break
            try:result[row['id']]={'text':raw.decode('utf-8-sig'),'title':row['title'],'path':str(path)}
            except UnicodeError:continue
    return result
