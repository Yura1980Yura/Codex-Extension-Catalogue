'use strict';
const resourceView={data:null,view:'resources',project:'',status:'all',origin:'all',kind:'all',direction:'all',provider:'all',billing:'all',method:'all',tag:'all',scope:'all',relation:'all',technical:false,query:'',selected:null,request:0};
const resourceKinds={external:'Внешний сервис',local:'Локальный инструмент',builtin:'Возможность Codex',unknown:'Тип не уточнён'};
const resourceBilling={free:'Бесплатно',included:'По плану Codex',paid:'Платно',mixed:'Смешанный тариф',unknown:'Стоимость не уточнена'};
const resourceMethods={mcp:'MCP',app:'Приложение',api:'API',cli:'CLI',browser:'Браузер',local:'Локальные файлы'};
const resourceRoles={recommended:'Рекомендован',codex_use:'Используется через Codex',runtime:'Интегрирован в приложение'};
const resourceStates={connected:'Доступно',available:'Можно подключить',needs_check:'Требует внимания',disabled:'Отключено'};
const resourceScopes={user:'Этот компьютер',account:'Аккаунт',project:'Настройка проекта',system:'Система',enterpriseManaged:'Организация',sessionFlags:'Сеанс',packagedDefaults:'Поставка'};

function resourceRows(){
 const data=resourceView.data?.resources||[];
 return resourceView.view==='connections'?data.flatMap(r=>r.connections.map(instance=>({...r,_instance:instance,availability:instance.connection,methods:[instance.kind==='mcp'?'mcp':'app'],scopes:[...new Set((instance.sources||[]).map(s=>s.scope))]}))):data;
}
function resourceMatches(r,f=resourceView,omit=''){
 const eq=(key,value)=>omit===key||f[key]==='all'||f[key]===value;
 const has=(key,values)=>omit===key||f[key]==='all'||values.includes(f[key]);
 const bindings=f.project?r.bindings.filter(b=>b.project_id===f.project):r.bindings;
 const relation=f.relation==='linked'?bindings.length>0:f.relation==='unassigned'?bindings.length===0:bindings.some(b=>b.role===f.relation);
 const words=f.query.toLowerCase().split(/\s+/).filter(Boolean);
 const search=[r.profile.title,r.profile.provider,r.profile.description,...r.tags,...r.skills.map(s=>s.name),...r.bindings.map(b=>b.project_name+' '+b.purpose),r._instance?.server_name,r._instance?.name].join(' ').toLowerCase();
 return (f.technical||!r.technical)&&eq('status',r.availability.state)&&eq('origin',r.profile.origin)&&eq('kind',r.kind)&&eq('provider',r.profile.provider)&&eq('billing',r.billing)&&has('direction',r.direction_ids)&&has('method',r.methods)&&has('tag',r.tags)&&has('scope',r.scopes)&&(omit==='relation'||f.relation==='all'||relation)&&words.every(w=>search.includes(w));
}
function resourceOptions(key){
 const data=resourceView.data;
 const map={status:Object.entries(resourceStates),origin:Object.entries(connectionOrigins),kind:Object.entries(resourceKinds),billing:Object.entries(resourceBilling),method:Object.entries(resourceMethods),scope:Object.entries(resourceScopes),relation:[['linked','Назначенные'],['recommended','Рекомендованные'],['codex_use','Используются через Codex'],['runtime','Интегрированы в код'],['unassigned','Без назначения']]};
 if(key==='direction')return data.directions.map(x=>[x.id,x.title]);
 if(key==='provider'||key==='tag')return [...new Set(data.resources.flatMap(r=>key==='tag'?r.tags:[r.profile.provider]))].sort((a,b)=>a.localeCompare(b,'ru')).map(x=>[x,x]);
 return map[key]||[];
}
function resourceFilter(key,label){return `<label>${label}<select class="filter-select" aria-label="${esc(label)}" data-resource-filter="${key}"></select></label>`;}
function resourceBadge(state){return `<span class="connection-state-label connection-state-${esc(state.state)}">${esc(state.label)}</span>`;}
function resourceCard(r){
 const p=r.profile,instance=r._instance;
 const dirs=r.direction_ids.map(id=>resourceView.data.directions.find(d=>d.id===id)?.title||id);
 return `<article class="connection-card resource-card"><div class="connection-card-top"><span class="connection-kind">${esc(instance?instance.kind==='mcp'?'Подключение MCP':'Подключение приложения':resourceKinds[r.kind])}</span><span class="origin-badge">${esc(connectionOrigins[p.origin]||'Источник не уточнён')}</span></div><h2><button class="card-open" data-open-resource="${esc(r.id)}" aria-label="Открыть ресурс ${esc(p.title)}">${esc(p.title)}</button></h2>${instance?`<p class="technical-name">${esc(instance.server_name||instance.name)}</p>`:''}<p class="connection-provider">Поставщик: ${esc(p.provider)}</p><p>${esc(p.description)}</p>${resourceBadge(r.availability)}<p class="connection-state-reason">${esc(r.availability.reason)}</p><div class="tag-list">${dirs.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}${r.tags.slice(0,4).map(x=>`<span class="resource-tag">${esc(x)}</span>`).join('')}</div><p class="small-note">${esc(resourceBilling[r.billing])} · ${instance?'Статус этого подключения':r.connections.length+' подключений · '+r.skills.length+' связанных навыков'}</p><div class="connection-card-footer"><span>${r.bindings.length?'Назначений проектам: '+r.bindings.length:'Проекты пока не назначены'}</span><div><button class="quiet-button" data-resource-guide="${esc(r.id)}">Как подключить</button><button class="quiet-button" data-open-resource="${esc(r.id)}">Подробнее ${icon('arrow')}</button></div></div></article>`;
}
function paintResources(){
 const rows=resourceRows(),list=rows.filter(r=>resourceMatches(r));
 content.querySelectorAll('[data-resource-filter]').forEach(select=>{
  const key=select.dataset.resourceFilter,chosen=resourceView[key];
  const options=resourceOptions(key).map(([id,label])=>{const count=rows.filter(r=>resourceMatches(r,{...resourceView,[key]:id},key)&&resourceMatches(r,{...resourceView,status:'all',origin:'all',kind:'all',direction:'all',provider:'all',billing:'all',method:'all',tag:'all',scope:'all',relation:'all',[key]:id})).length;return `<option value="${esc(id)}" ${chosen===id?'selected':''}>${esc(label)} · ${count}</option>`;});
  select.innerHTML=`<option value="all" ${chosen==='all'?'selected':''}>Все</option>`+options.join('');
 });
 content.querySelector('#resources-result').textContent=`Показано ${list.length} из ${rows.length} ${resourceView.view==='connections'?'подключений':'ресурсов'}`;
 const summary=content.querySelector('#resources-summary');
 summary.textContent=`В каталоге ${resourceView.data.resources.length} ресурсов, ${resourceView.data.connection_count} подключений и ${resourceView.data.component_count} компонентов. Компоненты расширений показаны внутри ресурсов.${resourceView.technical?'':' Служебные возможности скрыты; их можно показать в дополнительных условиях.'}`;
 content.querySelector('#resources-grid').innerHTML=list.map(resourceCard).join('')||empty('Подходящих ресурсов нет','Измените условия или сбросьте фильтры.');
 content.querySelectorAll('[data-open-resource]').forEach(b=>b.onclick=guarded(()=>openResource(b.dataset.openResource)));
 content.querySelectorAll('[data-resource-guide]').forEach(b=>b.onclick=guarded(()=>openResource(b.dataset.resourceGuide,true)));
 content.querySelectorAll('[data-resource-view]').forEach(b=>{const active=resourceView.view===b.dataset.resourceView;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
}
async function loadResources(){
 resourceView.data=await api('resources'+(resourceView.project?'?project='+encodeURIComponent(resourceView.project):''));return resourceView.data;
}
async function renderConnections(){
 const request=++resourceView.request;
 if(connectionsView.project){resourceView.project=connectionsView.project;connectionsView.project='';}
 content.innerHTML=heading('Ресурсы и подключения','Возможности, реальные подключения и назначения проектам.')+'<p role="status">Читаем каталог…</p>';
 try{
  const data=await loadResources();if(request!==resourceView.request||ui.page!=='connections')return;
  content.innerHTML=heading('Ресурсы и подключения','Выбирайте ресурс по задаче и отдельно проверяйте его подключение.','<button class="primary-button" id="resource-add">'+icon('plus')+'Добавить ресурс</button>')+`<div class="resource-tabs" role="group" aria-label="Представление каталога"><button class="filter-chip" data-resource-view="resources">Ресурсы</button><button class="filter-chip" data-resource-view="connections">Подключения</button><button class="quiet-button" id="resources-refresh">${icon('refresh')}Перечитать</button></div><p id="resources-summary" class="small-note"></p>${data.warning?`<p class="inline-warning">${esc(data.warning)}</p>`:''}<section class="resource-filters" aria-label="Фильтры ресурсов"><label class="resource-search">Поиск<input id="resources-search" class="text-input" type="search" value="${esc(resourceView.query)}" placeholder="Задача, ресурс, поставщик, тег"></label><label>Область проекта<select id="resources-project" aria-label="Область проекта" class="filter-select"><option value="">Codex на этом компьютере</option>${data.projects.map(p=>`<option value="${esc(p.id)}" ${p.id===resourceView.project?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label>${resourceFilter('status','Состояние')}${resourceFilter('direction','Направление')}${resourceFilter('kind','Тип ресурса')}${resourceFilter('origin','Происхождение')}${resourceFilter('provider','Поставщик')}${resourceFilter('billing','Расходы')}${resourceFilter('tag','Тег')}${resourceFilter('relation','Назначение проектам')}<details class="resource-advanced"><summary>Дополнительные условия</summary><div class="resource-filters">${resourceFilter('method','Способ работы')}${resourceFilter('scope','Область подключения')}<label class="resource-checkbox"><input id="resource-technical" type="checkbox" ${resourceView.technical?'checked':''}>Показать служебные возможности</label></div></details></section><div class="connection-caption"><span id="resources-result" role="status"></span><button class="quiet-button" id="resource-reset">Сбросить фильтры</button><span>${esc(data.source)} · ${esc(date(data.checked_at,true))}</span></div><div class="connection-grid" id="resources-grid"></div>`;
  content.querySelectorAll('[data-resource-filter]').forEach(s=>s.onchange=()=>{resourceView[s.dataset.resourceFilter]=s.value;paintResources();});
  content.querySelector('#resources-search').oninput=e=>{resourceView.query=e.target.value;paintResources();};
  content.querySelector('#resources-project').onchange=e=>{resourceView.project=e.target.value;renderConnections();};
  content.querySelector('#resource-technical').onchange=e=>{resourceView.technical=e.target.checked;paintResources();};
  content.querySelector('#resources-refresh').onclick=guarded(renderConnections);
  content.querySelector('#resource-add').onclick=guarded(async()=>{connectionsView.data=await api('connections');openConnectionForm('add');});
  content.querySelector('#resource-reset').onclick=()=>{for(const key of ['status','origin','kind','direction','provider','billing','method','tag','scope','relation'])resourceView[key]='all';resourceView.query='';resourceView.technical=false;renderConnections();};
  content.querySelectorAll('[data-resource-view]').forEach(b=>b.onclick=()=>{resourceView.view=b.dataset.resourceView;paintResources();});
  paintResources();
 }catch(error){if(request===resourceView.request)content.innerHTML=empty('Каталог ресурсов недоступен',error.message);}
}
function resourceSection(title,body){return `<section class="detail-section"><h2>${title}</h2>${body}</section>`;}
function instanceHTML(c){
 const check=c.last_check;
 return `<article class="resource-instance"><h3>${esc(c.server_name||c.name)}</h3>${resourceBadge(c.connection)}<p>${esc(c.connection.reason)}</p><dl class="connection-facts"><div><dt>Способ</dt><dd>${esc(c.transport||'Приложение аккаунта')}</dd></div><div><dt>Подтверждения Codex</dt><dd>${esc(({prompt:'Запрашивать',writes:'Для операций записи',approve:'Без запроса',auto:'Автоматический выбор',default:'По общим настройкам'})[c.approval]||'Определяются приложением')}</dd></div></dl>${check?`<p class="small-note">Последняя проверка: ${esc(date(check.checked_at,true))} · инструментов: ${check.tool_count??'не подтверждено'}${check.fresh?'':' · результат устарел'}</p>`:''}${c.kind==='mcp'&&c.enabled&&!resourceView.project?`<button class="secondary-button" data-resource-probe="${esc(c.id)}">Проверить инструменты</button>`:''}<details class="connection-sources"><summary>Откуда получено подключение</summary>${(c.sources||[]).map(s=>`<p>${esc(connectionScopes[s.scope]||s.scope)}<code>${esc(s.path)}</code></p>`).join('')}</details></article>`;
}
async function openResource(id,guide=false){
 if(!resourceView.data)await loadResources();
 const r=resourceView.data.resources.find(x=>x.id===id);if(!r){toast('Ресурс сейчас не найден.',true);return;}
 resourceView.selected=id;const p=r.profile;
 const guideHTML=connectionGuideHTML({id:r.id,profile:p,connection:r.connections.find(c=>c.connection.state==='connected')?.connection||{state:'available'}});
 document.querySelector('#detail-content').innerHTML=`<div class="detail-head"><span>Ресурс · ${esc(resourceKinds[r.kind])}</span><button id="close-resource" class="icon-button" aria-label="Закрыть карточку">${icon('close')}</button></div><div class="detail-body resource-detail"><h1 id="resource-title">${esc(p.title)}</h1><p class="connection-provider">${esc(p.provider)} · ${esc(connectionOrigins[p.origin]||'Источник не уточнён')}</p>${resourceBadge(r.availability)}<p>${esc(r.availability.reason)}</p><p>${esc(p.description)}</p><div class="detail-actions">${connectionLink(p.website,'Сайт ресурса')}${connectionLink(p.documentation,'Документация')}</div>${resourceSection('Назначение и расходы',`<p>${r.direction_ids.map(x=>esc(resourceView.data.directions.find(d=>d.id===x)?.title||x)).join(' · ')}</p><div class="tag-list">${r.tags.map(x=>`<span class="resource-tag">${esc(x)}</span>`).join('')}</div><p>${esc(resourceBilling[r.billing])}</p><p class="small-note">${esc(p.pricing||'Расходы не уточнены.')}</p><button class="secondary-button" id="edit-resource-profile">Изменить описание и классификацию</button>`)}${resourceSection('Мои подключения · '+r.connections.length,r.connections.map(instanceHTML).join('')||'<p>Подключение аккаунта или MCP не обнаружено. Для локальных возможностей отдельное подключение может не требоваться.</p>')}${r.components.length?`<details class="resource-components"><summary>Компоненты расширений · ${r.components.length}</summary><p class="small-note">Это сведения о поставке возможности. Они не являются отдельными подключёнными аккаунтами.</p>${r.components.map(c=>`<p><code>${esc(c.name)}</code> · ${c.enabled===false?'отключён':'есть в настройках'}</p>`).join('')}</details>`:''}${resourceSection('Возможности',`<ul>${(p.capabilities||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>${esc(p.data_access||'Область данных не уточнена.')}</p>`)}${resourceSection('Связанные навыки',r.skills.length?r.skills.map(s=>`<button class="secondary-button resource-skill" data-resource-skill="${esc(s.id)}">${esc(s.name)}</button>`).join(''):'<p>Связанные навыки пока не назначены.</p>')}${resourceSection('Проекты',`<p class="small-note">Назначение ресурса, доступ Codex и интеграция в код — отдельные сведения.</p>${r.bindings.map(b=>`<article class="connection-project-note"><strong>${esc(b.project_name)}</strong><p>${esc(resourceRoles[b.role])}</p><p>${esc(b.purpose)}</p>${b.evidence?`<p class="small-note">Основание: ${esc(b.evidence)}</p>`:''}<button class="quiet-button" data-resource-bind-edit="${esc(b.project_id)}">Изменить назначение</button><button class="quiet-button" data-resource-unbind="${esc(b.project_id)}">Убрать связь</button></article>`).join('')||'<p>Назначений пока нет.</p>'}<button id="resource-bind" class="secondary-button">Назначить проекту</button>`)}${guideHTML}${r.id==='resource:meshy'?'<div class="detail-actions"><button class="secondary-button" id="resource-meshy-key">Локальная форма API-ключа</button></div>':''}${resourceSection('Ваши заметки',`<p class="connection-notes">${esc(r.notes||'Заметок пока нет.')}</p>`)}<details class="connection-sources"><summary>Происхождение сведений</summary><p>${esc(p.evidence||'Источник не уточнён.')}</p><p>Автор интеграции: ${esc(p.integration_author||'Не уточнён')}.</p><p>${esc(resourceView.data.source)} · ${esc(date(resourceView.data.checked_at,true))}</p><p>Проверки относятся к выбранной области. Операции сервисов и разрешения этой карточкой не изменяются.</p></details></div>`;
 detailDialog.setAttribute('aria-labelledby','resource-title');document.querySelector('#close-resource').onclick=()=>detailDialog.close();
 document.querySelector('#edit-resource-profile').onclick=()=>openResourceProfile(id);
 document.querySelector('#resource-bind').onclick=guarded(()=>openResourceBinding(id,resourceView.project));
 detailDialog.querySelectorAll('[data-resource-skill]').forEach(b=>b.onclick=guarded(()=>openSkill(b.dataset.resourceSkill)));
 detailDialog.querySelectorAll('[data-resource-bind-edit]').forEach(b=>b.onclick=guarded(()=>openResourceBinding(id,b.dataset.resourceBindEdit)));
 detailDialog.querySelectorAll('[data-resource-unbind]').forEach(b=>b.onclick=()=>openResourceUnbind(id,b.dataset.resourceUnbind));
 detailDialog.querySelectorAll('[data-resource-probe]').forEach(b=>b.onclick=guarded(async()=>{b.disabled=true;try{await api('connections/probe',{id:b.dataset.resourceProbe});await loadResources();await openResource(id);if(ui.page==='connections')paintResources();}finally{if(b.isConnected)b.disabled=false;}}));
 const copy=document.querySelector('#copy-connection-doc');if(copy)copy.onclick=guarded(async()=>{await navigator.clipboard.writeText(p.connection_documentation);toast('Ссылка скопирована.');});
 const key=document.querySelector('#resource-meshy-key');if(key)key.onclick=guarded(openMeshyPlan);
 if(!detailDialog.open)detailDialog.showModal();detailDialog.scrollTop=0;if(guide)document.querySelector('#service-connection-guide')?.scrollIntoView({block:'start'});
}
function resourceForm(title,body,submitLabel='Сохранить'){
 formDialog.querySelector('#form-content').innerHTML=`<div class="form-header"><h2>${esc(title)}</h2><button class="icon-button" data-close-form aria-label="Закрыть">${icon('close')}</button></div><p class="small-note">Изменения относятся к каталогу. Подключения и разрешения Codex здесь не переключаются. Не вводите ключи и пароли.</p><p id="direction-error" role="alert" class="inline-warning" hidden></p><form id="resource-form" class="connection-form">${body}<p id="resource-form-status" role="status"></p><div class="form-actions"><button type="button" class="secondary-button" data-close-form>Отмена</button><button class="primary-button" type="submit">${esc(submitLabel)}</button></div></form>`;
 const form=document.querySelector('#resource-form');form.oninput=()=>{form.dataset.directionDirty='true';};form.onchange=form.oninput;
 formDialog.querySelectorAll('[data-close-form]').forEach(b=>b.onclick=requestFormClose);formDialog.classList.remove('reading-document');if(!formDialog.open)formDialog.showModal();return form;
}
async function afterResourceSave(result,id){
 directionBusy(false);formDialog.querySelector('form').dataset.directionDirty='false';formDialog.close();showSaved(result,'Сведения каталога сохранены.');await load();await loadResources();
 if(ui.page==='connections')await renderConnections();else if(ui.page==='projects')await renderProjects();
 if(detailDialog.open&&id)await openResource(id);
}
function bindResourceSubmit(form,build,id){
 const revision=resourceView.data.revision,requestId=crypto.randomUUID();
 form.onsubmit=async event=>{event.preventDefault();const fields=build(form);directionBusy(true);try{const result=await api('resources',{revision,request_id:requestId,...fields});await afterResourceSave(result,fields.id||id);}catch(error){form.querySelector('#resource-form-status').textContent=error.message;}finally{directionBusy(false);}};
}
function openResourceProfile(id){
 const r=resourceView.data.resources.find(x=>x.id===id),p=r.profile;
 const select=(name,label,options,value)=>`<label>${label}<select class="filter-select" name="${name}">${Object.entries(options).map(([k,v])=>`<option value="${esc(k)}" ${k===value?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
 const input=(name,label,value)=>`<label>${label}<input class="text-input" name="${name}" maxlength="2048" value="${esc(value||'')}"></label>`;
 const area=(name,label,value)=>`<label>${label}<textarea class="note-input" name="${name}" maxlength="7212">${esc(Array.isArray(value)?value.join('\n'):value||'')}</textarea></label>`;
 const form=resourceForm('Описание и классификация',input('title','Название',p.title)+input('provider','Поставщик',p.provider)+select('origin','Происхождение',connectionOrigins,p.origin)+select('resource_kind','Тип ресурса',resourceKinds,r.kind)+select('billing','Расходы',resourceBilling,r.billing)+`<fieldset class="resource-choices"><legend>Направления</legend>${resourceView.data.directions.map(d=>`<label><input type="checkbox" name="direction_ids" value="${esc(d.id)}" ${r.direction_ids.includes(d.id)?'checked':''}>${esc(d.title)}</label>`).join('')}</fieldset>`+input('tags','Теги через запятую',r.tags.join(', '))+input('website','Сайт ресурса',p.website)+input('documentation','Документация ресурса',p.documentation)+area('description','Описание',p.description)+area('capabilities','Возможности — по одной строке',p.capabilities)+input('connection_documentation','Документация подключения',p.connection_documentation)+area('connection_requirements','Что потребуется',p.connection_requirements)+area('connection_steps','Шаги подключения',p.connection_steps)+area('notes','Ваши заметки',r.notes));
 bindResourceSubmit(form,f=>{const p=Object.fromEntries(new FormData(f));p.direction_ids=[...f.querySelectorAll('[name="direction_ids"]:checked')].map(x=>x.value);p.tags=p.tags.split(',').map(x=>x.trim()).filter(Boolean);for(const key of ['capabilities','connection_requirements','connection_steps'])p[key]=p[key].split(/\r?\n/).map(x=>x.trim()).filter(Boolean);return {action:'profile',id,profile:p};},id);
}
async function openResourceBinding(id=null,projectId=''){
 if(!resourceView.data)await loadResources();const data=resourceView.data,pid=projectId||data.projects[0]?.id||'';
 const r=data.resources.find(x=>x.id===id),binding=r?.bindings.find(b=>b.project_id===pid);
 const form=resourceForm('Назначить ресурс проекту',`<label>Ресурс<select class="filter-select" name="id" required>${data.resources.map(x=>`<option value="${esc(x.id)}" ${x.id===(id||data.resources[0]?.id)?'selected':''}>${esc(x.profile.title)}</option>`).join('')}</select></label><label>Проект<select class="filter-select" name="project_id" required>${data.projects.map(p=>`<option value="${esc(p.id)}" ${p.id===pid?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><label>Связь<select class="filter-select" aria-label="Связь" name="role">${Object.entries(resourceRoles).map(([k,v])=>`<option value="${k}" ${k===(binding?.role||'recommended')?'selected':''}>${v}</option>`).join('')}</select></label><label>Для какой задачи<textarea class="note-input" name="purpose" maxlength="2000" required>${esc(binding?.purpose||'')}</textarea></label><label>Правило использования<select class="filter-select" name="policy">${Object.entries(connectionPolicies).map(([k,v])=>`<option value="${k}" ${k===(binding?.policy||'explicit')?'selected':''}>${v}</option>`).join('')}</select></label><div id="resource-evidence-fields"><label>Ссылка или путь к результату<input class="text-input" name="evidence" maxlength="2000" value="${esc(binding?.evidence||'')}"></label><label class="resource-checkbox"><input type="checkbox" name="confirmed" ${binding?.confirmed?'checked':''}>Я подтверждаю фактическое использование или интеграцию.</label></div><p class="small-note">Рекомендация описывает план. Для записи использования или интеграции нужны подтверждение и основание. Настройки проекта и сервиса не меняются.</p>`);
 const sync=()=>{form.querySelector('#resource-evidence-fields').hidden=form.elements.role.value==='recommended';};form.elements.role.onchange=()=>{form.dataset.directionDirty='true';sync();};sync();
 bindResourceSubmit(form,f=>({...Object.fromEntries(new FormData(f)),action:'bind',confirmed:f.elements.confirmed.checked}),id);
}
function openResourceUnbind(id,pid){
 const form=resourceForm('Убрать назначение','<p>Убрать эту связь из каталога? Подключение и учётные данные сохраняются.</p>','Убрать связь');
 bindResourceSubmit(form,()=>({action:'unbind',id,project_id:pid}),id);
}
function mountSkillResources(card){
 const known=ui.data.resource_summaries||[],ids=card.resource_ids||[];
 const section=document.createElement('section');section.className='detail-section';
 section.innerHTML=`<h2>Теги и связанные ресурсы</h2><div class="tag-list">${(card.catalog_tags||[]).map(t=>`<span class="resource-tag">${esc(t)}</span>`).join('')||'<p>Теги пока не назначены.</p>'}</div><div class="resource-skill-links">${ids.map(id=>`<button class="secondary-button" data-skill-resource="${esc(id)}">${esc(known.find(x=>x.id===id)?.title||id)}</button>`).join('')}</div><p class="small-note">Связь показывает, какие ресурсы полезны для задач навыка; она не запускает сервис.</p><button class="secondary-button" id="edit-skill-resources">Изменить теги и связи</button>`;
 document.querySelector('.detail-body').append(section);
 section.querySelectorAll('[data-skill-resource]').forEach(b=>b.onclick=guarded(()=>openResource(b.dataset.skillResource)));
 section.querySelector('#edit-skill-resources').onclick=()=>openSkillResourcesForm(card);
}
function openSkillResourcesForm(card){
 const known=ui.data.resource_summaries||[],form=resourceForm('Теги и ресурсы навыка',`<label>Теги через запятую<input class="text-input" name="tags" value="${esc((card.catalog_tags||[]).join(', '))}" maxlength="1600"></label><fieldset class="resource-choices"><legend>Связанные ресурсы</legend>${known.map(r=>`<label><input type="checkbox" name="resource_ids" value="${esc(r.id)}" ${(card.resource_ids||[]).includes(r.id)?'checked':''}>${esc(r.title)}</label>`).join('')}</fieldset>`);
 form.onsubmit=async event=>{event.preventDefault();const tags=form.elements.tags.value.split(',').map(x=>x.trim()).filter(Boolean),resource_ids=[...form.querySelectorAll('[name="resource_ids"]:checked')].map(x=>x.value);directionBusy(true);try{const result=await api('skill-organization',{skill_id:card.id,revision:card.organization_revision,tags,resource_ids});form.dataset.directionDirty='false';directionBusy(false);formDialog.close();await load();resourceView.data=null;await openSkill(card.id);showSaved(result,'Теги и связи навыка сохранены.');}catch(error){form.querySelector('#resource-form-status').textContent=error.message;}finally{directionBusy(false);}};
}
