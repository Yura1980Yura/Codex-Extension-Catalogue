function documentationHTML(addon,parts){
 const skills=addon.skills||[],profile=addon.profile||{};
 let html=instructionActions(parts,addon);
 for(const skill of skills){
  const docs=skill.documentation||[];
  if(docs.length)html+=section(skills.length>1?'Документы · '+(skill.title_ru||skill.name):'Документы навыка',`<div class="documentation-list">${docs.map(d=>`<button type="button" class="documentation-item" data-skill-document="${esc(skill.id)}" data-document="${esc(d.id)}">${icon('notes')}<span><strong>${esc(d.title)}</strong><small>${esc(d.id)}</small></span>${icon('chevron')}</button>`).join('')}</div>`);
  else if(skill.instruction_available!==false)html+=`<p class="tiny">${skills.length>1?esc(skill.title_ru||skill.name)+': ':''}Дополнительных документов в пакете нет. Основной документ — инструкция навыка.</p>`;
  if(skill.documentation_issues?.length)html+=section('Материалы требуют внимания',`<ul class="documentation-issues">${skill.documentation_issues.map(issue=>`<li>${esc(issue.id)}: ${esc(issue.reason)}</li>`).join('')}</ul>`);
 }
 const seenLinks=new Set();const links=[[profile.documentation,'Документация сервиса'],[profile.connection_documentation,'Подключение'],[profile.website,'Сайт поставщика']].filter(([url])=>url&&!seenLinks.has(url)&&seenLinks.add(url)).map(([url,label])=>link(url,label)).filter(Boolean);
 const authorLinks=skills.map(skill=>{const author=skill.author_profile||{};const heading=skills.length>1?skill.title_ru||skill.name:author.name!==profile.provider?author.name||'Автор не указан':'';return `<div class="documentation-provider">${heading?`<strong>${esc(heading)}</strong>`:''}${skills.length>1&&author.name?`<p class="tiny">Автор: ${esc(author.name)}</p>`:''}<div class="links">${(author.links||[]).map(l=>link(l.url,l.label)).join('')}</div>${skill.repository_evidence?`<p class="tiny">${esc(skill.repository_evidence)}</p>`:''}</div>`;}).join('');
 html+=section('Поставщик и документация',textList(profile.provider)+`<div class="links">${[...new Set(links)].join('')}</div>`+authorLinks);
 if(profile.connection_steps?.length)html+=section('Как подключается',textList(profile.connection_method)+textList(profile.connection_requirements)+textList(profile.connection_steps));
 return html;
}

import {renderGuide} from './guide.js';
import {invocationFor,callsFor,promptMenuHTML,bindPromptMenus} from './invocations.js';
import {singleControl,switchHTML,headerControlHTML,controlGuidance,controlContextNote,tileControlsHTML,unavailableControlsHTML} from './activation-ui.js';
import {renderBacklog} from './backlog.js';
import {renderSettings,selectSettingsProject} from './settings.js';
import {contentKey,pollDelay,preserveView} from './state.js';
import {reconciliationHTML as renderReconciliation} from './reconciliation.js';
import {skillManagementHTML,bindSkillFileTools,removedSkillsHTML} from './skill-actions.js';
import {markdown} from './markdown.js';
import {showDialog as openNativeDialog,closeDialog as closeNativeDialog,clearDialogMotion} from './dialog.js';
import {typeNames,scopeNames,origins,componentsFor,presence,status,visible,values,reorderIds,metadataFor,sortRows} from './model.js';
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths={settings:'M4 7h16M4 17h16M8 4v6M16 14v6',all:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',skill:'M5 4h14v16H5zM8 8h8M8 12h8M8 16h5',mcp:'M8 8v8m8-8v8M8 12h8M4 5h4v3H4zM16 5h4v3h-4zM4 16h4v3H4zM16 16h4v3h-4z',plugin:'M4 4h6v4a3 3 0 0 0 6 0V4h4v16h-4v-4a3 3 0 0 0-6 0v4H4z',app:'M4 4h16v16H4zM4 9h16M8 4v5',program:'M3 4h18v13H3zM8 21h8m-4-4v4',star:'m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z',notes:'M5 3h14v18H5zM8 7h8M8 11h8M8 15h5',history:'M4 5v5h5M4 10a8 8 0 1 1 .3 5M12 7v5l3 2',globe:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18',folder:'M3 6h7l2 2h9v12H3z',refresh:'M20 7v5h-5M4 17v-5h5M20 12a8 8 0 0 0-14-5M4 12a8 8 0 0 0 14 5',info:'M12 11v6m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',filter:'M4 6h16M7 12h10M10 18h4',close:'m6 6 12 12M18 6 6 18',chevron:'m9 5 7 7-7 7',copy:'M9 9h11v11H9zM5 15H3V3h12v2'};
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]||paths.skill}"/></svg>`;
const plural=(n,one,few,many)=>`${n} ${n%10===1&&n%100!==11?one:n%10>=2&&n%10<=4&&(n%100<12||n%100>14)?few:many}`;
const date=(s,time=false)=>{if(!s)return 'Дата не указана';const d=new Date(s);return Number.isNaN(+d)?s:d.toLocaleString('ru-RU',time?{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}:{day:'numeric',month:'long',year:'numeric'});};
const bills={free:'Бесплатно',included:'Включено в подписку',paid:'Платные операции',mixed:'Есть платные возможности',unknown:'Расходы не уточнены'};
let data, selected=null, detailTab='overview', page='all', poll, toastTimer, sortMode=localStorage.getItem('catalog-sort')||'custom';
let filters={project:'',types:[],scope:'',enabled:'',presence:'installed',direction:'',origin:'',tag:'',billing:'',query:'',favorite:localStorage.getItem('catalog-favorites-only')==='true'};
let pendingRender=false,lastInput='pointer',dragged=null,orderSaving=false;
let switching=false,stateEpoch=0;
document.addEventListener('keydown',()=>lastInput='keyboard',true);
document.addEventListener('pointerdown',()=>lastInput='pointer',true);
const token=$('meta[name=catalog-token]').content;
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'X-Catalog-Token':token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(body?90000:15000)});const j=await r.json();if(!r.ok)throw Error(j.error||'Не удалось выполнить действие.');return j;}
function toast(message){$('#toast').textContent=message;$('#toast').style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').style.display='none',4200);}
function safeURL(s){try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}}
const link=(url,label)=>safeURL(url)?`<a href="${esc(safeURL(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`:'';
function parseRoute(){const route=new URLSearchParams(location.hash.slice(1));const id=route.get('project');page=route.get('page')||'all';if(id){page='project';filters.project=id;}else filters.project='';if(page==='settings')selectSettingsProject(route.get('settings_project'));if(page==='favorites')rememberFavoriteFilter(true);if(!['all','project','favorites','found','notes','history','wishes','guide','settings'].includes(page))page='all';}
function rememberFavoriteFilter(enabled){
 filters.favorite=enabled;
 try{localStorage.setItem('catalog-favorites-only',String(enabled));}catch{/* Keep the choice for navigation when browser storage is unavailable. */}
 if(!enabled&&page==='favorites'){page='all';history.replaceState(null,'','#all');}
}
function project(){return data.projects.find(p=>p.id===filters.project)||null;}
function routeFor(id){return id?'#project='+encodeURIComponent(id):'#all';}
function sidebar(){
 const count=data.addons.filter(a=>presence(componentsFor(a))==='installed').length;
 const nav=(href,label,ico,active,count='')=>`<a href="${href}" class="nav-link ${active?'active':''}" ${active?'aria-current="page"':''}>${icon(ico)}<span>${esc(label)}</span>${count!==''?`<span class="count">${count}</span>`:''}</a>`;
 $('#navigation').innerHTML=nav('#all','Весь Codex','all',page==='all',count)+nav('#page=favorites','Избранное','star',page==='favorites')+'<p class="nav-heading">Проекты</p>'+data.projects.map(p=>`<a class="nav-link ${filters.project===p.id?'active':''}" href="${routeFor(p.id)}" ${filters.project===p.id?'aria-current="page"':''} title="${esc(p.file_path||p.path)}"><span class="project-dot" aria-hidden="true"></span><span class="project-label">${esc(p.name)}${p.available===false?'<small class="project-missing">Папка недоступна</small>':''}</span></a>`).join('')+nav('#page=found','Найденные навыки','skill',page==='found')+'<p class="nav-heading">Мои записи</p>'+nav('#page=notes','Заметки','notes',page==='notes')+nav('#page=history','История','history',page==='history')+nav('#page=wishes','Пожелания','folder',page==='wishes')+'<p class="nav-heading">О каталоге</p>'+nav('#page=settings','Настройки','settings',page==='settings')+nav('#page=guide','Что здесь показано','info',page==='guide');
 $('#legacy-link').href=data.legacy_url;
 $('#legacy-link').onclick=async e=>{e.preventDefault();const tab=window.open('about:blank','_blank');if(tab)tab.opener=null;try{const result=await api('legacy',{});if(tab)tab.location.href=result.url;else location.href=result.url;}catch(error){tab?.close();toast(error.message);}};
 $('#crumb').textContent=project()?.name||({all:'Весь Codex',favorites:'Избранное',notes:'Заметки',history:'История',wishes:'Пожелания',guide:'Что здесь показано',settings:'Настройки',found:'Найденные навыки'}[page]);
 $('#footer').innerHTML=`<span>Сверка ${esc(date(data.updated_at,true))} · снимок ${esc(data.version)}</span><button class="quiet" id="coverage">Откуда эти сведения ${icon('info')}</button>`;
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
 const scopeLabel=p?`<div class="project-actions"><button type="button" class="scope-label secondary" id="project-open" aria-label="Открыть папку проекта в Проводнике" title="${esc(p.file_path||p.path)}">${icon('folder')} Открыть папку</button><button class="quiet" id="project-folder-settings">Настройки проекта</button></div>`:`<span class="scope-label">${icon('globe').replace('<svg','<svg width="14" height="14"')} Этот компьютер</span>`;
 $('#main').innerHTML=heading(p?p.name:page==='favorites'?'Избранное':'Весь Codex',p?'Общие надстройки Codex и собственные надстройки этого проекта.':page==='favorites'?'То, что вы хотите держать под рукой.':'Все ваши надстройки: что установлено, из чего состоит и где работает.',scopeLabel)+(p?.available===false?'<div class="soft-note amber" role="status"><strong>Папка недоступна</strong><p>Проект зарегистрирован в Codex, но его папка не найдена или недоступна при последней сверке.</p><code>'+esc(p.path)+'</code></div>':'')+
 `<div class="overview-line"><span><span class="status-dot"></span><strong>${plural(installed,'надстройка установлена','надстройки установлены','надстроек установлено')}</strong></span><span>Глобально <strong>${global}</strong></span><span>Локально <strong>${local}</strong></span></div><section class="filters" aria-label="Фильтры надстроек"><div class="type-toolbar"><div class="type-row" role="group" aria-label="Состав надстройки"><button class="type-chip" data-type="all" aria-pressed="${!filters.types.length}">${icon('all')}Все типы</button>${Object.entries(typeNames).map(([k,v])=>`<button class="type-chip" data-type="${k}" aria-pressed="${filters.types.includes(k)}">${icon(k)}${v}<span data-count="${k}"></span></button>`).join('')}</div><button type="button" id="favorite-filter" class="type-chip favorite-filter" aria-pressed="${filters.favorite}" title="Только избранные надстройки в выбранном разделе">${icon('star')}Избранное<span id="favorite-count" aria-hidden="true"></span></button></div><div class="filter-row">${select('scope','Область',[['','Глобальные и локальные'],['global','Только глобальные'],['local','Только локальные'],['unknown','Не уточнена']])}${select('enabled','Включение',[['','Любое'],['on','Включено'],['off','Отключено'],['unknown','Не проверено']])}${select('direction','Назначение',[['','Все направления'],...(data.directions||[]).map(d=>[d.id,d.title])])}<label class="search">Найти по названию<input id="search" type="search" value="${esc(filters.query)}" placeholder="Например, Blender" aria-label="Найти по названию"></label><button id="more-filters" class="quiet filter-more" aria-expanded="false">${icon('filter')}Ещё фильтры</button></div><div class="filter-row advanced" id="advanced">${select('origin','Происхождение',[['','Любое'],...Object.entries(origins)])}${select('billing','Расходы',[['','Любые'],...Object.entries(bills)])}${select('tag','Тег',[['','Любой'],...[...new Set(data.addons.flatMap(a=>metadataFor(a,data.overlay.items[a.id]).tags))].sort().map(t=>[t,t])])}</div><p class="filter-hint" id="type-hint" hidden></p></section><div id="active-filters" class="active-filters"></div><div class="results-line"><span id="result-count" tabindex="-1" role="status" aria-live="polite"></span><div class="result-actions"><select id="sort" aria-label="Порядок карточек"><option value="custom">Мой порядок</option><option value="composition">Сначала составные</option><option value="name">По названию</option><option value="newest">Сначала новые</option><option value="oldest">Сначала старые</option></select><button class="quiet" id="reset-filters">Сбросить фильтры</button></div></div><div class="grid" id="grid"></div>`;
 $('#sort').value=sortMode; $('#sort').onchange=e=>{sortMode=e.target.value;localStorage.setItem('catalog-sort',sortMode);paintGrid();};
 $('#search').oninput=e=>{filters.query=e.target.value;paintGrid();};
 document.querySelectorAll('[data-filter]').forEach(el=>el.onchange=()=>{filters[el.dataset.filter]=el.value;paintGrid();});
 document.querySelectorAll('[data-multi-filter]').forEach(el=>el.onchange=()=>{const field=el.dataset.multiFilter;filters[field]=[...document.querySelectorAll(`[data-multi-filter="${field}"]:checked`)].map(x=>x.value);updateMulti(field);paintGrid();});
 document.querySelectorAll('[data-multi-clear]').forEach(b=>b.onclick=()=>{const f=b.dataset.multiClear;filters[f]=[];document.querySelectorAll(`[data-multi-filter="${f}"]`).forEach(x=>x.checked=false);updateMulti(f);paintGrid();});
 document.querySelectorAll('.multi').forEach(el=>el.addEventListener('toggle',()=>{if(el.open){positionMulti(el);document.querySelectorAll('.multi').forEach(other=>{if(other!==el)other.open=false;});}}));
 document.querySelectorAll('[data-type]').forEach(btn=>btn.onclick=()=>{const k=btn.dataset.type;filters.types=k==='all'?[]:filters.types.includes(k)?filters.types.filter(x=>x!==k):[...filters.types,k];paintGrid();});
 $('#favorite-filter').onclick=()=>{const previousPage=page;rememberFavoriteFilter(!filters.favorite);if(page!==previousPage){renderPage();$('#favorite-filter').focus();}else paintGrid();};
 $('#more-filters').onclick=()=>{const v=$('#advanced').classList.toggle('open');$('#more-filters').setAttribute('aria-expanded',v);};
 $('#reset-filters').onclick=()=>{rememberFavoriteFilter(false);filters={project:filters.project,favorite:false,types:[],scope:'',enabled:'',presence:'installed',direction:'',origin:'',tag:'',billing:'',query:''};renderPage();$('#reset-filters').focus();};
 if(p){$('#project-open').onclick=e=>openProjectFolder(p,e.currentTarget);$('#project-folder-settings').onclick=()=>{location.hash='page=settings&settings_project='+encodeURIComponent(p.id);};}
 paintGrid();
}
function scopeKind(parts){const scopes=[...new Set(parts.filter(c=>c.installed||c.file_found).map(c=>c.scope))];return scopes.includes('global')&&scopes.includes('local')?'mixed':scopes[0]||'unconfirmed';}
function scopeLabel(parts){const kind=scopeKind(parts);return kind==='mixed'?'Глобально + локально':scopeNames[kind]||'Не подтверждено';}
function scopeHTML(parts){const kind=scopeKind(parts);return `<span class="scope scope-${esc(kind)}">${icon(kind==='local'||kind==='mixed'?'folder':'globe')}${esc(scopeLabel(parts))}</span>`;}
function primaryKind(parts){return ['plugin','program','mcp','app','skill'].find(kind=>parts.some(c=>c.kind===kind))||'info';}
function composition(parts){return Object.keys(typeNames).filter(k=>parts.some(p=>p.kind===k)).map(k=>{const n=parts.filter(p=>p.kind===k).length;return `<span class="badge ${k}">${({skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение',program:'Программа'})[k]}${n>1?' ×'+n:''}${parts.filter(p=>p.kind===k).every(p=>!p.installed)?' · не подтверждено':parts.some(p=>p.kind===k&&!p.installed)?' · есть непроверенные':''}</span>`;}).join('');}
function paintGrid(){
 const expanded=[...document.querySelectorAll('#grid .tile-control-menu[open]')].map(el=>el.closest('[data-addon]').dataset.addon);
 const rows=sortRows(visible(data,filters),sortMode,data.overlay.orders?.[filters.project||'all']||[]);

 $('#result-count').innerHTML=`<strong>${plural(rows.length,'надстройка','надстройки','надстроек')}</strong>${filters.types.length||filters.favorite?' по выбранным условиям':''}`;
 document.querySelectorAll('[data-type]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.type==='all'?!filters.types.length:filters.types.includes(b.dataset.type)));
 $('#favorite-filter').setAttribute('aria-pressed',filters.favorite);
 $('#favorite-count').textContent=visible(data,{...filters,favorite:true}).length;
 const candidates=visible(data,filters,true);
 document.querySelectorAll('[data-count]').forEach(el=>el.textContent=candidates.filter(r=>r.matching.some(c=>c.kind===el.dataset.count)).length);
 $('#type-hint').hidden=filters.types.length<2;$('#type-hint').textContent='Показаны надстройки, в составе которых есть все выбранные типы. Остальные фильтры действуют одновременно.';
 const labels={scope:'Область',enabled:'Включение',presence:'Наличие',direction:'Назначение',origin:'Происхождение',tag:'Тег',billing:'Расходы'};
 $('#active-filters').innerHTML=Object.entries(labels).filter(([k])=>values(filters[k]).length&&!(k==='presence'&&filters[k]==='installed')).map(([k,v])=>`<button class="clear-chip" data-clear="${k}">${v}: ${esc($(`[data-filter="${k}"] option:checked`)?.textContent||$(`#value-${k}`)?.textContent||filters[k])} ×</button>`).join('');
 document.querySelectorAll('[data-clear]').forEach(b=>b.onclick=()=>{filters[b.dataset.clear]=b.dataset.clear==='presence'?'installed':'';inventory();});
 $('#grid').innerHTML=rows.length?rows.map(({addon:a,parts,overlay,presence:found})=>{const s=status(parts),kind=primaryKind(parts);return `<article class="addon" data-addon="${esc(a.id)}"><div class="addon-head"><span class="addon-mark ${kind}">${icon(kind)}</span><button class="addon-name" data-open="${esc(a.id)}">${esc(a.title)}</button></div><button class="favorite" data-favorite="${esc(a.id)}" aria-label="В избранное: ${esc(a.title)}" aria-pressed="${overlay.favorite??a.favorite}">${icon('star')}</button><p class="addon-description">${esc(a.description||'Описание пока не подготовлено. Состав и источники доступны в карточке.')}</p><div class="composition">${composition(parts)||'<span class="badge">Есть описание подключения</span>'}</div><div class="addon-state-line ${s.key}">${esc(s.label)}</div><div class="addon-bottom">${scopeHTML(parts)}<span class="state ${found}">${found==='installed'?'Установлено':found==='unconfirmed'?'Не подтверждено':'Можно добавить'}</span></div>${['newest','oldest'].includes(sortMode)?`<p class="added-date tiny">Добавлено: ${a.added_at?esc(date(a.added_at)): 'дата не сохранена'}</p>`:''}${tileControlsHTML(parts,esc,filters.project||'all')}${sortMode==='custom'?`<div class="order-controls"><button class="drag-handle quiet" draggable="true" data-drag="${esc(a.id)}" aria-label="Переставить: ${esc(a.title)}" title="Перетащите на другую плитку, чтобы поменять их местами; Alt + стрелка вверх / вниз — обмен с соседней">⠿ <span>Переставить</span></button><button class="quiet order-up" data-move="${esc(a.id)}" data-step="-1" aria-label="Выше: ${esc(a.title)}">↑</button><button class="quiet order-down" data-move="${esc(a.id)}" data-step="1" aria-label="Ниже: ${esc(a.title)}">↓</button></div>`:''}${parts.some(c=>c.restriction)?'<div class="restriction">Есть ограничение по проекту</div>':''}</article>`;}).join(''):`<div class="empty"><h2>Нет надстроек с таким сочетанием</h2><p>Уберите одно условие или сбросьте фильтры.</p><button class="secondary" id="empty-reset">Сбросить фильтры</button></div>`;
 document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openAddon(b.dataset.open));
 document.querySelectorAll('[data-favorite]').forEach(b=>b.onclick=()=>save(b.dataset.favorite,'favorite',{value:b.getAttribute('aria-pressed')!=='true'}).catch(e=>toast(e.message)));
 document.querySelectorAll('#grid .tile-control-menu').forEach(el=>{
  if(expanded.includes(el.closest('[data-addon]').dataset.addon))el.open=true;
  el.addEventListener('toggle',()=>{if(el.isConnected&&el.open)document.querySelectorAll('#grid .tile-control-menu').forEach(other=>{if(other!==el)other.open=false;});});
 });
 bindControls();bindOrdering(rows);
 if($('#empty-reset'))$('#empty-reset').onclick=()=>$('#reset-filters').click();
}
function section(title,body){return body?`<section class="section"><h2>${esc(title)}</h2>${body}</section>`:'';}
function textList(value){if(!value||Array.isArray(value)&&!value.length)return '';return Array.isArray(value)?`<ul>${value.map(v=>`<li>${esc(typeof v==='string'?v:JSON.stringify(v))}</li>`).join('')}</ul>`:`<p>${esc(value)}</p>`;}
function componentHTML(c,showControl=true){
 const projectName=c.contextId?data.projects.find(p=>p.id===c.contextId)?.name:c.project_path?data.projects.find(p=>p.path===c.project_path)?.name:'';
 const installed=c.installed?'Установлено':c.file_found?'Файл найден · доступность Codex не подтверждена':'Наличие не подтверждено';
 const enabled=c.enabled===true?'Включено':c.enabled===false?'Отключено':'Включение не проверено';
 const details=[c.version?`<p>Версия: ${esc(c.version)}</p>`:'',c.fingerprint?`<p>Отпечаток версии: <code>${esc(c.fingerprint)}</code></p>`:''].join('');
 const seen=(c.observations||[]).filter(o=>o.kind==='session');
 return `<article class="component"><div class="component-header"><strong>${esc(c.title||c.name)}</strong><span class="badge ${c.kind}">${({skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение',program:'Программа'})[c.kind]||esc(c.kind)}</span></div><div class="component-status"><span class="scope scope-${esc(c.scope||'unknown')}">${esc(scopeNames[c.scope]||'Не уточнено')}${projectName?' · '+esc(projectName):''}</span><span>· ${installed}</span><span>· ${enabled}</span></div>${c.connection?.reason?`<p>${esc(c.connection.label)}. ${esc(c.connection.reason)}</p>`:''}${c.basis?`<p>${esc(c.basis)}</p>`:''}${seen.length?`<p>В метаданных этого чата: ${esc(date(seen.at(-1).at))}. Это свидетельство доступности на указанную дату.</p>`:''}${c.restriction?`<div class="soft-note amber">${esc(c.restriction)}</div>`:''}${c.approval?`<p>Запрос разрешения: ${esc(c.approval==='prompt'?'перед операцией':c.approval==='default'?'по настройкам Codex':c.approval)}.</p>`:''}${c.policy&&c.policy!=='inherit'?`<p>Правило в каталоге: ${esc(({explicit:'только по явной команде',ask:'с подтверждением операции',blocked:'не использовать'})[c.policy]||c.policy)}. Это заметка о применении, не изменение разрешений.</p>`:''}${showControl?controlHTML(c,true)+skillManagementHTML([c],esc):''}${details?`<details><summary>Версия и проверка</summary>${details}${c.checked_at?`<p>Сверено ${esc(date(c.checked_at,true))}</p>`:''}</details>`:''}</article>`;
}
function controlHTML(c,explain=false){
 const control=c.control;
 if(!control?.supported)return explain?`<p class="tiny control-unavailable">${esc(control?.message||'Переключатель для этой части пока недоступен.')}</p>`:'';
 const name=c.title||c.name;
 return `<div class="control-row"><div><strong>${esc(name)}</strong><small>Глобально · на этом компьютере</small></div>${switchHTML(c,esc,filters.project||'all')}</div>${c.state_note?`<p class="tiny">${esc(c.state_note)}</p>`:c.enabled!==null&&c.enabled!==control.enabled?`<p class="tiny">В этом проекте: ${c.enabled?'включено':'отключено'}. Его действующая настройка отличается от общей.</p>`:''}`;
}
function controlsHTML(parts){
 if(singleControl(parts))return '';
 const available=parts.filter(c=>c.control?.supported);
 return section('Использовать в Codex',`${parts.map(c=>`<div class="component-management">${controlHTML(c)}${!c.control?.supported&&c.file_actions?.remove?`<strong>${esc(c.title||c.name)}</strong>`:''}${skillManagementHTML([c],esc)}</div>`).join('')}${unavailableControlsHTML(parts,esc)}${available.length?'<p class="tiny">Изменение сохраняется в настройках на этом компьютере и в истории. Перезапустите Codex, чтобы открытые чаты получили новое состояние. Настройки отдельных проектов могут иметь приоритет.</p>':''}<p class="control-result" role="status"></p>`);
}
function bindControls(){
 document.querySelectorAll('[data-activation]').forEach(button=>{button.disabled=switching;button.onclick=async()=>{
  if(switching){toast('Дождитесь сохранения текущего переключения.');return;}
  const tile=button.closest('[data-addon]'),id=tile?.dataset.addon||selected,tab=detailTab,view=location.hash,hadFocus=document.activeElement===button;
  const componentId=button.dataset.activation,context=button.dataset.context;
  const addon=data.addons.find(a=>a.id===id);
  if(!addon)return;
  const component=componentsFor(addon,project()).find(c=>c.id===button.dataset.activation&&(c.contextId||filters.project||'all')===button.dataset.context);
  if(!component?.control?.supported)return;
  switching=true;stateEpoch++;
  const buttons=[...document.querySelectorAll('[data-activation]')];buttons.forEach(b=>b.disabled=true);button.setAttribute('aria-busy','true');
  const target=tile?.querySelector('.tile-control-result')||$('#details .control-result');if(target)target.textContent='Сохраняем в Codex…';
  let message='';
  try{
   const response=await api('activation',{id,component_id:component.id,context,enabled:!component.control.enabled,revision:component.control.revision});
   data=response.state;
   message=response.result.unchanged?'Настройка уже имеет это значение.':response.result.warning||'Сохранено в Codex и истории. Требуется перезапуск Codex.';
  }catch(error){message=error.message;try{data=await api('state');}catch{/* Keep the last confirmed state; no optimistic switch. */}}
  finally{
   const restoreFocus=hadFocus&&view===location.hash&&(document.activeElement===button||document.activeElement===document.body);
   switching=false;stateEpoch++;clearTimeout(poll);
   if(['all','project','favorites'].includes(page))paintGrid();
   if($('#details').open&&selected===id){openAddon(id,tab);const result=$('#details .control-result');if(result)result.textContent=message;}
   const newTile=[...document.querySelectorAll('#grid [data-addon]')].find(el=>el.dataset.addon===id);
   if(tile&&view===location.hash){const result=newTile?.querySelector('.tile-control-result');if(result)result.textContent=message;}
   if(restoreFocus){
    const host=tile?newTile:$('#details');
    const next=[...host?.querySelectorAll('[data-activation]')||[]].find(b=>b.dataset.activation===componentId&&b.dataset.context===context);
    (next||newTile?.querySelector('[data-open]')||$('#result-count'))?.focus({preventScroll:true});
   }
   buttons.forEach(b=>{b.disabled=false;b.removeAttribute('aria-busy');});toast(message);
  }
 };});
}
function overviewHTML(a,parts){
 const profile=a.profile||{},overlay=data.overlay.items[a.id]||{};
 const meta=metadataFor(a,overlay);
 const purposes=meta.directions.map(id=>data.directions.find(d=>d.id===id)?.title||id);
 const property=(field,title,value)=>`<button type="button" class="info-cell editable-property" data-property="${field}" aria-label="Настроить ${title.toLocaleLowerCase()}" aria-haspopup="dialog"><small>${title}</small><span class="property-pencil" aria-hidden="true">✎</span><span>${esc(value)}</span></button>`;
 let html=singleControl(parts)?`<section class="overview-management"><div class="overview-control"><h2>Использовать в Codex</h2>${switchHTML(parts[0],esc,filters.project||'all')}</div>${skillManagementHTML(parts,esc,false)}<p class="tiny">${esc(controlGuidance)}</p><p class="control-result" role="status"></p></section>`:parts.length>1?section('Использовать в Codex','<button type="button" class="secondary" data-open-composition>Включение частей '+icon('chevron')+'</button>'):controlsHTML(parts);
 html+=`<div class="info-grid"><div class="info-cell readonly-property"><small>Область</small>${scopeHTML(parts)}<span class="tiny">Определяется установкой в Codex</span></div>${property('origins','Происхождение',meta.origins.map(v=>origins[v]||v).join(', ')||'Источник не уточнён')}${property('directions','Назначение',purposes.join(', ')||'Пока не указано')}${property('billings','Расходы',meta.billings.map(v=>bills[v]||v).join(', ')||'Расходы не уточнены')}</div>`;
 html+=`<button type="button" class="info-cell editable-property tags-property" data-property="tags" aria-label="Редактировать теги" aria-haspopup="dialog"><small>Теги</small><span class="property-pencil" aria-hidden="true">✎</span><span class="tag-list">${meta.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')||'<span class="tiny">Добавить теги</span>'}</span></button><p class="tiny added-date">Добавлено в каталог: ${a.added_at?esc(date(a.added_at,true)):'дата не была сохранена'}</p>`;
 if(profile.capabilities?.length)html+=section('Что умеет',textList(profile.capabilities));

 for(const s of a.skills){
  html+=section(a.skills.length>1?s.title_ru||s.name:'Как помогает',textList(s.helps||s.description_ru||s.description_original||s.description));
  html+=(s.capability_groups||[]).map(g=>section(g.title,textList(g.text))).join('');
  html+=section('Что получится',textList(s.output))+section('Когда выбирать',textList(s.choose_when))+section('Что подготовить',textList(s.prepare))+section('Зависимости',textList(s.dependencies))+section('Автор и версия',textList(s.author_profile?.name)+textList(s.declared_version?'Версия '+s.declared_version:''));
  if(s.capability_limits)html+=`<div class="soft-note amber">${esc(s.capability_limits)}</div>`;
 }
 if(parts.some(c=>c.restriction))html+=`<div class="soft-note amber">${esc(parts.find(c=>c.restriction).restriction)}</div>`;
 html+=section('Данные, ограничения и расходы',textList(profile.data_access)+textList(profile.limitations)+textList(profile.pricing));
 if(a.bindings.length)html+=section('Записанные связи с проектами',a.bindings.map(b=>`<p><strong>${esc(b.project_name)}</strong>: ${esc(b.purpose)}<br><span class="tiny">${esc(({recommended:'Рекомендация',codex_use:'Записано использование в Codex',runtime:'Записана интеграция'})[b.role]||b.role)}${b.evidence?' · '+esc(b.evidence):''}</span></p>`).join(''));
 const related=a.related.map(id=>data.addons.find(x=>x.id===id)).filter(Boolean);
 if(related.length)html+=section('Полезно вместе',`<p>Связанные возможности; они не входят автоматически в состав этой надстройки.</p><div class="links">${related.map(r=>`<button class="secondary" data-related="${esc(r.id)}">${esc(r.title)}</button>`).join('')}</div>`);
 return html;
}
function sourcesHTML(a,parts){const p=a.profile||{};return sourceEvidenceHTML(parts)+section('Основание описания',textList(p.evidence))+a.skills.map(s=>section(s.title_ru||s.name,`<p>Автор: ${esc(s.author_profile?.name||'Не указан')}</p>${textList(s.origin_evidence)}<p class="tiny">Русская инструкция: ${esc(s.instruction_localization?.message||'Нет сведений')}</p>`)).join('')+section('Как подключается',textList(p.connection_method)+textList(p.connection_requirements)+textList(p.connection_steps)+textList(p.reviewed_at?'Описание проверено: '+date(p.reviewed_at):''))+section('Границы проверки',`<p>Области и включение проверяются по настройкам. Успешное применение к задаче показывается только при наличии отдельной записи.</p><p>Каталог показывает настройки Codex. Подтверждённые личные навыки и пользовательские настройки MCP, плагинов и приложений можно включать и отключать в карточке. Пути и открытие папок находятся только в «Источниках». Подключение и удаление навыка — рядом с управлением «Использовать в Codex»; перед удалением каталог показывает точный файл и запрашивает подтверждение. Доступ к аккаунтам и разрешения операций здесь не меняются.</p>`);}
function notesHTML(a){const item=data.overlay.items[a.id]||{};return section('Мои заметки',`<div class="notes-list">${a.notes.map(n=>`<div class="note">${esc(n)}<small>Из прежнего каталога</small></div>`).join('')}${(item.notes||[]).map(n=>`<div class="note">${esc(n.text)}<small>${esc(date(n.at,true))} · новый вариант</small></div>`).join('')}${!a.notes.length&&!item.notes?.length?'<p>Здесь можно сохранить своё наблюдение об этой надстройке.</p>':''}</div>${noteForm('note','Новая заметка')}`)+section('Проверенный опыт',a.skills.flatMap(s=>(s.verified_experience||[]).map(e=>`<div class="note">${esc(e.task||'Применение')}<p>${esc(e.result||'')}</p><small>${esc(e.date||'')} ${esc(e.limitations||'')}</small></div>`)).join('')||'<p>Записанного опыта пока нет. Это не означает, что надстройку никогда не использовали.</p>')+section('Опыт других версий',textList(a.skills.flatMap(s=>(s.historical_experience||[]).map(e=>(e.task||'Применение')+' — '+(e.result||'')))))+section('История этой надстройки',eventsHTML(a));}
function noteForm(action,label){return `<form class="note-form" data-note-action="${action}"><label for="note-text">${label}</label><textarea id="note-text" required maxlength="20000" placeholder="Ваш текст…"></textarea><div class="actions"><span class="tiny">Личная запись сохранится на этом компьютере.</span><button class="primary" type="submit">Сохранить ${action==='wish'?'пожелание':'заметку'}</button></div><p class="error" role="alert"></p></form>`;}
function openAddon(id,tab='overview'){
 const a=data.addons.find(a=>a.id===id);if(!a)return;selected=id;const parts=componentsFor(a,project()).filter(c=>page!=='found'||c.kind==='skill'&&c.file_found&&!c.installed);
 if(tab==='composition'&&parts.length<2)tab='documentation';detailTab=tab;
 $('#detail-content').innerHTML=`<header class="drawer-head"><span>${esc(project()?.name||'Весь Codex')} / Надстройка</span><div class="drawer-top-actions"><button class="icon-button" id="close-detail" aria-label="Закрыть карточку">${icon('close')}</button></div></header><div class="drawer-body"><div class="drawer-title"><span class="addon-mark ${primaryKind(parts)}">${icon(primaryKind(parts))}</span><div><h1 id="detail-title">${esc(a.title)}</h1><div class="composition">${composition(parts)}</div></div></div><p class="drawer-intro">${esc(a.description)}</p><div class="drawer-tabs" role="tablist" aria-label="Раздел карточки">${[['overview','Обзор'],['documentation','Документация'],...(parts.length>1?[['composition','Состав · '+parts.length]]:[]),['notes','Заметки и опыт'],['sources','Источники']].map(([k,v])=>`<button type="button" role="tab" id="detail-tab-${k}" data-tab="${k}" aria-controls="drawer-panel" aria-selected="${detailTab===k}" tabindex="${detailTab===k?0:-1}">${v}</button>`).join('')}</div><div id="drawer-panel" role="tabpanel" aria-labelledby="detail-tab-${detailTab}">${detailTab==='overview'?overviewHTML(a,parts):detailTab==='documentation'?documentationHTML(a,parts):detailTab==='composition'?`<p class="tiny">Каждая часть имеет свою область и состояние. Типы в фильтрах соответствуют этому составу.</p>${parts.map(c=>componentHTML(c,!singleControl(parts))).join('')||'<p>Действующая установка не обнаружена. Это справочная карточка.</p>'}<p class="control-result" role="status"></p>`:detailTab==='notes'?notesHTML(a):sourcesHTML(a,parts)}</div></div>`;
 $('#close-detail').onclick=()=>closeDialog($('#details'));
 bindSkillFileTools({data,addon:a,parts,api,esc,readPanel,toast,closeReader:()=>closeDialog($('#reader')),acceptState:next=>{data=next;renderPage();if($('#details').open)openAddon(id,tab);}});
 document.querySelectorAll('[data-tab]').forEach(b=>{
  const activate=name=>{openAddon(id,name);document.querySelector(`[data-tab="${name}"]`)?.focus({preventScroll:true});};
  b.onclick=()=>activate(b.dataset.tab);
  b.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')],index=tabs.indexOf(b);const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;activate(tabs[next].dataset.tab);};
 });
 document.querySelectorAll('[data-related]').forEach(b=>b.onclick=()=>openAddon(b.dataset.related));
 bindInstructionActions();
 bindControls();

 bindNotes(id);
 bindMetadata(id);bindSourceFolders(id);
 const manage=$('[data-open-composition]');if(manage)manage.onclick=()=>{openAddon(id,'composition');$('#details [data-tab=composition]')?.focus();};
 if(!$('#details').open)showDialog($('#details'));
}
function bindNotes(id){document.querySelectorAll('[data-note-action]').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('[type=submit]');b.disabled=true;try{await save(id,form.dataset.noteAction,{text:form.querySelector('textarea').value});}catch(error){form.querySelector('.error').textContent=error.message;}finally{b.disabled=false;}});}
async function save(id,action,extra,revision=data.overlay.revision){data.overlay=await api('annotate',{id,action,revision,...extra});toast('Сохранено.');if(['all','project','favorites'].includes(page))paintGrid();else renderPage();if($('#details').open)openAddon(selected,detailTab);}
const eventNames={preview_order:'Изменён порядок карточек',preview_project:'Добавлен проект',preview_note:'Добавлена заметка',preview_favorite:'Изменено избранное',preview_tags:'Изменены теги',preview_metadata:'Изменены свойства надстройки',preview_wish:'Записано пожелание',inventory_refreshed:'Сверены установки',skill_note_added:'Добавлена заметка к навыку',note_added:'Добавлена заметка',search_started:'Начат поиск навыков',search_completed:'Сохранена подборка',operation_started:'Начата операция',operation_completed:'Завершена операция',skill_activation_changed:'Изменено включение навыка',skill_activation_unconfirmed:'Переключение навыка не подтверждено',extension_activation_changed:'Изменено включение надстройки',extension_activation_unconfirmed:'Переключение надстройки не подтверждено',resource_catalog_changed:'Изменена карточка ресурса',organization_changed:'Изменена классификация',directions_changed:'Изменены направления',project_catalog_changed:'Изменены сведения проекта',manager_favorite_changed:'Изменено избранное'};
eventNames.wish_created='Записано пожелание';eventNames.wish_updated='Обновлено пожелание';
eventNames.preview_project_folder='Изменена папка проекта';
eventNames.preview_skill_sources='Изменены папки поиска навыков';
eventNames.preview_skill_remove='Удалена инструкция навыка';
eventNames.preview_skill_restore='Восстановлена инструкция навыка';
eventNames.preview_skill_install='Установлены файлы навыка';
function eventSummary(e){const x=e.data||{};if(e.kind==='preview_metadata'){const a=e.value.after;return `Происхождение: ${a.origins.map(v=>origins[v]||v).join(', ')||'не указано'}; назначение: ${a.directions.map(id=>data.directions.find(d=>d.id===id)?.title||id).join(', ')||'не указано'}; расходы: ${a.billings.map(v=>bills[v]||v).join(', ')||'не указаны'}`;}if(e.kind==='preview_tags'&&typeof e.value==='object')return `Теги: ${e.value.before.join(', ')||'нет'} → ${e.value.after.join(', ')||'нет'}`;if(['preview_skill_remove','preview_skill_install','preview_skill_restore'].includes(e.kind))return `${e.value.name}: ${e.value.source}${e.value.destination?' → '+e.value.destination:''}${e.value.backup?' · резервная копия: '+e.value.backup:''}`;if(e.kind==='preview_skill_sources'){const {before=[],after=[],action}=e.value;const row=after.find(r=>!before.some(b=>JSON.stringify(b)===JSON.stringify(r)))||before.find(r=>!after.some(a=>a.id===r.id));return (({save:'Сохранена папка поиска',remove:'Папка убрана из поиска; файлы сохранены',toggle:row?.enabled?'Поиск в папке включён':'Поиск в папке выключен'})[action]||'Изменены источники')+(row?' — '+row.path:'');}if(e.kind==='preview_project_folder')return `${e.value.project}: ${e.value.before} → ${e.value.after}`;if(e.kind.includes('activation'))return `${x.component_name||x.skill_name||x.resource_name||''}: ${x.before_enabled?'включено':'отключено'} → ${x.actual_enabled===true?'включено':x.actual_enabled===false?'отключено':'не подтверждено'}${x.restart_required?' · требуется перезапуск Codex':''}`;return x.query||x.title||x.wish_id||x.detail||x.reason||x.text||x.skill_name||x.resource_name||x.target||x.task||e.value||'';}
function eventsHTML(a=null){const ids=a?new Set([a.id,...a.skills.map(s=>s.id),...a.components.map(c=>c.id)]):null;const rows=[...data.events.map(e=>({...e,legacy:true})),...data.overlay.events].filter(e=>!ids||ids.has(e.extension_id)||Object.values(e.data||{}).some(v=>typeof v==='string'&&ids.has(v))).sort((a,b)=>String(b.at||b.timestamp).localeCompare(String(a.at||a.timestamp))).slice(0,a?30:150);return rows.length?rows.map(e=>`<article class="event"><time>${esc(date(e.at||e.timestamp,true))}</time><div><strong>${esc(eventNames[e.kind]||'Запись каталога')}</strong><p>${esc(typeof eventSummary(e)==='string'?eventSummary(e):JSON.stringify(eventSummary(e)))}</p><span class="tiny">${e.kind.includes('activation')?'Настройки Codex':e.kind.startsWith('wish_')?'Бэклог':e.legacy?'Общая история':'Каталог'}</span><details><summary>Подробности записи</summary><div class="document">${esc(JSON.stringify(e.data||{value:e.value},null,2))}</div></details></div></article>`).join(''):'<p class="tiny">Записей пока нет.</p>';}
function documentsHTML(ids){return `<div class="doc-links">${data.documents.filter(d=>ids.includes(d.id)).map(d=>`<button class="secondary" data-doc="${d.id}">${icon('notes')}${esc(d.title)}</button>`).join('')}</div>`;}
function bindDocuments(){document.querySelectorAll('[data-doc]').forEach(b=>b.onclick=()=>{const d=data.documents.find(d=>d.id===b.dataset.doc);readPanel(d.title,`<p class="path">${esc(d.path)}</p>${markdown(d.text)}`);});}
function renderFound(){
 const selectedProject=data.projects.find(p=>p.id===filters.project)||null;
 const findings=data.addons.flatMap(a=>componentsFor(a,selectedProject).filter(c=>c.kind==='skill'&&c.file_found&&!c.installed).map(c=>({a,c})));
 $('#main').innerHTML=heading('Найденные навыки','Файлы на этом компьютере, доступность которых Codex не подтвердил. Их подключение пока не подтверждено.')+`<label for="found-project">Область<select id="found-project"><option value="">Все проекты и общие папки</option>${data.projects.map(p=>`<option value="${esc(p.id)}" ${p.id===filters.project?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><p class="tiny">Новые папки поиска добавляются в «Настройках». Поиск выполняется только по кнопке «Сверить с Codex».</p><div class="grid">${findings.map(({a,c})=>`<article class="addon"><h2><button class="quiet" data-found-open="${esc(a.id)}">${esc(c.title||c.name)}</button></h2><p>${esc(a.description)}</p><code class="source-path">${esc(c.path)}</code><p class="tiny">${esc(c.basis||'Файл найден; Codex не подтвердил доступность.')}</p><button class="secondary" data-found-open="${esc(a.id)}">${c.managed_package?'Инструкция и сведения о пакете':'Инструкция и подключение'}</button></article>`).join('')||'<p>Неподключённых навыков в проверенных источниках не найдено.</p>'}</div>`;
 $('#found-project').onchange=e=>{filters.project=e.target.value;renderFound();};
 document.querySelectorAll('[data-found-open]').forEach(b=>b.onclick=()=>openAddon(b.dataset.foundOpen));
}
function renderPage(){
 sidebar();
 if(page==='found'){renderFound();return;}
 if(page==='settings'){renderSettings($('#main'),{data,esc,icon,date,change:changeSkillSources,openFolderSettings:projectFolderSettings,openFolder:openProjectFolder,openAddon,revealSkill:async file=>{try{await api('reveal-skill',{id:file.addon_id,component_id:file.component_id});}catch(error){toast(error.message);}},copyPath:async path=>{try{await navigator.clipboard.writeText(path);toast('Путь скопирован.');}catch{toast('Не удалось скопировать путь.');}},refresh:()=>$('#refresh').click()});return;}
 if(['all','project','favorites'].includes(page)){inventory();return;}
 if(page==='history'){
  $('#main').innerHTML=heading('История','Что менялось, что искали и что уже проверяли.')+documentsHTML(['journal'])+removedSkillsHTML(data.removed_skills,esc)+'<div class="timeline">'+eventsHTML()+'</div>';
  bindSkillFileTools({data,addon:null,parts:[],api,esc,readPanel,toast,closeReader:()=>closeDialog($('#reader')),acceptState:next=>{data=next;renderPage();}});
 }
 if(page==='wishes')renderBacklog($('#main'),{api,esc,markdown,readPanel,toast,acceptEvents:events=>{data.events=events;}});
 if(page==='notes'){
  $('#main').innerHTML=heading('Заметки','Ваши наблюдения о надстройках и общие записи.')+documentsHTML(['inbox'])+`<div class="notebook">${noteForm('note','Общая заметка')}${Object.entries(data.overlay.items).flatMap(([id,v])=>(v.notes||[]).map(n=>`<article class="page-note"><h2>${esc(data.addons.find(a=>a.id===id)?.title||'Общая запись')}</h2><div class="document">${esc(n.text)}</div><p class="tiny">${esc(date(n.at,true))} · Новый вариант</p></article>`)).join('')}${data.addons.filter(a=>a.notes.length).map(a=>`<article class="page-note"><h2><button class="quiet" data-note-open="${esc(a.id)}">${esc(a.title)}</button></h2>${a.notes.map(n=>`<p class="document">${esc(n)}</p>`).join('')}<p class="tiny">Из прежнего каталога</p></article>`).join('')}</div>`;
  bindNotes('workspace');document.querySelectorAll('[data-note-open]').forEach(b=>b.onclick=()=>openAddon(b.dataset.noteOpen,'notes'));
 }
 if(page==='guide')renderGuide($('#main'),{data,esc,icon,coverage});
 bindDocuments();if($('#guide-coverage'))$('#guide-coverage').onclick=coverage;
}
function readPanel(title,html){$('#reader-title').textContent=title;$('#reader-actions').innerHTML='';$('#reader-content').innerHTML=html;if(!$('#reader').open)showDialog($('#reader'));$('#reader').scrollTop=0;}
function coverage(){readPanel('Откуда эти сведения',`<p>Последняя сверка: ${esc(date(data.updated_at,true))}.</p><ul class="coverage-list"><li><strong>Файлы навыков</strong><p>Личные папки, системные инструкции, зарегистрированные проекты и пакеты расширений.</p></li><li><strong>Настройки и приложения Codex</strong><p>Отдельно прочитаны для каждой папки проекта. Проверка сервисных операций не запускалась.</p></li><li><strong>Метаданные этого чата</strong><p>${esc(data.coverage.session_label||'Не переданы')}. ${esc(date(data.coverage.session_at))}.</p></li></ul>${reconciliationHTML()}${textList(data.coverage.limits)}${Object.entries(data.coverage.views).filter(([id,v])=>v.warning).map(([id,v])=>`<div class="soft-note amber">${esc(data.projects.find(p=>p.id===id)?.name||'Весь Codex')}: ${esc(v.warning)}</div>`).join('')}<p class="tiny">Кеш пакета сам по себе не считается установленной и включённой надстройкой.</p>`);}
async function load(){
 clearTimeout(poll);if(switching)return;const epoch=stateEpoch;
 try{
  const next=await api('state');if(epoch!==stateEpoch)return;
  $('#refresh').disabled=next.job.state==='running';
  $('#refresh').innerHTML=icon('refresh')+(next.job.state==='running'?'Сверяем…':'Сверить с Codex');
  if(next.loading){
   if(next.job.state!=='running'){document.dispatchEvent(new Event('catalog-ready'));document.querySelector('.loader')?.remove();document.querySelector('.loading h1').textContent='Сверьте каталог с Codex';}
   $('#loading-status').textContent=next.job.state==='running'?'Читаем настройки и папки проектов…':next.job.state==='error'?next.job.message:'Нажмите «Сверить с Codex», чтобы получить список этой машины.';
   const delay=pollDelay(next);if(delay)poll=setTimeout(load,delay);return;
  }
  const first=!data,changed=!data||contentKey(data)!==contentKey(next);data=next;
  if(first)parseRoute();
  if(filters.project&&!data.projects.some(p=>p.id===filters.project)){filters.project='';page='all';history.replaceState(null,'','#all');}
  if(first){renderPage();document.dispatchEvent(new Event('catalog-ready'));}
  else if(changed){
   if(!document.querySelector('dialog[open]')&&!document.querySelector('.multi[open]')&&!['TEXTAREA','INPUT'].includes(document.activeElement?.tagName)&&![...document.querySelectorAll('.note-form input,.note-form textarea')].some(el=>el.value!==el.defaultValue))preserveView($('#main'),renderPage);
   else pendingRender=true;
  }
  if($('#settings-check'))$('#settings-check').disabled=data.job.state==='running';
  if($('#settings-status'))$('#settings-status').textContent=data.job.state==='running'?'Сверяем папки и доступность в Codex…':data.job.state==='error'?data.job.message:data.source_settings?.pending?'Настройки сохранены. Нажмите «Сверить с Codex».':'Последняя проверка: '+date(data.source_settings?.checked_at,true);
  $('#footer span').textContent='Сверка '+date(data.updated_at,true)+' · снимок '+data.version;
  if(data.coverage.project_registry_warning)toast(data.coverage.project_registry_warning);
  const delay=pollDelay(data);if(delay)poll=setTimeout(load,delay);
  else if(data.job.state==='error')toast(data.job.message);
 }catch(e){$('#loading-status')?$('#loading-status').textContent=e.message:toast(e.message);}
}
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
function instructionActions(parts,addon){
 const skills=[...new Map(parts.filter(c=>c.kind==='skill'&&c.skill_id).map(c=>[c.skill_id,c])).values()];
 if(!skills.length)return callsFor(addon,parts).length?`<section class="section"><h2>Применение</h2><button type="button" class="secondary" data-open-calls>${icon('copy')}Скопировать вызов</button></section>`:'';
 return skills.map(c=>{const skill=addon.skills.find(s=>s.id===c.skill_id)||{},readable=skill.instruction_available!==false;return `<section class="section documentation-actions"><h2>${esc(skills.length>1?skill.title_ru||c.title||c.name:'Инструкция и вызов')}</h2><div class="links">${readable?`<button type="button" class="primary" data-instruction="${esc(c.skill_id)}">${icon('notes')}Прочитать инструкцию</button>`:'<p class="tiny">Инструкция этой установки недоступна. Выполните сверку с Codex.</p>'}<button type="button" class="secondary" data-open-calls="${esc(c.skill_id)}">${icon('copy')}Скопировать вызов</button></div></section>`;}).join('');
}

async function copyInvocation(id){
 const name=data.addons.flatMap(a=>a.skills||[]).find(s=>s.id===id)?.name||id;
 try{await navigator.clipboard.writeText(invocationFor(data.addons,id));toast('Вызов навыка скопирован.');}
 catch{readPanel('Вызов навыка · '+name,`<p>Скопируйте текст вручную:</p><textarea readonly aria-label="Вызов навыка">${esc(invocationFor(data.addons,id))}</textarea>`);$('#reader-actions').innerHTML='';}
}
function bindInstructionActions(){
 document.querySelectorAll('[data-open-calls]').forEach(button=>button.onclick=()=>{
  const addon=data.addons.find(a=>a.id===selected),parts=componentsFor(addon,project());
  const rows=callsFor(addon,parts,button.dataset.openCalls?{skillId:button.dataset.openCalls}:{});
  readPanel('Скопировать вызов',`<div class="prompt-dialog">${promptMenuHTML(rows,esc)}</div>`);
  const menu=$('#reader-content .invocation-menu');if(menu)menu.open=true;
  bindPromptMenus($('#reader-content'),{copy:value=>navigator.clipboard.writeText(value),toast});
 });
 document.querySelectorAll('[data-skill-document]').forEach(b=>b.onclick=async()=>{
  try{
   const i=await api('instruction?id='+encodeURIComponent(b.dataset.skillDocument)),doc=i.documents?.[b.dataset.document];
   if(!doc)throw new Error('Документ недоступен. Выполните сверку с Codex.');
   readPanel(doc.title,`<p class="tiny"><span class="path">${esc(doc.path)}</span></p>${markdown(doc.text,{documents:i.documents,currentDocument:b.dataset.document})}`);
   $('#reader-actions').innerHTML='';
   bindDocumentNavigation(i);
  }catch(e){toast(e.message);}
 });
 document.querySelectorAll('[data-instruction]').forEach(b=>b.onclick=async()=>{
  try{
   const id=b.dataset.instruction,i=await api('instruction?id='+encodeURIComponent(id));
   const skill=data.addons.flatMap(a=>componentsFor(a,project())).find(c=>c.skill_id===id);
   const show=original=>{
    readPanel('Инструкция · '+(skill?.title||skill?.name||''),`<p class="tiny">${!original&&i.translation?'Русский текст, сверенный с оригиналом':'Оригинал'} · <span class="path">${esc(i.path)}</span></p>${markdown(!original&&i.translation?i.translation:i.text,{documents:i.documents})}`);
    bindDocumentNavigation(i);
    $('#reader-actions').innerHTML=i.translation?`<button class="secondary" id="instruction-language">${original?'Русский текст':'Оригинал'}</button>`:'';
    if($('#instruction-language'))$('#instruction-language').onclick=()=>show(!original);
   };show(false);
  }catch(e){toast(e.message);}
 });
 bindPromptMenus($('#detail-content'),{copy:value=>navigator.clipboard.writeText(value),toast});
}
function bindDocumentNavigation(instruction){
 $('#reader-content').querySelectorAll('[data-document-target]').forEach(button=>button.onclick=()=>{
  const key=button.dataset.documentTarget,doc=instruction.documents?.[key];if(!doc)return;
  readPanel(doc.title,`<p class="tiny"><span class="path">${esc(doc.path)}</span></p>${markdown(doc.text,{documents:instruction.documents,currentDocument:key})}`);
  bindDocumentNavigation(instruction);
 });
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
document.addEventListener('click',e=>document.querySelectorAll('.invocation-menu[open],.multi[open],.tile-control-menu[open]').forEach(d=>{if(!d.closest('.prompt-dialog')&&!d.contains(e.target))d.open=false;}));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const open=[...document.querySelectorAll('.invocation-menu[open],.multi[open],.tile-control-menu[open]')].find(el=>!el.closest('.prompt-dialog')&&(!$('#reader').open||$('#reader').contains(el)));if(open){open.open=false;open.querySelector('summary').focus();e.preventDefault();}}});

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
 const move=(id,step)=>{const visibleIds=rows.map(r=>r.addon.id),index=visibleIds.indexOf(id),target=visibleIds[index+step];if(!target)return;persistOrder(reorderIds(fullOrder(rows),id,target),id);};
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
function reconciliationHTML(){return renderReconciliation(data.coverage.reconciliation,esc);}
function projectFolderSettings(p){
 const manual=p.file_path_source==='user';
 readPanel('Папка проекта · '+p.name,`<p>«Открыть папку» перейдёт сюда в Проводнике. Каталог также проверит здесь локальные навыки.</p><form class="note-form" id="folder-settings-form"><label for="file-folder-path">Папка файлов</label><input id="file-folder-path" required value="${esc(p.file_path||p.path)}" placeholder="C:\\Projects\\MyProject" autocomplete="off" spellcheck="false"><p class="tiny">${manual?'Указана вами. Автоматическое обновление её не заменит.':p.source==='codex'?'Взята из записи проекта Codex. Проверьте, действительно ли здесь ваши файлы.':'Взята из настроек каталога.'}</p><div class="project-actions"><button class="primary" type="submit">Сохранить</button>${manual?`<button class="quiet" type="button" id="reset-file-folder">Вернуть исходную папку</button>`:''}</div><p class="error" role="alert"></p></form><p class="tiny folder-context">Исходная запись проекта Codex остаётся прежней. Сравнивайте её с выбранной папкой; открытый чат автоматически не переносится:<br><code>${esc(p.path)}</code></p>`);
 const form=$('#folder-settings-form');
 const persist=async path=>{
  const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  stateEpoch++;
  try{data=await api('project-folder',{id:p.id,path,revision:data.overlay.revision});await closeDialog($('#reader'));renderPage();toast('Папка сохранена. Нажмите «Сверить с Codex».');}
  catch(error){form.querySelector('.error').textContent=error.message;}
  finally{buttons.forEach(b=>b.disabled=false);}
 };
 form.onsubmit=e=>{e.preventDefault();persist($('#file-folder-path').value);};
 if($('#reset-file-folder'))$('#reset-file-folder').onclick=()=>persist(null);
}
async function openProjectFolder(p,button){
 if(button.disabled)return;
 button.disabled=true;
 try{await api('open-project',{id:p.id});toast('Папка открыта в Проводнике.');}
 catch(error){toast(error.message);}
 finally{button.disabled=false;}
}
function sourceEvidenceHTML(parts){
 if(!parts.length)return '';
 const rows=new Map(),missing=[];
 for(const c of parts){
  const locations=c.source_locations||[];
  if(!locations.length)missing.push(c.title||c.name);
  for(const s of locations){
   let key=s.path.replace(/\\/g,'/').replace(/\/+$/,'');
   if(/^[a-z]:/i.test(key)||key.startsWith('//'))key=key.toLowerCase();
   let row=rows.get(key);
   if(!row){row={source:s,component:c,names:new Set(),labels:new Set(),evidence:new Set()};rows.set(key,row);}
   row.names.add(c.title||c.name);row.labels.add(s.label);
   for(const evidence of c.search_sources||[])row.evidence.add(evidence.title+(evidence.project_name?' · '+evidence.project_name:''));
  }
 }
 const entries=[...rows.values()].map(({source:s,component:c,names,labels,evidence})=>`<div class="source-evidence"><strong>${[...names].map(esc).join(' · ')}</strong><small>${[...labels].map(esc).join(' · ')}</small><code class="source-path">${esc(s.path)}</code><div class="links"><button type="button" class="quiet" data-source-folder="${esc(s.id)}" data-source-component="${esc(c.id)}" data-source-context="${esc(c.contextId||filters.project||'all')}" ${s.available?'':'disabled'}>${icon('folder')}Показать папку в Проводнике</button><button type="button" class="quiet" data-copy-path="${esc(s.path)}">Скопировать путь</button></div>${!s.available?'<p class="tiny">Файл или папка недоступны.</p>':''}${evidence.size?`<p class="tiny">${[...evidence].map(esc).join('; ')}</p>`:''}</div>`).join('');
 return section('Где найдено',entries+(missing.length?`<p class="tiny">Локальный файл или папка не указаны в данных Codex: ${[...new Set(missing)].map(esc).join(', ')}.</p>`:''));
}
function bindSourceFolders(id){
 document.querySelectorAll('[data-source-folder]').forEach(button=>button.onclick=async()=>{
  button.disabled=true;
  try{await api('reveal-source',{id,component_id:button.dataset.sourceComponent,context:button.dataset.sourceContext,source_id:button.dataset.sourceFolder});toast('Папка открыта в Проводнике.');}
  catch(error){toast(error.message);}finally{button.disabled=false;}
 });
}
function metadataEditor(meta,field){
 const settings={origins:['Происхождение',Object.entries(origins)],directions:['Назначение',(data.directions||[]).map(d=>[d.id,d.title])],billings:['Расходы',Object.entries(bills)]};
 const [title,options]=settings[field];
 return `<form id="metadata-form" class="note-form"><p class="tiny">Выберите одно или несколько значений. Ваши правки сохраняются при сверке с Codex.</p><div class="property-options" role="group" aria-label="${title}">${options.map(([value,label])=>`<label><input type="checkbox" value="${esc(value)}" ${meta[field].includes(value)?'checked':''}><span>${esc(label)}</span></label>`).join('')}</div><div class="editor-actions"><button type="button" class="secondary" data-cancel-editor>Отмена</button><button class="primary" type="submit">Сохранить</button></div><p class="error" role="alert"></p></form>`;
}
function bindMetadata(id){
 document.querySelectorAll('[data-property]').forEach(button=>button.onclick=()=>{
  const addon=data.addons.find(a=>a.id===id),meta=metadataFor(addon,data.overlay.items[id]||{}),field=button.dataset.property,revision=data.overlay.revision;
  if(field==='tags'){openTagEditor(id,meta.tags);return;}
  const title={origins:'Происхождение',directions:'Назначение',billings:'Расходы'}[field];
  readPanel(title,metadataEditor(meta,field));const form=$('#metadata-form');
  form.querySelector('[data-cancel-editor]').onclick=()=>closeDialog($('#reader'));
  form.onsubmit=async event=>{event.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;
   try{const payload=Object.fromEntries(['origins','directions','billings'].map(key=>[key,key===field?[...form.querySelectorAll('input:checked')].map(input=>input.value):meta[key]]));await save(id,'metadata',payload,revision);await closeDialog($('#reader'));document.querySelector(`[data-property="${field}"]`)?.focus();}
   catch(error){form.querySelector('.error').textContent=error.message;}finally{submit.disabled=false;}
  };
 });
}
function openTagEditor(id,tags){
 let draft=[...tags];const revision=data.overlay.revision;
 readPanel('Теги',`<form class="note-form" id="tags-form"><p class="tiny">Добавляйте свои теги и удаляйте ненужные. Изменения применяются после сохранения.</p><div class="tag-editor-list"></div><label for="tags-input">Новый тег</label><div class="tag-input-row"><input id="tags-input" maxlength="120" placeholder="Например, исследование"><button type="button" class="secondary" id="add-tag">Добавить</button></div><div class="editor-actions"><button type="button" class="secondary" data-cancel-editor>Отмена</button><button class="primary" type="submit">Сохранить</button></div><p class="error" role="alert"></p></form>`);
 const form=$('#tags-form'),input=$('#tags-input'),error=form.querySelector('.error');
 const render=()=>{form.querySelector('.tag-editor-list').innerHTML=draft.map((tag,index)=>`<span class="tag editable-tag">${esc(tag)}<button type="button" data-remove-tag="${index}" aria-label="Удалить тег ${esc(tag)}">×</button></span>`).join('')||'<p class="tiny">Тегов пока нет</p>';form.querySelectorAll('[data-remove-tag]').forEach(b=>b.onclick=()=>{draft.splice(Number(b.dataset.removeTag),1);render();input.focus();});};
 const add=()=>{const value=input.value.trim();if(!value)return true;if(value.includes(',')||draft.length>=100){error.textContent='Введите один тег без запятой. Допустимо до 100 тегов.';return false;}if(!draft.some(tag=>tag.toLocaleLowerCase()===value.toLocaleLowerCase()))draft.push(value);input.value='';error.textContent='';render();return true;};
 $('#add-tag').onclick=()=>{add();input.focus();};input.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();add();}};
 form.querySelector('[data-cancel-editor]').onclick=()=>closeDialog($('#reader'));
 form.onsubmit=async event=>{event.preventDefault();if(!add())return;const submit=form.querySelector('[type=submit]');submit.disabled=true;try{await save(id,'tags',{text:draft.join(', ')},revision);await closeDialog($('#reader'));document.querySelector('[data-property=tags]')?.focus();}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};
 render();input.focus();
}

async function changeSkillSources(payload){
 stateEpoch++;switching=true;
 try{data=await api('skill-sources',{...payload,revision:data.overlay.revision});renderPage();toast('Настройки сохранены. Нажмите «Сверить с Codex».');}
 finally{switching=false;stateEpoch++;clearTimeout(poll);}
}

load();
