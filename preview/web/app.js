import {markdown} from './markdown.js';
import {showDialog as openNativeDialog,closeDialog as closeNativeDialog,clearDialogMotion} from './dialog.js';
import {typeNames,scopeNames,origins,componentsFor,presence,status,visible,values,reorderIds} from './model.js';
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths={all:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',skill:'M5 4h14v16H5zM8 8h8M8 12h8M8 16h5',mcp:'M8 8v8m8-8v8M8 12h8M4 5h4v3H4zM16 5h4v3h-4zM4 16h4v3H4zM16 16h4v3h-4z',plugin:'M4 4h6v4a3 3 0 0 0 6 0V4h4v16h-4v-4a3 3 0 0 0-6 0v4H4z',app:'M4 4h16v16H4zM4 9h16M8 4v5',program:'M3 4h18v13H3zM8 21h8m-4-4v4',star:'m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z',notes:'M5 3h14v18H5zM8 7h8M8 11h8M8 15h5',history:'M4 5v5h5M4 10a8 8 0 1 1 .3 5M12 7v5l3 2',globe:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18',folder:'M3 6h7l2 2h9v12H3z',refresh:'M20 7v5h-5M4 17v-5h5M20 12a8 8 0 0 0-14-5M4 12a8 8 0 0 0 14 5',info:'M12 11v6m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',filter:'M4 6h16M7 12h10M10 18h4',close:'m6 6 12 12M18 6 6 18',chevron:'m9 5 7 7-7 7',copy:'M9 9h11v11H9zM5 15H3V3h12v2'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]||paths.skill}"/></svg>`;
const plural=(n,one,few,many)=>`${n} ${n%10===1&&n%100!==11?one:n%10>=2&&n%10<=4&&(n%100<12||n%100>14)?few:many}`;
const date=(s,time=false)=>{if(!s)return 'Дата не указана';const d=new Date(s);return Number.isNaN(+d)?s:d.toLocaleString('ru-RU',time?{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}:{day:'numeric',month:'long',year:'numeric'});};
const bills={free:'Бесплатно',included:'Включено в подписку',paid:'Платные операции',mixed:'Есть платные возможности',unknown:'Расходы не уточнены'};
let data, selected=null, detailTab='overview', page='all', poll, toastTimer, sortMode=localStorage.getItem('catalog-sort')||'custom';
let filters={project:'',types:[],scope:'',enabled:'',presence:'installed',direction:'',origin:'',tag:'',billing:'',query:'',favorite:false};
let pendingRender=false,lastInput='pointer',dragged=null,orderSaving=false;
let switching=false,stateEpoch=0;
document.addEventListener('keydown',()=>lastInput='keyboard',true);
document.addEventListener('pointerdown',()=>lastInput='pointer',true);
const token=$('meta[name=catalog-token]').content;
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'X-Catalog-Token':token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(body?90000:15000)});const j=await r.json();if(!r.ok)throw Error(j.error||'Не удалось выполнить действие.');return j;}
function toast(message){$('#toast').textContent=message;$('#toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').style.display='none',4200);}
function safeURL(s){try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}}
const link=(url,label)=>safeURL(url)?`<a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:'';
function parseRoute(){const route=new URLSearchParams(location.hash.slice(1));const id=route.get('project');page=route.get('page')||'all';if(id){page='project';filters.project=id;}else filters.project='';filters.favorite=page==='favorites';if(!['all','project','favorites','notes','history','wishes','guide'].includes(page))page='all';}
function project(){return data.projects.find(p=>p.id===filters.project)||null;}
function routeFor(id){return id?'#project='+encodeURIComponent(id):'#all';}
function sidebar(){
 const count=data.addons.filter(a=>presence(componentsFor(a))==='installed').length;
 const nav=(href,label,ico,active,count='')=>`<a href="${href}" class="nav-link ${active?'active':''}" ${active?'aria-current="page"':''}>${icon(ico)}<span>${esc(label)}</span>${count!==''?`<span class="count">${count}</span>`:''}</a>`;
 $('#navigation').innerHTML=nav('#all','Весь Codex','all',page==='all',count)+nav('#page=favorites','Избранное','star',page==='favorites')+'<p class="nav-heading">Проекты</p>'+data.projects.map(p=>`<a class="nav-link ${filters.project===p.id?'active':''}" href="${routeFor(p.id)}" ${filters.project===p.id?'aria-current="page"':''} title="${esc(p.path)}"><span class="project-dot" aria-hidden="true"></span><span class="project-label">${esc(p.name)}</span></a>`).join('')+'<button class="quiet add-project" id="add-project">+ Добавить проект</button><p class="nav-heading">Мои записи</p>'+nav('#page=notes','Заметки','notes',page==='notes')+nav('#page=history','История','history',page==='history')+nav('#page=wishes','Пожелания','folder',page==='wishes')+'<p class="nav-heading">О каталоге</p>'+nav('#page=guide','Что здесь показано','info',page==='guide');
 $('#legacy-link').href=data.legacy_url; $('#add-project').onclick=addProject;
 $('#legacy-link').onclick=async e=>{e.preventDefault();const tab=window.open('about:blank','_blank');if(tab)tab.opener=null;try{const result=await api('legacy',{});if(tab)tab.location.href=result.url;else location.href=result.url;}catch(error){tab?.close();toast(error.message);}};
 $('#crumb').textContent=project()?.name||({all:'Весь Codex',favorites:'Избранное',notes:'Заметки',history:'История',wishes:'Пожелания',guide:'Что здесь показано'}[page]);
 $('#footer').innerHTML=`<span>Сверка ${esc(date(data.updated_at,true))} · ${esc(data.version)}</span><button class="quiet" id="coverage">Откуда эти сведения ${icon('info')}</button>`;
 $('#coverage').onclick=coverage;
}
function heading(title,sub,right=''){return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(sub)}</p></div>${right}</div>`;}
function select(field,label,options){
 if(field==='presence')return `<label>${label}<select data-filter="${field}" aria-label="${label}">${options.map(([key,name])=>`<option value="${esc(key)}" ${filters[field]===key?'selected':''}>${esc(name)}</option>`).join('')}</select></label>`;
 const chosen=values(filters[field]);
 return `<div class="multi-field"><span id="label-${field}">${label}</span><details class="multi" data-multi="${field}"><summary aria-labelledby="label-${field} value-${field}"><span id="value-${field}" data-default="${esc(options[0][1])}">${esc(chosen.length?options.filter(([k])=>chosen.includes(k)).map(([,v])=>v).join(', '):options[0][1])}</span><span aria-hidden="true">⌄</span></summary><div class="multi-options" role="group" aria-labelledby="label-${field}">${options.filter(([key])=>key).map(([key,name])=>`<label><input type="checkbox" data-multi-filter="${field}" value="${esc(key)}" ${chosen.includes(key)?'checked':''}><span>${esc(name)}</span></label>`).join('')}<button class="quiet" data-multi-clear="${field}">Снять выбор</button></div></details></div>`;
}
function inventory(){
 const p=project();
 const scope=data.addons.map(a=>componentsFor(a,p));const installed=scope.filter(c=>presence(c)==='installed').length;
 const global=scope.filter(c=>c.some(x=>x.installed&&x.scope==='global')).length, local=scope.filter(c=>c.some(x=>x.installed&&x.scope==='local')).length;
 const scopeLabel=p?`<button type="button" class="scope-label secondary" id="project-open" aria-label="Открыть папку проекта в Проводнике" title="${esc(p.path)}">${icon('folder')} Открыть папку</button>`:`<span class="scope-label">${icon('globe').replace('<svg','<svg width="14" height="14"')} Этот компьютер</span>`;
 $('#main').innerHTML=heading(p?p.name:page==='favorites'?'Избранное':'Весь Codex',p?'Общие надстройки Codex и собственные надстройки этого проекта.':page==='favorites'?'То, что вы хотите держать под рукой.':'Все ваши надстройки: что установлено, из чего состоит и где работает.',scopeLabel)+
 `<div class="overview-line"><span><span class="status-dot"></span><strong>${plural(installed,'надстройка установлена','надстройки установлены','надстроек установлено')}</strong></span><span>Глобально <strong>${global}</strong></span><span>Локально <strong>${local}</strong></span></div><section class="filters" aria-label="Фильтры надстроек"><div class="type-row" role="group" aria-label="Состав надстройки"><button class="type-chip" data-type="all" aria-pressed="${!filters.types.length}">${icon('all')}Все типы</button>${Object.entries(typeNames).map(([k,v])=>`<button class="type-chip" data-type="${k}" aria-pressed="${filters.types.includes(k)}">${icon(k)}${v}<span data-count="${k}"></span></button>`).join('')}</div><div class="filter-row">${select('scope','Область',[['','Глобальные и локальные'],['global','Только глобальные'],['local','Только локальные'],['unknown','Не уточнена']])}${select('enabled','Включение',[['','Любое'],['on','Включено'],['off','Отключено'],['unknown','Не проверено']])}${select('direction','Назначение',[['','Все направления'],...data.directions.map(d=>[d.id,d.title])])}<label class="search">Найти по названию<input id="search" type="search" value="${esc(filters.query)}" placeholder="Например, Blender" aria-label="Найти по названию"></label><button id="more-filters" class="quiet filter-more" aria-expanded="false">${icon('filter')}Ещё фильтры</button></div><div class="filter-row advanced" id="advanced">${select('presence','Наличие',[['known','Все обнаруженные части'],['installed','Установлено'],['unconfirmed','Не подтверждено'],['suggested','Можно добавить'],['all','Все записи каталога']])}${select('origin','Происхождение',[['','Любое'],...Object.entries(origins)])}${select('billing','Расходы',[['','Любые'],...Object.entries(bills)])}${select('tag','Тег',[['','Любой'],...[...new Set(data.addons.flatMap(a=>[...a.tags,...(data.overlay.items[a.id]?.tags||[])]))].sort().map(t=>[t,t])])}</div><p class="filter-hint" id="type-hint" hidden></p></section><div id="active-filters" class="active-filters"></div><div class="results-line"><span id="result-count" role="status" aria-live="polite"></span><div class="result-actions"><select id="sort" aria-label="Порядок карточек"><option value="custom">Мой порядок</option><option value="composition">Сначала составные</option><option value="name">По названию</option></select><button class="quiet" id="reset-filters">Сбросить фильтры</button></div></div><div class="grid" id="grid"></div>`;
 $('#sort').value=sortMode; $('#sort').onchange=e=>{sortMode=e.target.value;localStorage.setItem('catalog-sort',sortMode);paintGrid();};
 $('#search').oninput=e=>{filters.query=e.target.value;paintGrid();};
 document.querySelectorAll('[data-filter]').forEach(el=>el.onchange=()=>{filters[el.dataset.filter]=el.value;paintGrid();});
 document.querySelectorAll('[data-multi-filter]').forEach(el=>el.onchange=()=>{const field=el.dataset.multiFilter;filters[field]=[...document.querySelectorAll(`[data-multi-filter="${field}"]:checked`)].map(x=>x.value);updateMulti(field);paintGrid();});
 document.querySelectorAll('[data-multi-clear]').forEach(b=>b.onclick=()=>{const f=b.dataset.multiClear;filters[f]=[];document.querySelectorAll(`[data-multi-filter="${f}"]`).forEach(x=>x.checked=false);updateMulti(f);paintGrid();});
 document.querySelectorAll('.multi').forEach(el=>el.addEventListener('toggle',()=>{if(el.open){positionMulti(el);document.querySelectorAll('.multi').forEach(other=>{if(other!==el)other.open=false;});}}));
 document.querySelectorAll('[data-type]').forEach(btn=>btn.onclick=()=>{const k=btn.dataset.type;filters.types=k==='all'?[]:filters.types.includes(k)?filters.types.filter(x=>x!==k):[...filters.types,k];paintGrid();});
 $('#more-filters').onclick=()=>{const v=$('#advanced').classList.toggle('open');$('#more-filters').setAttribute('aria-expanded',v);};
 $('#reset-filters').onclick=()=>{filters={project:filters.project,favorite:filters.favorite,types:[],scope:'',enabled:'',presence:'installed',direction:'',origin:'',tag:'',billing:'',query:''};inventory();};
 if(p)$('#project-open').onclick=e=>openProjectFolder(p,e.currentTarget);
 paintGrid();
}
function scopeLabel(parts){const scopes=[...new Set(parts.filter(c=>c.installed).map(c=>c.scope))];return scopes.includes('global')&&scopes.includes('local')?'Глобально + локально':scopeNames[scopes[0]]||'Не подтверждено';}
function composition(parts){return Object.keys(typeNames).filter(k=>parts.some(p=>p.kind===k)).map(k=>{const n=parts.filter(p=>p.kind===k).length;return `<span class="badge ${k}">${({skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение',program:'Программа'})[k]}${n>1?' ×'+n:''}${parts.filter(p=>p.kind===k).every(p=>!p.installed)?' · не подтверждено':parts.some(p=>p.kind===k&&!p.installed)?' · есть непроверенные':''}</span>`;}).join('');}
function paintGrid(){
 const rows=visible(data,filters).sort((a,b)=>(Number(b.overlay.favorite??b.addon.favorite)-Number(a.overlay.favorite??a.addon.favorite))||(sortMode==='composition'?new Set(b.parts.map(c=>c.kind)).size-new Set(a.parts.map(c=>c.kind)).size:0)||a.addon.title.localeCompare(b.addon.title,'ru'));
 const saved=data.overlay.orders?.[filters.project||'all']||[];if(sortMode==='custom')rows.sort((a,b)=>(saved.includes(a.addon.id)?saved.indexOf(a.addon.id):Infinity)-(saved.includes(b.addon.id)?saved.indexOf(b.addon.id):Infinity));
 $('#result-count').innerHTML=`<strong>${plural(rows.length,'надстройка','надстройки','надстроек')}</strong>${filters.types.length?' по выбранным условиям':''}`;
 document.querySelectorAll('[data-type]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.type==='all'?!filters.types.length:filters.types.includes(b.dataset.type)));
 const candidates=visible(data,filters,true);
 document.querySelectorAll('[data-count]').forEach(el=>el.textContent=candidates.filter(r=>r.matching.some(c=>c.kind===el.dataset.count)).length);
 $('#type-hint').hidden=filters.types.length<2;$('#type-hint').textContent='Показаны надстройки, в составе которых есть все выбранные типы. Остальные фильтры действуют одновременно.';
 const labels={scope:'Область',enabled:'Включение',presence:'Наличие',direction:'Назначение',origin:'Происхождение',tag:'Тег',billing:'Расходы'};
 $('#active-filters').innerHTML=Object.entries(labels).filter(([k])=>values(filters[k]).length&&!(k==='presence'&&filters[k]==='installed')).map(([k,v])=>`<button class="clear-chip" data-clear="${k}">${v}: ${esc($(`[data-filter="${k}"] option:checked`)?.textContent||$(`#value-${k}`)?.textContent||filters[k])} ×</button>`).join('');
 document.querySelectorAll('[data-clear]').forEach(b=>b.onclick=()=>{filters[b.dataset.clear]=b.dataset.clear==='presence'?'installed':'';inventory();});
 $('#grid').innerHTML=rows.length?rows.map(({addon:a,parts,overlay,presence:found})=>{const s=status(parts),kind=parts.some(c=>c.kind==='plugin')?'plugin':parts.some(c=>c.kind==='mcp')?'mcp':'skill';return `<article class="addon" data-addon="${esc(a.id)}"><div class="addon-head"><span class="addon-mark ${kind}">${icon(kind)}</span><button class="addon-name" data-open="${esc(a.id)}">${esc(a.title)}</button></div><button class="favorite" data-favorite="${esc(a.id)}" aria-label="В избранное: ${esc(a.title)}" aria-pressed="${overlay.favorite??a.favorite}">${icon('star')}</button><p class="addon-description">${esc(a.description||'Описание пока не подготовлено. Состав и источники доступны в карточке.')}</p><div class="composition">${composition(parts)||'<span class="badge">Есть описание подключения</span>'}</div><div class="addon-state-line ${s.key}">${esc(s.label)}</div><div class="addon-bottom"><span class="scope">${icon(parts.some(c=>c.scope==='local')?'folder':'globe')}${esc(scopeLabel(parts))}</span><span class="state ${s.key}">${found==='installed'?'Установлено':found==='unconfirmed'?'Не подтверждено':'Можно добавить'}</span></div>${sortMode==='custom'?`<div class="order-controls"><button class="drag-handle quiet" draggable="true" data-drag="${esc(a.id)}" aria-label="Переставить: ${esc(a.title)}" title="Перетащите или используйте Alt + стрелку вверх / вниз">⠿ <span>Переставить</span></button><button class="quiet order-up" data-move="${esc(a.id)}" data-step="-1" aria-label="Выше: ${esc(a.title)}">↑</button><button class="quiet order-down" data-move="${esc(a.id)}" data-step="1" aria-label="Ниже: ${esc(a.title)}">↓</button></div>`:''}${parts.some(c=>c.restriction)?'<div class="restriction">Есть ограничение по проекту</div>':''}</article>`;}).join(''):`<div class="empty"><h2>Нет надстроек с таким сочетанием</h2><p>Уберите одно условие или сбросьте фильтры.</p><button class="secondary" id="empty-reset">Сбросить фильтры</button></div>`;
 document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openAddon(b.dataset.open));
 document.querySelectorAll('[data-favorite]').forEach(b=>b.onclick=()=>save(b.dataset.favorite,'favorite',{value:b.getAttribute('aria-pressed')!=='true'}).catch(e=>toast(e.message)));
 bindOrdering(rows);
 if($('#empty-reset'))$('#empty-reset').onclick=()=>$('#reset-filters').click();
}
function section(title,body){return body?`<section class="section"><h2>${esc(title)}</h2>${body}</section>`:'';}
function textList(value){if(!value||Array.isArray(value)&&!value.length)return '';return Array.isArray(value)?`<ul>${value.map(v=>`<li>${esc(typeof v==='string'?v:JSON.stringify(v))}</li>`).join('')}</ul>`:`<p>${esc(value)}</p>`;}
function componentHTML(c){
 const projectName=c.contextId?data.projects.find(p=>p.id===c.contextId)?.name:c.project_path?data.projects.find(p=>p.path===c.project_path)?.name:'';
 const installed=c.installed?'Установлено':'Наличие не подтверждено';
 const enabled=c.enabled===true?'Включено':c.enabled===false?'Отключено':'Включение не проверено';
 const details=[c.path?`<p>Путь: <span class="path">${esc(c.path)}</span></p>`:'',c.version?`<p>Версия: ${esc(c.version)}</p>`:'',c.fingerprint?`<p>Отпечаток версии: <code>${esc(c.fingerprint)}</code></p>`:'',...(c.sources||[]).map(s=>`<p>${esc(s.scope)}: <span class="path">${esc(s.path)}</span>${s.applied?'':' (не применяется)'}</p>`)].join('');
 const seen=(c.observations||[]).filter(o=>o.kind==='session');
 return `<article class="component"><div class="component-header"><strong>${esc(c.title||c.name)}</strong><span class="badge ${c.kind}">${({skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение',program:'Программа'})[c.kind]||esc(c.kind)}</span></div><div class="component-status"><span>${esc(scopeNames[c.scope]||'Не уточнено')}${projectName?' · '+esc(projectName):''}</span><span>· ${installed}</span><span>· ${enabled}</span></div>${c.connection?.reason?`<p>${esc(c.connection.label)}. ${esc(c.connection.reason)}</p>`:''}${c.basis?`<p>${esc(c.basis)}</p>`:''}${seen.length?`<p>В метаданных этого чата: ${esc(date(seen.at(-1).at))}. Это свидетельство доступности на указанную дату.</p>`:''}${c.restriction?`<div class="soft-note amber">${esc(c.restriction)}</div>`:''}${c.approval?`<p>Запрос разрешения: ${esc(c.approval==='prompt'?'перед операцией':c.approval==='default'?'по настройкам Codex':c.approval)}.</p>`:''}${c.policy&&c.policy!=='inherit'?`<p>Правило в каталоге: ${esc(({explicit:'только по явной команде',ask:'с подтверждением операции',blocked:'не использовать'})[c.policy]||c.policy)}. Это заметка о применении, не изменение разрешений.</p>`:''}${c.kind==='skill'?`<div class="links"><button class="quiet" data-instruction="${esc(c.skill_id)}">Прочитать инструкцию</button><button class="quiet" data-copy="${esc(c.name)}">Скопировать вызов</button></div>`:''}${controlHTML(c,true)}${details?`<details><summary>Путь, версия и основание</summary>${details}${c.checked_at?`<p>Сверено ${esc(date(c.checked_at,true))}</p>`:''}</details>`:''}</article>`;
}
function controlHTML(c,explain=false){
 const control=c.control;
 if(!control?.supported)return explain?`<p class="tiny control-unavailable">${esc(control?.message||'Переключатель для этой части пока недоступен.')}</p>`:'';
 const name=c.title||c.name;
 return `<div class="control-row"><div><strong>${esc(name)}</strong><small>Глобально · на этом компьютере</small></div><button class="codex-switch" role="switch" aria-checked="${control.enabled}" aria-label="Использовать в Codex: ${esc(name)}" data-activation="${esc(c.id)}" data-context="${esc(c.contextId||filters.project||'all')}"><span class="switch-track" aria-hidden="true"></span><span>${control.enabled?'Включено':'Отключено'}</span></button></div>${c.state_note?`<p class="tiny">${esc(c.state_note)}</p>`:c.enabled!==null&&c.enabled!==control.enabled?`<p class="tiny">В этом проекте: ${c.enabled?'включено':'отключено'}. Его действующая настройка отличается от общей.</p>`:''}`;
}
function controlsHTML(parts){
 const available=parts.filter(c=>c.control?.supported);
 return section('Использовать в Codex',`${available.map(c=>controlHTML(c)).join('')||'<p class="tiny">Управление этими частями доступно в настройках Codex. Причина указана во вкладке «Состав».</p>'}${available.length?'<p class="tiny">Изменение сохраняется в настройках на этом компьютере и в истории. Перезапустите Codex, чтобы открытые чаты получили новое состояние. Настройки отдельных проектов могут иметь приоритет.</p>':''}<p class="control-result" role="status"></p>`);
}
function bindControls(){
 document.querySelectorAll('[data-activation]').forEach(button=>button.onclick=async()=>{
  if(switching){toast('Дождитесь сохранения текущего переключения.');return;}
  const id=selected,tab=detailTab;
  const addon=data.addons.find(a=>a.id===id);
  const component=componentsFor(addon,project()).find(c=>c.id===button.dataset.activation&&(c.contextId||filters.project||'all')===button.dataset.context);
  if(!component?.control?.supported)return;
  switching=true;stateEpoch++;
  const buttons=[...document.querySelectorAll('[data-activation]')];buttons.forEach(b=>b.disabled=true);
  const target=$('.control-result');if(target)target.textContent='Сохраняем настройку в Codex…';
  let message='';
  try{
   const response=await api('activation',{id,component_id:component.id,context:button.dataset.context,enabled:!component.control.enabled,revision:component.control.revision});
   data=response.state;
   message=response.result.unchanged?'Настройка уже имеет это значение.':response.result.warning||'Сохранено в Codex и истории. Требуется перезапуск Codex.';
  }catch(error){message=error.message;try{data=await api('state');}catch{/* Keep the last confirmed state; no optimistic switch. */}}
  finally{
   switching=false;stateEpoch++;clearTimeout(poll);poll=setTimeout(load,15000);
   if(['all','project','favorites'].includes(page))paintGrid();
   if($('#details').open&&selected===id){openAddon(id,tab);const result=$('.control-result');if(result)result.textContent=message;}
   buttons.forEach(b=>b.disabled=false);toast(message);
  }
 });
}
function overviewHTML(a,parts){
 const profile=a.profile||{},overlay=data.overlay.items[a.id]||{};
 const purposes=a.directions.map(id=>data.directions.find(d=>d.id===id)?.title||id);
 let html=`<div class="info-grid"><div class="info-cell"><small>Область</small>${esc(scopeLabel(parts))}</div><div class="info-cell"><small>Происхождение</small>${esc(origins[a.origin]||a.origin)}</div><div class="info-cell"><small>Назначение</small>${esc(purposes.join(', ')||'Пока не указано')}</div><div class="info-cell"><small>Расходы</small>${esc(bills[a.billing]||'Не уточнены')}</div></div>`;
 html+=instructionActions(parts);
 html+=controlsHTML(parts);
 if(profile.capabilities?.length)html+=section('Что умеет',textList(profile.capabilities));
 if(profile.example)html+=section('Пример команды в Codex',textList(profile.example)+'<button class="secondary" id="copy-example">Скопировать пример</button><p class="tiny">Копирование не запускает действие.</p>');
 for(const s of a.skills){
  html+=section(a.skills.length>1?s.title_ru||s.name:'Как помогает',textList(s.helps||s.description_ru||s.description_original||s.description));
  html+=(s.capability_groups||[]).map(g=>section(g.title,textList(g.text))).join('');
  html+=section('Что получится',textList(s.output))+section('Когда выбирать',textList(s.choose_when))+section('Что подготовить',textList(s.prepare||s.dependencies));
  if(s.capability_limits)html+=`<div class="soft-note amber">${esc(s.capability_limits)}</div>`;
 }
 if(parts.some(c=>c.restriction))html+=`<div class="soft-note amber">${esc(parts.find(c=>c.restriction).restriction)}</div>`;
 html+=section('Данные, ограничения и расходы',textList(profile.data_access)+textList(profile.limitations)+textList(profile.pricing));
 if(a.bindings.length)html+=section('Записанные связи с проектами',a.bindings.map(b=>`<p><strong>${esc(b.project_name)}</strong>: ${esc(b.purpose)}<br><span class="tiny">${esc(({recommended:'Рекомендация',codex_use:'Записано использование в Codex',runtime:'Записана интеграция'})[b.role]||b.role)}${b.evidence?' · '+esc(b.evidence):''}</span></p>`).join(''));
 const related=a.related.map(id=>data.addons.find(x=>x.id===id)).filter(Boolean);
 if(related.length)html+=section('Полезно вместе',`<p>Связанные возможности; они не входят автоматически в состав этой надстройки.</p><div class="links">${related.map(r=>`<button class="secondary" data-related="${esc(r.id)}">${esc(r.title)}</button>`).join('')}</div>`);
 html+=section('Теги',`<div class="tag-list">${[...new Set([...a.tags,...(overlay.tags||[])])].map(t=>`<span class="tag">${esc(t)}</span>`).join('')||'<span class="tiny">Пока нет тегов.</span>'}</div><form class="note-form" id="tags-form"><label for="tags-input">Мои дополнительные теги</label><input id="tags-input" value="${esc((overlay.tags||[]).join(', '))}" placeholder="Через запятую"><button class="secondary" type="submit">Сохранить теги</button><p class="error" role="alert"></p></form>`);
 return html;
}
function sourcesHTML(a,parts){const p=a.profile||{};return section('Поставщик и документация',textList(p.provider)+textList(p.integration_author)+`<div class="links">${link(p.website,'Сайт')}${link(p.documentation,'Документация')}${link(p.connection_documentation,'Подключение')}</div>`)+section('Основание описания',textList(p.evidence))+a.skills.map(s=>section(s.title_ru||s.name,`<p>Автор: ${esc(s.author_profile?.name||'Не указан')}</p><div class="links">${(s.author_profile?.links||[]).map(l=>link(l.url,l.label)).join('')}</div>${textList(s.origin_evidence)}<p class="tiny">Русская инструкция: ${esc(s.instruction_localization?.message||'Нет сведений')}</p>`)).join('')+section('Как подключается',textList(p.connection_method)+textList(p.connection_requirements)+textList(p.connection_steps)+textList(p.reviewed_at?'Описание проверено: '+date(p.reviewed_at):''))+section('Границы проверки',`<p>Области и включение проверяются по настройкам. Успешное применение к задаче показывается только при наличии отдельной записи.</p><p>Каталог показывает настройки Codex. Подтверждённые личные навыки и пользовательские настройки MCP, плагинов и приложений можно включать и отключать в карточке. Установка, доступ к аккаунтам и разрешения операций здесь не меняются.</p>`);}
function notesHTML(a){const item=data.overlay.items[a.id]||{};return section('Мои заметки',`<div class="notes-list">${a.notes.map(n=>`<div class="note">${esc(n)}<small>Из прежнего каталога</small></div>`).join('')}${(item.notes||[]).map(n=>`<div class="note">${esc(n.text)}<small>${esc(date(n.at,true))} · новый вариант</small></div>`).join('')}${!a.notes.length&&!item.notes?.length?'<p>Здесь можно сохранить своё наблюдение об этой надстройке.</p>':''}</div>${noteForm('note','Новая заметка')}`)+section('Проверенный опыт',a.skills.flatMap(s=>(s.verified_experience||[]).map(e=>`<div class="note">${esc(e.task||'Применение')}<p>${esc(e.result||'')}</p><small>${esc(e.date||'')} ${esc(e.limitations||'')}</small></div>`)).join('')||'<p>Записанного опыта пока нет. Это не означает, что надстройку никогда не использовали.</p>')+section('Опыт других версий',textList(a.skills.flatMap(s=>(s.historical_experience||[]).map(e=>(e.task||'Применение')+' — '+(e.result||'')))))+section('История этой надстройки',eventsHTML(a));}
function noteForm(action,label){return `<form class="note-form" data-note-action="${action}"><label for="note-text">${label}</label><textarea id="note-text" required maxlength="20000" placeholder="Ваш текст…"></textarea><div class="actions"><span class="tiny">Личная запись сохранится на этом компьютере.</span><button class="primary" type="submit">Сохранить ${action==='wish'?'пожелание':'заметку'}</button></div><p class="error" role="alert"></p></form>`;}
function openAddon(id,tab='overview'){
 const a=data.addons.find(a=>a.id===id);if(!a)return;selected=id;detailTab=tab;const parts=componentsFor(a,project());
 $('#detail-content').innerHTML=`<header class="drawer-head"><span>${esc(project()?.name||'Весь Codex')} / Надстройка</span><button class="icon-button" id="close-detail" aria-label="Закрыть карточку">${icon('close')}</button></header><div class="drawer-body"><div class="drawer-title"><span class="addon-mark">${icon(parts.some(c=>c.kind==='mcp')?'mcp':'skill')}</span><div><h1 id="detail-title">${esc(a.title)}</h1><div class="composition">${composition(parts)}</div></div></div><p class="drawer-intro">${esc(a.description)}</p><div class="drawer-tabs" role="group" aria-label="Раздел карточки">${[['overview','Обзор'],['composition','Состав · '+parts.length],['notes','Заметки и опыт'],['sources','Источники']].map(([k,v])=>`<button data-tab="${k}" aria-pressed="${detailTab===k}">${v}</button>`).join('')}</div><div id="drawer-panel">${detailTab==='overview'?overviewHTML(a,parts):detailTab==='composition'?`<p class="tiny">Каждая часть имеет свою область и состояние. Типы в фильтрах соответствуют этому составу.</p>${parts.map(componentHTML).join('')||'<p>Действующая установка не обнаружена. Это справочная карточка.</p>'}<p class="control-result" role="status"></p>`:detailTab==='notes'?notesHTML(a):sourcesHTML(a,parts)}</div></div>`;
 $('#close-detail').onclick=()=>closeDialog($('#details'));
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>openAddon(id,b.dataset.tab));
 document.querySelectorAll('[data-related]').forEach(b=>b.onclick=()=>openAddon(b.dataset.related));
 bindInstructionActions();
 bindControls();
 if($('#copy-example'))$('#copy-example').onclick=async()=>{try{await navigator.clipboard.writeText(a.profile.example);toast('Пример скопирован.');}catch{toast('Не удалось скопировать. Пример приведён выше.');}};
 bindNotes(id);
 if($('#tags-form'))$('#tags-form').onsubmit=async e=>{e.preventDefault();try{await save(id,'tags',{text:$('#tags-input').value});}catch(error){$('#tags-form .error').textContent=error.message;}};
 if(!$('#details').open)showDialog($('#details'));
}
function bindNotes(id){document.querySelectorAll('[data-note-action]').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('[type=submit]');b.disabled=true;try{await save(id,form.dataset.noteAction,{text:form.querySelector('textarea').value});}catch(error){form.querySelector('.error').textContent=error.message;}finally{b.disabled=false;}});}
async function save(id,action,extra){data.overlay=await api('annotate',{id,action,revision:data.overlay.revision,...extra});toast('Сохранено.');if(['all','project','favorites'].includes(page))paintGrid();else renderPage();if($('#details').open)openAddon(selected,detailTab);}
const eventNames={preview_order:'Изменён порядок карточек',preview_project:'Добавлен проект',preview_note:'Добавлена заметка',preview_favorite:'Изменено избранное',preview_tags:'Изменены теги',preview_wish:'Записано пожелание',inventory_refreshed:'Сверены установки',skill_note_added:'Добавлена заметка к навыку',note_added:'Добавлена заметка',search_started:'Начат поиск навыков',search_completed:'Сохранена подборка',operation_started:'Начата операция',operation_completed:'Завершена операция',skill_activation_changed:'Изменено включение навыка',skill_activation_unconfirmed:'Переключение навыка не подтверждено',extension_activation_changed:'Изменено включение надстройки',extension_activation_unconfirmed:'Переключение надстройки не подтверждено',resource_catalog_changed:'Изменена карточка ресурса',organization_changed:'Изменена классификация',directions_changed:'Изменены направления',project_catalog_changed:'Изменены сведения проекта',manager_favorite_changed:'Изменено избранное'};
function eventSummary(e){const x=e.data||{};if(e.kind.includes('activation'))return `${x.component_name||x.skill_name||x.resource_name||''}: ${x.before_enabled?'включено':'отключено'} → ${x.actual_enabled===true?'включено':x.actual_enabled===false?'отключено':'не подтверждено'}${x.restart_required?' · требуется перезапуск Codex':''}`;return x.query||x.detail||x.reason||x.text||x.skill_name||x.resource_name||x.target||x.task||e.value||'';}
function eventsHTML(a=null){const ids=a?new Set([a.id,...a.skills.map(s=>s.id),...a.components.map(c=>c.id)]):null;const rows=[...data.events.map(e=>({...e,legacy:true})),...data.overlay.events].filter(e=>!ids||ids.has(e.extension_id)||Object.values(e.data||{}).some(v=>typeof v==='string'&&ids.has(v))).sort((a,b)=>String(b.at||b.timestamp).localeCompare(String(a.at||a.timestamp))).slice(0,a?30:150);return rows.length?rows.map(e=>`<article class="event"><time>${esc(date(e.at||e.timestamp,true))}</time><div><strong>${esc(eventNames[e.kind]||'Запись каталога')}</strong><p>${esc(typeof eventSummary(e)==='string'?eventSummary(e):JSON.stringify(eventSummary(e)))}</p><span class="tiny">${e.kind.includes('activation')?'Настройки Codex':e.legacy?'Архивная история':'Каталог 3.1'}</span><details><summary>Подробности записи</summary><div class="document">${esc(JSON.stringify(e.data||{value:e.value},null,2))}</div></details></div></article>`).join(''):'<p class="tiny">Записей пока нет.</p>';}
function documentsHTML(ids){return `<div class="doc-links">${data.documents.filter(d=>ids.includes(d.id)).map(d=>`<button class="secondary" data-doc="${d.id}">${icon('notes')}${esc(d.title)}</button>`).join('')}</div>`;}
function bindDocuments(){document.querySelectorAll('[data-doc]').forEach(b=>b.onclick=()=>{const d=data.documents.find(d=>d.id===b.dataset.doc);readPanel(d.title,`<p class="path">${esc(d.path)}</p>${markdown(d.text)}`);});}
function renderPage(){
 sidebar();
 if(['all','project','favorites'].includes(page)){inventory();return;}
 if(page==='history')$('#main').innerHTML=heading('История','Что менялось, что искали и что уже проверяли.')+documentsHTML(['journal'])+'<div class="timeline">'+eventsHTML()+'</div>';
 if(page==='notes'||page==='wishes'){
  const wish=page==='wishes',kind=wish?'wishes':'notes';
  $('#main').innerHTML=heading(wish?'Пожелания':'Заметки',wish?'Идеи для следующего шага, с сохранением исходной формулировки.':'Ваши наблюдения о надстройках и общие записи.')+documentsHTML(wish?['backlog']:['inbox'])+`<div class="notebook">${noteForm(wish?'wish':'note',wish?'Новое пожелание':'Общая заметка')}${Object.entries(data.overlay.items).flatMap(([id,v])=>(v[kind]||[]).map(n=>`<article class="page-note"><h2>${esc(data.addons.find(a=>a.id===id)?.title||'Общая запись')}</h2><div class="document">${esc(n.text)}</div><p class="tiny">${esc(date(n.at,true))} · Новый вариант</p></article>`)).join('')}${wish?'':data.addons.filter(a=>a.notes.length).map(a=>`<article class="page-note"><h2><button class="quiet" data-note-open="${esc(a.id)}">${esc(a.title)}</button></h2>${a.notes.map(n=>`<p class="document">${esc(n)}</p>`).join('')}<p class="tiny">Из прежнего каталога</p></article>`).join('')}</div>`;
  bindNotes('workspace');document.querySelectorAll('[data-note-open]').forEach(b=>b.onclick=()=>openAddon(b.dataset.noteOpen,'notes'));
 }
 if(page==='guide')$('#main').innerHTML=heading('Ваш Codex, по полочкам','Два уровня обзора, одна карточка для каждой надстройки.')+`<div class="notebook"><section class="page-note"><h2>Весь Codex и проекты</h2><p>«Весь Codex» показывает обнаруженные надстройки на этом компьютере, включая локальные установки известных проектов. Выберите проект слева: общие установки останутся в списке, к ним добавятся его собственные.</p><p><strong>Глобально</strong> — установлено для пользователя, аккаунта или вместе с Codex. <strong>Локально</strong> — относится к папке проекта. У общей инструкции тоже может быть ограничение по назначению.</p></section><section class="page-note"><h2>Одна надстройка — несколько частей</h2><p>Навык — инструкция для Codex. MCP — подключение внешних инструментов. Плагин — комплект, который может включать и то и другое. Приложение — интеграция с сервисом аккаунта. Программа — найденное приложение на компьютере.</p><p>Надстройка с навыком и MCP отображается в обоих фильтрах. Нажмите оба фильтра одновременно, чтобы оставить только надстройки, содержащие обе части.</p></section><section class="page-note"><h2>Что установлено и что работает</h2><p>Наличие установки, включение в настройках и успешная работа — разные сведения. Откройте «Состав»: здесь для каждой части указаны область, состояние и основание. Непроверенное так и подписано.</p><p>Карточки «Можно добавить» — справочник вариантов. Они не смешиваются с вашими записями по умолчанию.</p></section><section class="page-note"><h2>Обновление и личные записи</h2><p>Сведения сверяются при запуске, после изменений местных файлов и каждые пять минут для приложений аккаунта. Ваши заметки, теги, избранное и порядок карточек сохраняются отдельно от снимка установок. Переключатели «Использовать в Codex» сохраняют включение личных навыков и поддерживаемых подключений. Изменения записываются в историю; для открытых чатов нужен перезапуск Codex. Установка, удаление, подключение аккаунтов и разрешения операций здесь не меняются.</p><button class="secondary" id="guide-coverage">Посмотреть границы проверки</button></section></div>`;
 bindDocuments();if($('#guide-coverage'))$('#guide-coverage').onclick=coverage;
}
function readPanel(title,html){$('#reader-title').textContent=title;$('#reader-actions').innerHTML='';$('#reader-content').innerHTML=html;if(!$('#reader').open)showDialog($('#reader'));$('#reader').scrollTop=0;}
function addProject(){
 readPanel('Добавить проект',`<p>Каталог прочитает навыки и настройки в этой папке. Сам проект и его настройки останутся прежними.</p><form class="note-form" id="project-form"><label for="project-name">Название</label><input id="project-name" required maxlength="100" placeholder="Мой проект"><label for="project-path">Папка на этом компьютере</label><input id="project-path" required placeholder="C:\\Projects\\MyProject"><button class="primary" type="submit">Добавить и сверить</button><p class="error" role="alert"></p></form>`);
 $('#project-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;try{await api('project',{name:$('#project-name').value,path:$('#project-path').value});$('#reader').close();toast('Проект добавлен в новый вариант. Сверяем его сведения.');await load();}catch(error){form.querySelector('.error').textContent=error.message;}finally{button.disabled=false;}};
}
function coverage(){readPanel('Откуда эти сведения',`<p>Последняя сверка: ${esc(date(data.updated_at,true))}.</p><ul class="coverage-list"><li><strong>Файлы навыков</strong><p>Личные папки, системные инструкции, зарегистрированные проекты и пакеты расширений.</p></li><li><strong>Настройки и приложения Codex</strong><p>Отдельно прочитаны для каждой папки проекта. Проверка сервисных операций не запускалась.</p></li><li><strong>Метаданные этого чата</strong><p>${esc(data.coverage.session_label||'Не переданы')}. ${esc(date(data.coverage.session_at))}.</p></li></ul>${reconciliationHTML()}${textList(data.coverage.limits)}${Object.entries(data.coverage.views).filter(([id,v])=>v.warning).map(([id,v])=>`<div class="soft-note amber">${esc(data.projects.find(p=>p.id===id)?.name||'Весь Codex')}: ${esc(v.warning)}</div>`).join('')}<p class="tiny">Кеш пакета сам по себе не считается установленной и включённой надстройкой.</p>`);}
async function load(){clearTimeout(poll);if(switching){poll=setTimeout(load,2000);return;}const epoch=stateEpoch;try{const next=await api('state');if(epoch!==stateEpoch)return;if(next.loading){$('#loading-status').textContent=next.job.state==='error'?next.job.message:'Читаем настройки и папки проектов…';if(next.job.state!=='error')poll=setTimeout(load,1600);return;}const first=!data;const changed=!data||data.updated_at!==next.updated_at||data.overlay.revision!==next.overlay.revision||data.control_revision!==next.control_revision||data.events.length!==next.events.length;data=next;$('#refresh').disabled=data.job.state==='running';$('#refresh').innerHTML=icon('refresh')+(data.job.state==='running'?'Сверяем…':'Сверить с Codex');if(first){parseRoute();renderPage();document.dispatchEvent(new Event("catalog-ready"));}else if(changed){if(!document.querySelector('dialog[open]')&&!document.querySelector('.multi[open]')&&!['TEXTAREA','INPUT'].includes(document.activeElement?.tagName)&&![...document.querySelectorAll('.note-form input,.note-form textarea')].some(el=>el.value!==el.defaultValue)){renderPage();toast('Сведения обновлены. Личные записи сохранены.');}else pendingRender=true;}if(data.job.state==='running')poll=setTimeout(load,2000);else {poll=setTimeout(load,15000);if(data.job.state==='error')toast(data.job.message);}}catch(e){$('#loading-status')?$('#loading-status').textContent=e.message:toast(e.message);}}
$('#refresh').onclick=async()=>{try{$('#refresh').disabled=true;await api('refresh',{});clearTimeout(poll);await load();}catch(e){toast(e.message);$('#refresh').disabled=false;}};
$('#reader-close').onclick=()=>closeDialog($('#reader'));
$('#menu').onclick=()=>setMenu(!$('#sidebar').classList.contains('open'));
$('#navigation').onclick=e=>{if(e.target.closest('a')){setMenu(false);}};
window.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#sidebar').classList.contains('open')){setMenu(false);$('#menu').focus();}});
window.addEventListener('hashchange',()=>{parseRoute();setMenu(false);if($('#details').open)$('#details').close();renderPage();window.scrollTo(0,0);$('#main').focus({preventScroll:true});});
function updateMulti(field){
 const el=$(`#value-${field}`),chosen=[...document.querySelectorAll(`[data-multi-filter="${field}"]:checked`)];
 el.textContent=chosen.length?chosen.map(x=>x.nextElementSibling.textContent).join(', '):el.dataset.default;
}
function positionMulti(el){el.classList.remove('align-right');if(el.querySelector('.multi-options').getBoundingClientRect().right>innerWidth-16)el.classList.add('align-right');}
window.addEventListener('resize',()=>document.querySelectorAll('.multi[open]').forEach(positionMulti));
function instructionActions(parts){
 const skills=[...new Map(parts.filter(c=>c.kind==='skill'&&c.skill_id).map(c=>[c.skill_id,c])).values()];
 return skills.length?`<div class="instruction-actions" aria-label="Инструкции и вызовы">${skills.map(c=>`<div>${skills.length>1?`<strong>${esc(c.title||c.name)}</strong>`:''}<div class="links"><button class="secondary" data-instruction="${esc(c.skill_id)}">${icon('notes')}Прочитать инструкцию</button><button class="quiet" data-copy="${esc(c.name)}">${icon('copy')}Скопировать вызов</button></div></div>`).join('')}</div>`:'';
}
async function copyInvocation(name){
 try{await navigator.clipboard.writeText('Используй навык $'+name+' для моей задачи.');toast('Вызов навыка скопирован.');}
 catch{toast('Копирование недоступно: используйте $'+name);}
}
function bindInstructionActions(){
 document.querySelectorAll('[data-instruction]').forEach(b=>b.onclick=async()=>{
  try{
   const id=b.dataset.instruction,i=await api('instruction?id='+encodeURIComponent(id));
   const skill=data.addons.flatMap(a=>a.components).find(c=>c.skill_id===id);
   const show=original=>{
    readPanel('Инструкция · '+(skill?.title||skill?.name||''),`<p class="tiny">${!original&&i.translation?'Русский текст, сверенный с оригиналом':'Оригинал'} · <span class="path">${esc(i.path)}</span></p>${markdown(!original&&i.translation?i.translation:i.text)}`);
    $('#reader-actions').innerHTML=`${i.translation?`<button class="quiet" id="instruction-language">${original?'Русский текст':'Оригинал'}</button>`:''}<button class="secondary" id="reader-copy">${icon('copy')}Скопировать вызов</button>`;
    $('#reader-copy').onclick=()=>copyInvocation(skill?.name||id);
    if($('#instruction-language'))$('#instruction-language').onclick=()=>show(!original);
   };show(false);
  }catch(e){toast(e.message);}
 });
 document.querySelectorAll('[data-copy]').forEach(b=>b.onclick=()=>copyInvocation(b.dataset.copy));
}
const immediateDialog=()=>lastInput==='keyboard'||matchMedia('(prefers-reduced-motion: reduce)').matches;
function showDialog(dialog){openNativeDialog(dialog,immediateDialog());}
function closeDialog(dialog){return closeNativeDialog(dialog,immediateDialog());}
for(const dialog of document.querySelectorAll('dialog')){
 let backdropDown=false;
 const outside=e=>{const r=dialog.getBoundingClientRect();return e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom;};
 dialog.addEventListener('pointerdown',e=>backdropDown=e.target===dialog&&outside(e));
 dialog.addEventListener('click',e=>{if(backdropDown&&e.target===dialog&&outside(e))closeDialog(dialog);backdropDown=false;});
 dialog.addEventListener('close',()=>{clearDialogMotion(dialog);if(pendingRender&&!document.querySelector('dialog[open]')){pendingRender=false;renderPage();}});
}
function setMenu(open){$('#sidebar').classList.toggle('no-motion',lastInput==='keyboard');$('#sidebar').classList.toggle('open',open);$('#menu').setAttribute('aria-expanded',open);$('#sidebar-shade').hidden=!open;$('.workspace').inert=open&&matchMedia('(max-width:760px)').matches;if(open&&lastInput==='keyboard')$('#navigation a').focus();}
window.addEventListener('resize',()=>{if(innerWidth>760&&$('#sidebar').classList.contains('open'))setMenu(false);});
$('#sidebar-shade').onclick=()=>setMenu(false);
document.addEventListener('click',e=>document.querySelectorAll('.multi[open]').forEach(d=>{if(!d.contains(e.target))d.open=false;}));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const open=document.querySelector('.multi[open]');if(open){open.open=false;open.querySelector('summary').focus();e.preventDefault();}}});

function fullOrder(rows){
 const saved=data.overlay.orders?.[filters.project||'all']||[];
 const known=new Set(data.addons.map(a=>a.id));
 return [...new Set([...saved.filter(id=>known.has(id)),...rows.map(r=>r.addon.id),...known])];
}
async function persistOrder(order,focusId){
 if(orderSaving)return;orderSaving=true;
 const context=filters.project||'all',label=project()?.name||'всего Codex';
 try{
  data.overlay=await api('order',{context,order,revision:data.overlay.revision});
  if($('#grid'))paintGrid();const handle=[...document.querySelectorAll('[data-drag]')].find(b=>b.dataset.drag===focusId);if(context===(filters.project||'all'))handle?.focus({preventScroll:true});toast('Порядок карточек сохранён для '+label+'.');
 }catch(error){toast(error.message);}finally{orderSaving=false;}
}
function bindOrdering(rows){
 if(sortMode!=='custom')return;
 const move=(id,step)=>{const visibleIds=rows.map(r=>r.addon.id),index=visibleIds.indexOf(id),target=visibleIds[index+step];if(!target)return;const order=fullOrder(rows).filter(x=>x!==id);order.splice(order.indexOf(target)+(step>0?1:0),0,id);persistOrder(order,id);};
 document.querySelectorAll('[data-move]').forEach(b=>{b.disabled=rows.findIndex(r=>r.addon.id===b.dataset.move)+(Number(b.dataset.step))<0||rows.findIndex(r=>r.addon.id===b.dataset.move)+Number(b.dataset.step)>=rows.length;b.onclick=()=>move(b.dataset.move,Number(b.dataset.step));});
 document.querySelectorAll('[data-drag]').forEach(handle=>{
  handle.onkeydown=e=>{if(e.altKey&&['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();move(handle.dataset.drag,e.key==='ArrowUp'?-1:1);}};
  handle.ondragstart=e=>{dragged=handle.dataset.drag;e.dataTransfer.setData('text/plain',dragged);e.dataTransfer.effectAllowed='move';handle.closest('.addon').classList.add('dragging');};
  handle.ondragend=()=>{dragged=null;document.querySelectorAll('.addon').forEach(el=>el.classList.remove('dragging','drop-target'));};
 });
 document.querySelectorAll('[data-addon]').forEach(card=>{
  card.ondragover=e=>{if(dragged&&dragged!==card.dataset.addon){e.preventDefault();e.dataTransfer.dropEffect='move';document.querySelectorAll('.drop-target').forEach(x=>x.classList.remove('drop-target'));card.classList.add('drop-target');}};
  card.ondrop=e=>{e.preventDefault();const moving=dragged;if(moving&&moving!==card.dataset.addon)persistOrder(reorderIds(fullOrder(rows),moving,card.dataset.addon),moving);card.classList.remove('drop-target');dragged=null;};
 });
}
function reconciliationHTML(){const r=data.coverage.reconciliation;if(!r)return '';return `<section class="soft-note ${r.complete?'':'amber'}"><strong>${r.complete?'Сопоставление пройдено':'Есть расхождения для проверки'}</strong><p>${r.skill_paths} файлов навыков · ${r.session_skills} навыков из списка чата · ${r.connections} подключений · ${r.project_contexts} папок проектов.</p><p>Пропуски: ${r.missing_skill_paths.length+r.missing_connections.length+r.missing_session_paths.length}. Повторяющиеся части: ${r.duplicate_component_ids.length}.</p><p>${esc(r.limits)}</p></section>`;}
async function openProjectFolder(p,button){
 if(button.disabled)return;
 button.disabled=true;
 try{await api('open-project',{id:p.id});toast('Папка открыта в Проводнике.');}
 catch(error){toast(error.message);}
 finally{button.disabled=false;}
}
load();
