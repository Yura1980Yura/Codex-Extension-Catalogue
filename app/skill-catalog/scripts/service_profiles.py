"""Curated resource descriptions, separate from observed connection evidence."""
from copy import deepcopy
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

ORIGINS = {'asemic', 'builtin', 'third_party', 'personal', 'unknown'}
ASSET = Path(__file__).resolve().parents[1]/'assets/service-profiles.json'


def suggestions():
    return {key:deepcopy(value) for key,value in json.loads(ASSET.read_text('utf-8'))['profiles'].items() if value.get('suggest_when_missing')}


def safe_url(value):
    if not value:
        return ''
    if not isinstance(value,str) or len(value)>2048 or any(c.isspace() for c in value):
        raise ValueError('Укажите обычную HTTPS-ссылку без ключей и параметров.')
    try:
        parsed=urlsplit(value)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443):
            raise ValueError()
        if re.search(r'msy_|sk-|token|api[_-]?key|secret|password',value,re.I):
            raise ValueError()
    except ValueError:
        raise ValueError('Укажите обычную HTTPS-ссылку без ключей и параметров.') from None
    return value


def validate(raw, text):
    if not isinstance(raw,dict) or raw.get('origin') not in ORIGINS:
        raise ValueError('Выберите происхождение сервиса.')
    result={k:text(raw.get(k,''),label,maximum,optional=optional) for k,label,maximum,optional in (
        ('title','Название карточки',120,False),('provider','Поставщик',120,True),
        ('description','Описание',2000,True))}
    result.update(origin=raw['origin'],website=safe_url(raw.get('website','')),documentation=safe_url(raw.get('documentation','')))
    capabilities=raw.get('capabilities',[])
    if not isinstance(capabilities,list) or len(capabilities)>12:
        raise ValueError('Укажите до 12 возможностей, по одной в строке.')
    result['capabilities']=[text(x,'Возможность',250) for x in capabilities]
    for field,label in (('connection_steps','Шаг подключения'),('connection_requirements','Требование')):
        if field in raw:
            values=raw[field]
            if not isinstance(values,list) or len(values)>12:
                raise ValueError('Укажите до 12 строк инструкции или требований.')
            result[field]=[text(x,label,600) for x in values]
    if 'connection_documentation' in raw:
        result['connection_documentation']=safe_url(raw['connection_documentation'])
    return result


def describe(card, saved=None):
    profiles=json.loads(ASSET.read_text('utf-8'))['profiles']
    profile=deepcopy(profiles.get(card['id'],{}))
    profile.setdefault('title',card['name'])
    profile.setdefault('origin','unknown')
    profile.setdefault('provider','Не уточнён')
    profile.setdefault('integration_author','Не уточнён')
    profile.setdefault('description',card.get('description') or 'Описание ресурса пока не заполнено.')
    profile.setdefault('capabilities',[])
    profile.setdefault('website','')
    profile.setdefault('documentation','')
    profile.setdefault('evidence','Источник не уточнён. Суффикс магазина сам по себе не определяет поставщика сервиса.')
    profile.setdefault('data_access','Область доступа к данным этим каталогом не проверена.')
    profile.setdefault('pricing','Тариф и возможные расходы этим каталогом не проверены.')
    profile.setdefault('example','')
    profile.setdefault('connection_requirements',['Права на выбранный ресурс и поддерживаемый способ интеграции.'])
    profile.setdefault('connection_steps',['Уточните официальный способ подключения ресурса.','Подготовьте подключение в настройках Codex или через его официальный плагин.','После настройки перечитайте каталог и проверьте доступность инструментов.'])
    profile.setdefault('connection_documentation','https://learn.chatgpt.com/docs/extend/mcp')
    profile.setdefault('connection_method','Способ подключения нужно уточнить')
    profile['customized']=False
    if saved:
        profile.update(deepcopy(saved))
        profile['customized']=True
        profile['evidence']='Описание и происхождение заданы пользователем в каталоге; разрешения подключения не менялись.'
    for field in ('website','documentation','connection_documentation'):
        try:profile[field]=safe_url(profile.get(field,''))
        except ValueError:profile[field]=''
    if profile.get('origin') not in ORIGINS:profile['origin']='unknown'
    return profile
