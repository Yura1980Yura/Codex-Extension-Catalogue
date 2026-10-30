"""Change one TOML boolean, preserving every other parsed value and local text."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib


def read_config(path):
    raw=Path(path).read_bytes() if Path(path).exists() else b''
    return tomllib.loads(raw.decode('utf-8-sig')),hashlib.sha256(raw).hexdigest()


def boolean_edit(raw,field,name,enabled):
    text=raw.decode('utf-8-sig');before=tomllib.loads(text)
    expected=deepcopy(before);expected.setdefault(field,{}).setdefault(name,{})['enabled']=enabled
    signature=lambda data:json.dumps(data,sort_keys=True,ensure_ascii=False,default=str)
    target=signature(expected);value='true' if enabled else 'false'
    def valid(candidate):
        try:return signature(tomllib.loads(candidate))==target
        except tomllib.TOMLDecodeError:return False
    # Full semantic comparison rejects apparent keys and table headers inside strings.
    for match in re.finditer(r'''(?<![\w-])(?:enabled|"enabled"|'enabled')\s*=\s*(true|false)\b''',text):
        start,end=match.span(1);candidate=text[:start]+value+text[end:]
        if valid(candidate):return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+candidate.encode('utf-8')
    newline='\r\n' if '\r\n' in text else '\n'
    for match in re.finditer(r'^\s*\[(?!\[)[^\r\n]+\][ \t]*(?:#[^\r\n]*)?$',text,re.M):
        candidate=text[:match.end()]+newline+'enabled = '+value+text[match.end():]
        if valid(candidate):return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+candidate.encode('utf-8')
    for match in re.finditer('}',text):
        for prefix in (', enabled = ','enabled = '):
            candidate=text[:match.start()]+prefix+value+text[match.start():]
            if valid(candidate):return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+candidate.encode('utf-8')
    candidate=field+'.'+json.dumps(name,ensure_ascii=False)+'.enabled = '+value+newline+text
    if valid(candidate):return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+candidate.encode('utf-8')
    candidate=text+newline+'['+field+'.'+json.dumps(name,ensure_ascii=False)+']'+newline+'enabled = '+value+newline
    if valid(candidate):return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+candidate.encode('utf-8')
    raise ValueError('Не удалось выделить единственную настройку, сохранив остальные значения. Файл не изменён.')


def write_boolean(path,field,name,enabled,fingerprint,backup):
    path=Path(path);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=fingerprint:raise ValueError('Настройки проекта уже изменились. Обновите состояние.')
    updated=boolean_edit(raw,field,name,enabled)
    backup=Path(backup);backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(raw)
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.catalogue-control-',suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(updated);stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary,path.stat().st_mode)
        if path.read_bytes()!=raw:raise ValueError('Настройки проекта изменились во время записи. Повторите после сверки.')
        os.replace(temporary,path)
        if path.read_bytes()!=updated:raise OSError('Не удалось подтвердить записанные байты.')
    finally:Path(temporary).unlink(missing_ok=True)
