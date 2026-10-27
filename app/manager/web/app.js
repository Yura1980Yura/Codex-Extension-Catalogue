'use strict';
const paths = {
 grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
 book:'<path d="M4 4h12a3 3 0 0 1 3 3v14H6a3 3 0 0 1-3-3V5a1 1 0 0 1 1-1Z"/><path d="M3 17h16M8 4v10"/>',
 history:'<path d="M3 10a9 9 0 1 1 2 8M3 4v6h6m3-4v6l4 2"/>',
 star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/>',
 arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>', plus:'<path d="M12 5v14M5 12h14"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>', refresh:'<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5m-4 8a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
 copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
 pen:'<path d="m15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-4-4L5 15l-1 5Z"/>',
 spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Zm7-1v4m-2-2h4"/>',
 document:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5"/>',
 chart:'<path d="M4 3v17h17M8 15V9m5 6V5m5 10v-4"/>',
 image:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5L4 21"/>',
 code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-14-2 16"/>',
 menu:'<path d="M4 6h16M4 12h16M4 18h16"/>', check:'<path d="m5 12 4 4L19 6"/>',
 link:'<path d="M14 3h7v7m0-7L10 14m0-10H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-5"/>'
};
const icon = name => `<svg aria-hidden="true" viewBox="0 0 24 24">${paths[name] || paths.spark}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const token = document.querySelector('meta[name="catalog-token"]').content;
const content = document.querySelector('#content');
const detailDialog = document.querySelector('#detail-dialog');
const formDialog = document.querySelector('#form-dialog');
document.documentElement.dataset.input='keyboard';
document.addEventListener('pointerdown',()=>{document.documentElement.dataset.input='pointer';},true);
document.addEventListener('keydown',()=>{document.documentElement.dataset.input='keyboard';},true);
const ui = {data:null, page:'skills', query:'', origin:'all', task:'all', installationScope:'all', installationProject:'all', catalogTag:'all', relatedResource:'all', usageProject:'all', favorites:false, notebook:'wishes', history:'actions', historyKind:'all', pendingJob:null, selected:null};
const origins = {builtin:'От OpenAI', personal:'Мои разработки', third_party:'От других авторов', unknown:'Источник не уточнён'};
const wishStates=['Записано','Разбираем','В работе','Проверено','Отложено'];
const labels = {service_catalog_changed:'Изменены сведения сервиса',wish_updated:'Пожелание обновлено',search_requested:'Запрос поиска', search_completed:'Найдены варианты', search_failed:'Поиск завершился с ошибкой', inventory_refreshed:'Каталог обновлён', catalog_installed:'Каталог установлен', operation_started:'Начата операция с навыком', operation_completed:'Завершена операция с навыком', user_note_added:'Заметка к навыку', favorite_changed:'Избранное изменено', document_saved:'Заметка сохранена', wish_created:'Пожелание записано', organization_completed:'Обновлено устройство каталога', literary_migration_started:'Начат перенос литературных навыков', literary_migration_verified:'Проверен литературный комплект', literary_migration_completed:'Литературные навыки перенесены', manager_verified:'Проверен менеджер навыков'};
Object.assign(labels,{skill_application_verified:'Проверено применение навыка',directions_initialized:'Созданы исходные направления',directions_seeded:'Классифицированы новые навыки',direction_created:'Создано направление',direction_renamed:'Направление переименовано',skill_directions_changed:'Изменены направления навыка',skill_origin_changed:'Изменено происхождение навыка',skill_author_changed:'Изменены автор и ссылки'});
Object.assign(labels,{skill_activation_changed:'Изменено использование в Codex',skill_activation_unconfirmed:'Переключение не подтверждено'});
Object.assign(labels,{project_added:'Проект добавлен',project_recommendation_changed:'Рекомендация проекта изменена',project_application_recorded:'Применение в проекте подтверждено пользователем'});
function date(value, full=false) {if (!value) return ''; const d = new Date(value); if (Number.isNaN(d.getTime())) return String(value); return d.toLocaleString('ru-RU', {day:'numeric',month:'short',...(full?{year:'numeric'}:{}),hour:'2-digit',minute:'2-digit'});}
async function api(path, data) {
 const response = await fetch('/api/'+path, {method:data===undefined?'GET':'POST', headers:{'X-Catalog-Token':token, ...(data===undefined?{}:{'Content-Type':'application/json'})}, ...(data===undefined?{}:{body:JSON.stringify(data)})});
 const result = await response.json(); if (!response.ok) {const error = new Error(result.error || 'Действие не завершено. Попробуйте ещё раз.'); error.status=response.status; throw error;} return result;
}
let toastTimer;
function toast(message, error=false) {const el=document.querySelector('#toast');(formDialog.open?formDialog:detailDialog.open?detailDialog:document.body).append(el);el.textContent=message;el.className='toast visible'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),error?10000:4500);}
function showSaved(result, message='Сохранено') {toast(result.warning || message, !!result.warning);}
function guarded(fn) {return async event=>{try {await fn(event);} catch(error) {toast(error.message,true);}};}
function typeFor(card) {const s=(card.name+' '+(card.tasks || []).join(' ')).toLowerCase(); if(/литератур|редактур|писат|editor|reader|novel|dialogue|character|rhythm|critique|scene|psychic/.test(s)) return ['pen','rose']; if(/документ|doc|pdf|sheet|slides|present/.test(s)) return ['document','blue'];if(/image|изображ|дизайн|design|visual|sites/.test(s)) return ['image','violet'];if(/аналит|data|research/.test(s)) return ['chart','amber'];if(/code|разработ|reverse|rea|skill/.test(s)) return ['code',''];return ['spark',''];}
function empty(title,description,action='') {return `<div class="empty-state">${icon('search')}<h2>${esc(title)}</h2><p>${esc(description)}</p>${action}</div>`;}
function heading(title,description,button='') {return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${button}</div>`;}
function nav() {
 const items=[['skills','Мои навыки','grid'],['connections','Ресурсы и подключения','link'],['projects','Проекты','book'],['search','Найти навыки','search'],['notebook','Блокнот','book'],['history','История','history']];
 document.querySelector('#navigation').innerHTML=items.map(([key,title,ico])=>`<button class="nav-item ${ui.page===key?'active':''}" data-page="${key}" ${ui.page===key?'aria-current="page"':''}>${icon(ico)}${title}${key==='skills'?`<span class="nav-count">${ui.data?.skills.length ?? '—'}</span>`:''}</button>`).join('');
 document.querySelectorAll('[data-page]').forEach(button=>button.onclick=()=>navigate(button.dataset.page));
 document.querySelector('#breadcrumb').textContent=items.find(x=>x[0]===ui.page)?.[1] || '';
 document.querySelector('#refresh-button').innerHTML=icon('refresh')+'Обновить каталог';
 document.querySelector('#refresh-button').disabled=!!ui.pendingJob;
 document.querySelector('#last-updated').textContent=ui.data?'Каталог обновлён '+date(ui.data.updated_at,true):'';
}
async function load() {ui.data=await api('state');nav();if(ui.data.recovery_warning)toast(ui.data.recovery_warning,true);}
const sidebar=document.querySelector('#sidebar');
const menuButton=document.querySelector('#menu-button');
const narrowScreen=matchMedia('(max-width:760px)');
function syncSidebar(){sidebar.inert=narrowScreen.matches&&!sidebar.classList.contains('open');menuButton.setAttribute('aria-expanded',String(sidebar.classList.contains('open')));}
function closeSidebar(){const wasOpen=sidebar.classList.contains('open');sidebar.classList.remove('open');document.querySelector('#sidebar-shade').classList.remove('open');syncSidebar();if(wasOpen&&narrowScreen.matches)menuButton.focus();}
narrowScreen.addEventListener('change',syncSidebar);syncSidebar();
function navigate(page) {
 if (page!==ui.page && document.querySelector('#inbox-editor')?.dataset.dirty==='true' && !confirm('В заметке есть несохранённый текст. Перейти без сохранения?')) return;
 ui.page=page;location.hash=page;closeSidebar();render();window.scrollTo({top:0,behavior:'instant'});
}
function render() {nav(); if(ui.page==='skills') renderSkills();else if(ui.page==='projects')renderProjects();else if(ui.page==='connections')renderConnections();else if(ui.page==='search') renderSearch();else if(ui.page==='notebook') renderNotebook();else renderHistory();if(ui.data.pending_save){const notice=document.createElement('div');notice.className='inline-warning';notice.innerHTML='Предыдущее сохранение прервалось. Его текст и квитанция сохранены. <button id="recover-save" class="quiet-button">Завершить сохранение</button>';content.prepend(notice);document.querySelector('#recover-save').onclick=guarded(async()=>{const result=await api('recover',{});await load();render();showSaved(result,'Сохранение завершено');});}}
const installationScopes=[['all','Все области'],['user','Глобальные'],['project','Проектные'],['system','Встроенные'],['plugin','Навыки расширений'],['unknown','Область не уточнена']];
function normalizeInstallationFilter(filter,projects) {
 const scope=installationScopes.some(([id])=>id===filter.installationScope)?filter.installationScope:'all';
 const project=scope==='project'&&projects.some(p=>p.id===filter.installationProject)?filter.installationProject:'all';
 return {installationScope:scope,installationProject:project};
}
function filteredCatalogCards(cards,filter) {
 const words=filter.query.toLowerCase().split(/\s+/).filter(Boolean);
 return cards.filter(card=>(!filter.favorites||card.favorite)&&(filter.origin==='all'||card.origin===filter.origin)&&(filter.task==='all'||(filter.task==='unassigned'?!(card.direction_ids||[]).length:(card.direction_ids||[]).includes(filter.task)))&&
  (filter.installationScope==='all'||(card.installation_filter?.scopes||['unknown']).includes(filter.installationScope))&&
  (filter.installationScope!=='project'||filter.installationProject==='all'||(card.installation_filter?.project_ids||[]).includes(filter.installationProject))&&
  (!filter.catalogTag||filter.catalogTag==='all'||(card.catalog_tags||[]).includes(filter.catalogTag))&&(!filter.relatedResource||filter.relatedResource==='all'||(card.resource_ids||[]).includes(filter.relatedResource))&&(!filter.usageProject||filter.usageProject==='all'||(card.project_ids||[]).includes(filter.usageProject))&&words.every(word=>[...(card.catalog_tags||[]),card.name,card.title_ru,card.helps,card.description,card.author_profile?.name,...(card.tasks||[]),...(card.directions||[]),...(card.notes||[])].join(' ').toLowerCase().includes(word)));
}
function installationFilterControls() {
 return `<div class="installation-filters"><label class="installation-filter"><span>Область установки</span><select id="scope-filter" class="filter-select" aria-label="Область установки">${installationScopes.map(([id,title])=>`<option value="${id}" ${ui.installationScope===id?'selected':''}>${title}</option>`).join('')}</select></label><label class="installation-filter project-filter-wrap" id="project-filter-wrap" hidden><span>Проект установки</span><select id="project-filter" class="filter-select" aria-label="Проект установки"></select></label><p id="scope-filter-help" class="scope-filter-help"></p><p id="project-filter-path" class="project-filter-path" hidden></p></div>`;
}
function paintInstallationFilters() {
 const projects=ui.data.installation_projects||[];
 Object.assign(ui,normalizeInstallationFilter(ui,projects));
 document.querySelector('#scope-filter').value=ui.installationScope;
 const wrap=document.querySelector('#project-filter-wrap'),select=document.querySelector('#project-filter');
 wrap.hidden=ui.installationScope!=='project';
 const nameCounts=new Map();projects.forEach(p=>nameCounts.set(p.name,(nameCounts.get(p.name)||0)+1));
 select.innerHTML='<option value="all">Все проекты</option>'+projects.map(p=>`<option value="${esc(p.id)}">${esc(p.name+(nameCounts.get(p.name)>1?' — '+p.path:''))}</option>`).join('');
 select.value=ui.installationProject;select.disabled=!projects.length;
 const current=projects.find(p=>p.id===ui.installationProject),path=document.querySelector('#project-filter-path');
 path.hidden=!current;path.textContent=current?'Папка проекта: '+current.path:'';
 const help={project:projects.length?'Показываются установки внутри проекта. Рекомендации и результаты работы находятся в разделе «Проекты».':'Проектные установки пока не найдены. Обновите каталог после их добавления.',plugin:'Здесь собраны навыки расширений. Их наличие в каталоге не подтверждает включение в текущем чате.',unknown:'У этих карточек область установки пока не установлена по имеющимся сведениям.'};
 document.querySelector('#scope-filter-help').textContent=help[ui.installationScope]||'Область установки и авторство — разные признаки. Фильтры можно сочетать.';
}
function renderSkills() {
 Object.assign(ui,normalizeInstallationFilter(ui,ui.data.installation_projects||[]));
 const tasks=ui.data.directions; if(ui.task!=='all'&&ui.task!=='unassigned'&&!tasks.some(t=>t.id===ui.task))ui.task='all';
 content.innerHTML=heading('Мои навыки','Ваши инструменты для работы, творчества и исследований.',`<button class="primary-button" id="find-new">${icon('plus')}Найти новые</button>`)+
 `<section class="catalog-tools" aria-label="Поиск и фильтры"><div class="search-row"><label class="search-field">${icon('search')}<input id="skill-search" type="search" aria-label="Поиск навыков" placeholder="Что вы хотите сделать?" value="${esc(ui.query)}"></label><label class="direction-filter"><span>Направление</span><select id="task-filter" class="filter-select" aria-label="Направление"><option value="all">Все направления</option>${tasks.map(t=>`<option value="${esc(t.id)}" ${ui.task===t.id?'selected':''}>${esc(t.title)}</option>`).join('')}<option value="unassigned" ${ui.task==='unassigned'?'selected':''}>Без направления</option></select></label><button class="quiet-button direction-manage" id="manage-directions">Настроить направления</button></div>`+
 installationFilterControls()+skillOrganizationFilters()+`<div class="filter-row">${[['all','Все навыки'],['builtin','От OpenAI'],['third_party','Других авторов'],['personal','Мои разработки'],['unknown','Источник не уточнён']].map(([key,title])=>`<button class="filter-chip ${ui.origin===key?'active':''}" aria-pressed="${ui.origin===key}" data-origin="${key}">${title}</button>`).join('')}<button id="favorites-filter" aria-pressed="${ui.favorites}" class="filter-chip ${ui.favorites?'active':''}">${icon('star')}Избранное</button></div></section><div class="results-toolbar"><span id="result-count" role="status" class="result-count"></span><button id="clear-filters" class="quiet-button" hidden>Сбросить фильтры</button></div><div class="skill-grid" id="skill-grid"></div>`;
 document.querySelector('#find-new').onclick=()=>navigate('search');
 document.querySelector('#clear-filters').onclick=()=>{ui.query='';ui.origin='all';ui.task='all';ui.installationScope='all';ui.installationProject='all';ui.catalogTag='all';ui.relatedResource='all';ui.usageProject='all';ui.favorites=false;renderSkills();document.querySelector('#skill-search').focus();};
 document.querySelectorAll('[data-skill-facet]').forEach(select=>select.onchange=()=>{ui[select.dataset.skillFacet]=select.value;drawCards();});
 document.querySelector('#manage-directions').onclick=openDirections;
 document.querySelector('#skill-search').oninput=event=>{ui.query=event.target.value;drawCards();};
 document.querySelector('#task-filter').onchange=event=>{ui.task=event.target.value;drawCards();};
 document.querySelector('#scope-filter').onchange=event=>{ui.installationScope=event.target.value;ui.installationProject='all';drawCards();};
 document.querySelector('#project-filter').onchange=event=>{ui.installationProject=event.target.value;drawCards();};
 document.querySelectorAll('[data-origin]').forEach(b=>b.onclick=()=>{ui.origin=b.dataset.origin;renderSkills();document.querySelector(`[data-origin="${ui.origin}"]`).focus();});
 document.querySelector('#favorites-filter').onclick=()=>{ui.favorites=!ui.favorites;renderSkills();document.querySelector('#favorites-filter').focus();};drawCards();
}
function drawCards() {
 paintInstallationFilters();
 paintSkillOrganizationFilters();
 const cards=filteredCatalogCards(ui.data.skills,ui);
 document.querySelector('#result-count').textContent=`Показано ${cards.length} из ${ui.data.skills.length}`;
 document.querySelector('#clear-filters').hidden=!(ui.query||ui.origin!=='all'||ui.task!=='all'||ui.favorites||ui.installationScope!=='all'||ui.installationProject!=='all'||ui.catalogTag!=='all'||ui.relatedResource!=='all'||ui.usageProject!=='all');
 document.querySelector('#skill-grid').innerHTML=cards.map(card=>{const [ico,color]=typeFor(card);return `<article class="skill-card"><div class="card-top"><span class="skill-icon ${color}">${icon(ico)}</span><span class="card-status">${card.state!=='present'?'Доступность не подтверждена':card.notes?.length?card.notes.length+' заметок':'В каталоге'}</span><button class="icon-button ${card.favorite?'is-favorite':''}" data-favorite="${esc(card.id)}" aria-label="${card.favorite?'Убрать из избранного':'Добавить в избранное'}: ${esc(card.title_ru||card.name)}" aria-pressed="${card.favorite}">${icon('star')}</button></div><h2><button class="card-open" aria-label="Открыть навык ${esc(card.title_ru||card.name)}" data-skill="${esc(card.id)}">${esc(card.title_ru||card.name)}</button></h2><span class="skill-name">${esc(card.name)}</span><div class="card-author">Автор: ${esc(card.author_profile?.name||'не указан')}</div><p>${esc(card.helps||card.description||'Откройте карточку, чтобы узнать больше.')}</p>${directionTags(card)}<div class="tag-list">${(card.catalog_tags||[]).slice(0,3).map(t=>`<span class="resource-tag">${esc(t)}</span>`).join('')}</div><div class="card-bottom"><span class="origin-badge">${esc(origins[card.origin]||card.origin)}</span><span class="card-arrow" aria-hidden="true">${icon('arrow')}</span></div></article>`;}).join('') || empty(ui.favorites?'В этой подборке нет избранного':'Нет навыков с такими условиями',ui.favorites?'Сбросьте фильтры или отметьте нужный навык звездой.':'Измените запрос или нажмите «Сбросить фильтры».');
 document.querySelectorAll('[data-skill]').forEach(button=>button.onclick=guarded(()=>openSkill(button.dataset.skill)));
 document.querySelectorAll('[data-favorite]').forEach(button=>button.onclick=guarded(async()=>{const card=ui.data.skills.find(c=>c.id===button.dataset.favorite);button.disabled=true;try{const result=await api('favorite',{id:card.id,enabled:!card.favorite});await load();drawCards();const restored=[...document.querySelectorAll('[data-favorite]')].find(b=>b.dataset.favorite===card.id);(restored||document.querySelector('#favorites-filter')).focus();showSaved(result,card.favorite?'Убрано из избранного':'Добавлено в избранное');}finally{button.disabled=false;}}));
}

function directionTags(card) {
 return `<div class="tag-list direction-tags">${(card.directions||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')||'<span class="muted">Без направления</span>'}</div>`;
}
function capabilities(card) {
 if(!card.capability_groups?.length)return '';
 return `<section class="detail-section capability-section"><h2>Что умеет</h2>${card.capability_groups.map(g=>`<div class="capability-group"><h3>${esc(g.title)}</h3><p>${esc(g.text)}</p></div>`).join('')}<p class="small-note">${esc(card.capability_limits||'')}</p></section>`;
}
function directionFormHeader(title) {
 return `<div class="form-header"><h2>${esc(title)}</h2><button class="icon-button" data-close-form aria-label="Закрыть">${icon('close')}</button></div><p id="direction-error" class="inline-warning" role="alert" hidden></p>`;
}
function directionBusy(value) {formDialog.dataset.directionSaving=String(value);formDialog.querySelectorAll('input,textarea,select,button').forEach(control=>control.disabled=value);if(value)document.querySelector('#direction-error').hidden=true;}
function directionError(error, form) {const message=document.querySelector('#direction-error');message.textContent=error.message;message.hidden=false;form.after(message);message.scrollIntoView({block:'nearest'});}
function directionDrafts(exclude) {return Object.fromEntries([...formDialog.querySelectorAll('[data-direction-dirty="true"]')].filter(f=>f!==exclude).map(f=>[f.dataset.directionId||"create",f.querySelector("input").value]));}
function openDirections(drafts={}) {
 const revision=ui.data.directions_revision;
 document.querySelector('#form-content').innerHTML=directionFormHeader('Настроить направления')+`<p class="editor-help">Направления объединяют навыки по задачам. Переименование сохраняет все назначения.</p><div class="direction-list">${ui.data.directions.map(d=>`<form class="direction-rename" data-direction-id="${esc(d.id)}"><label>Название направления<input class="text-input" aria-label="Название направления: ${esc(d.title)}" value="${esc(d.title)}" maxlength="80"></label><button class="secondary-button" type="submit">Сохранить название</button></form>`).join('')}</div><form id="direction-create"><h3>Своё направление</h3><label for="new-direction-title">Название нового направления</label><input class="text-input" id="new-direction-title" maxlength="80" placeholder="Например, мои исследования"><button class="primary-button" type="submit">Создать направление</button></form><button class="secondary-button" id="reload-directions">Загрузить свежий список</button>`;
 document.querySelector('[data-close-form]').onclick=requestFormClose;
 document.querySelectorAll('.direction-rename,#direction-create').forEach(form=>{
  const draft=drafts[form.dataset.directionId||"create"];if(draft!==undefined){form.querySelector("input").value=draft;form.dataset.directionDirty="true";}
  form.oninput=()=>form.dataset.directionDirty='true';
  form.onsubmit=guarded(async event=>{event.preventDefault();directionBusy(true);try{const drafts=directionDrafts(form);const created=form.id==='direction-create';const saved=await api('directions',{action:created?'create':'rename',revision,title:form.querySelector('input').value,direction_id:form.dataset.directionId});await load();renderSkills();openDirections(drafts);showSaved(saved,created?'Направление создано':'Название сохранено');}catch(error){directionError(error,form);}finally{directionBusy(false);}});
 });
 document.querySelector('#reload-directions').onclick=guarded(async()=>{if(document.querySelector('[data-direction-dirty="true"]')&&!confirm('Загрузить свежий список и заменить несохранённый ввод?'))return;await load();openDirections();});
 if(!formDialog.open)formDialog.showModal();
}
function openDirectionAssignment(card, draft=null) {
 const selected=draft||card.direction_ids||[];
 document.querySelector('#form-content').innerHTML=directionFormHeader('Направления навыка')+`<p>${esc(card.title_ru||card.name)}</p><p class="editor-help">Отметьте одну или несколько тем. Можно снять все отметки — навык останется без направления.</p><form id="direction-assignment"><div class="direction-options">${card.available_directions.map(d=>`<label><input type="checkbox" value="${esc(d.id)}" ${selected.includes(d.id)?'checked':''}><span>${esc(d.title)}</span></label>`).join('')}</div><button class="primary-button" type="submit">Сохранить направления</button></form><button class="secondary-button" id="reload-assignment">Обновить список, сохранив мой выбор</button>`;
 document.querySelector('[data-close-form]').onclick=requestFormClose;
 const form=document.querySelector('#direction-assignment');
 form.onchange=()=>form.dataset.directionDirty='true';
 const chosen=()=>[...form.querySelectorAll('input:checked')].map(input=>input.value);
 form.onsubmit=guarded(async event=>{event.preventDefault();directionBusy(true);try{const saved=await api('directions',{action:'assign',revision:card.directions_revision,skill_id:card.id,ids:chosen()});await load();ui.selected=await api('skill?id='+encodeURIComponent(card.id));document.querySelector('#skill-directions-current').innerHTML=directionTags(ui.selected);formDialog.close();if(ui.page==='skills')renderSkills();showSaved(saved,'Направления навыка сохранены');}catch(error){directionError(error,form);}finally{directionBusy(false);}});
 document.querySelector('#reload-assignment').onclick=guarded(async()=>{const draft=chosen();const fresh=await api('skill?id='+encodeURIComponent(card.id));openDirectionAssignment(fresh,draft);document.querySelector('#direction-assignment').dataset.directionDirty='true';});
 if(!formDialog.open)formDialog.showModal();
}
function openOriginEditor(card, draft=null) {
 const selected=draft??card.origin;
 document.querySelector('#form-content').innerHTML=directionFormHeader('Изменить происхождение')+`<p>${esc(card.title_ru||card.name)}</p><p class="editor-help">Выберите, к чьим разработкам относится навык. Выбор сохранится при обновлении каталога. Доступность навыка в проектах останется прежней.</p><form id="origin-assignment"><div class="direction-options" role="radiogroup" aria-label="Чьи разработки">${[['personal','Мои разработки'],['third_party','Других авторов'],['unknown','Источник не уточнён'],['builtin','От OpenAI']].map(([id,title])=>`<label><input type="radio" name="skill-origin" value="${id}" ${selected===id?'checked':''}><span>${title}</span></label>`).join('')}</div><button class="primary-button" type="submit">Сохранить происхождение</button></form><button class="secondary-button" id="reload-origin">Обновить сведения, сохранив мой выбор</button>`;
 document.querySelector('[data-close-form]').onclick=requestFormClose;
 const form=document.querySelector('#origin-assignment');
 const chosen=()=>form.querySelector('input:checked')?.value;
 form.onchange=()=>form.dataset.directionDirty='true';
 form.onsubmit=guarded(async event=>{event.preventDefault();directionBusy(true);try{const saved=await api('origin',{id:card.id,origin:chosen(),revision:card.origin_revision});await load();ui.selected=await api('skill?id='+encodeURIComponent(card.id));document.querySelector('#skill-origin-current').textContent=origins[ui.selected.origin];document.querySelector('#skill-origin-title').textContent=origins[ui.selected.origin];formDialog.close();if(ui.page==='skills')renderSkills();showSaved(saved,'Происхождение сохранено: '+origins[ui.selected.origin]);document.querySelector('#edit-skill-origin').focus();}catch(error){directionError(error,form);}finally{directionBusy(false);}});
 document.querySelector('#reload-origin').onclick=guarded(async()=>{const draft=chosen();directionBusy(true);try{const fresh=await api('skill?id='+encodeURIComponent(card.id));openOriginEditor(fresh,draft);document.querySelector('#origin-assignment').dataset.directionDirty='true';}catch(error){directionError(error,form);}finally{directionBusy(false);}});
 if(!formDialog.open)formDialog.showModal();
}
function authorURL(value) {
 try {if(/\s|[<>\\]/.test(value))return '';const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&u.hostname&&!u.username&&!u.password?u.href:'';}catch{return '';}
}
function authorSummary(card) {
 const profile=card.author_profile||{name:'',links:[]};
 const links=(profile.links||[]).filter(link=>authorURL(link.url));
 return `<p class="author-name">${esc(profile.name||'Автор не указан')}</p>${links.length?`<ul class="author-links">${links.map(link=>`<li><a href="${esc(authorURL(link.url))}" target="_blank" rel="noopener noreferrer">${esc(link.label)} ${icon('link')}<span class="sr-only"> (откроется в новой вкладке)</span></a><span class="author-domain">${esc(new URL(authorURL(link.url)).hostname)}</span></li>`).join('')}</ul>`:'<p class="small-note">Ссылки пока не добавлены.</p>'}`;
}
function openAuthorEditor(card, draft) {
 const profile=draft||card.author_profile||{name:'',links:[]};
 document.querySelector('#form-content').innerHTML=directionFormHeader('Автор и ссылки')+`<p class="editor-help">Укажите имя человека, команды или компании. Это отдельные сведения: группа происхождения останется прежней.</p><form id="author-form"><label for="author-name">Имя автора<input class="text-input" id="author-name" value="${esc(profile.name)}" maxlength="160" placeholder="Например, имя автора или название команды"></label><h3>Ссылки</h3><p class="editor-help">Сайт, страница на GitHub или другой ресурс автора. Можно добавить до 8 ссылок.</p><div id="author-link-rows"></div><button class="secondary-button" id="add-author-link" type="button">${icon('plus')}Добавить ссылку</button><div class="form-actions"><button class="secondary-button" data-close-form type="button">Отмена</button><button class="primary-button" type="submit">Сохранить автора и ссылки</button></div></form><button class="quiet-button" id="reload-author">Обновить сведения, сохранив мой ввод</button>`;
 const form=document.querySelector('#author-form');let rowId=0;
 formDialog.querySelectorAll('[data-close-form]').forEach(button=>button.onclick=requestFormClose);
 function addLink(link={label:'',url:''},focus=false) {
  const rows=document.querySelector('#author-link-rows');if(rows.children.length>=8){toast('Можно сохранить до 8 ссылок.');return;}
  const id=++rowId;
  rows.insertAdjacentHTML('beforeend',`<fieldset class="author-link-row"><legend>Ссылка</legend><label for="author-label-${id}">Название ссылки<input class="text-input" id="author-label-${id}" data-author-label value="${esc(link.label)}" maxlength="80" placeholder="Например, GitHub" required></label><label for="author-url-${id}">Адрес страницы<input class="text-input" id="author-url-${id}" data-author-url value="${esc(link.url)}" type="url" maxlength="2048" placeholder="https://…" required></label><button class="quiet-button" type="button" data-remove-author-link>Удалить ссылку</button></fieldset>`);
  const row=rows.lastElementChild;
  row.querySelector('[data-remove-author-link]').onclick=()=>{row.remove();form.dataset.directionDirty='true';document.querySelector('#add-author-link').focus();};
  if(focus)row.querySelector('input').focus();
 }
 (profile.links||[]).forEach(link=>addLink(link));
 const readProfile=()=>({name:document.querySelector('#author-name').value,links:[...form.querySelectorAll('.author-link-row')].map(row=>({label:row.querySelector('[data-author-label]').value,url:row.querySelector('[data-author-url]').value}))});
 form.oninput=()=>form.dataset.directionDirty='true';
 if(draft)form.dataset.directionDirty='true';
 document.querySelector('#add-author-link').onclick=()=>{addLink(undefined,true);form.dataset.directionDirty='true';};
 form.onsubmit=guarded(async event=>{
  event.preventDefault();directionBusy(true);
  try {
   const saved=await api('author',{id:card.id,profile:readProfile(),revision:card.author_revision});
   ui.selected.author_profile=saved.author_profile;ui.selected.author_revision=saved.revision;
   document.querySelector('#skill-author-current').innerHTML=authorSummary(ui.selected);
   directionBusy(false);formDialog.close();showSaved(saved,'Автор и ссылки сохранены');document.querySelector('#edit-skill-author').focus();
   try{await load();if(ui.page==='skills')renderSkills();}catch(error){toast('Автор сохранён. Не удалось обновить список: '+error.message,true);}
  } catch(error){directionError(error,form);} finally{if(form.isConnected)directionBusy(false);}
 });
 document.querySelector('#reload-author').onclick=guarded(async()=>{
  const current=readProfile();directionBusy(true);
  try{const fresh=await api('skill?id='+encodeURIComponent(card.id));openAuthorEditor(fresh,current);}
  catch(error){directionError(error,form);}finally{directionBusy(false);}
 });
 if(!formDialog.open)formDialog.showModal();
}

function installationSummary(card) {
 const info=card.installation;
 if(!info)return '<section class="installation-panel"><h2>Где доступен навык</h2><p>Сведения об установке пока не получены. Перезапустите менеджер и откройте карточку повторно.</p></section>';
 const entries=(info.entries||[]).map(entry=>`<article class="installation-item"><h3>${esc(entry.title)}</h3>${entry.project_name?`<p class="installation-project">Проект: <strong>${esc(entry.project_name)}</strong></p>`:''}<p>${esc(entry.description)}</p>${entry.project_path||entry.installation_path?`<details class="installation-paths"><summary>Показать место установки</summary>${entry.project_path?`<p>Папка проекта<br><code>${esc(entry.project_path)}</code></p>`:''}${entry.installation_path?`<p>Папка навыка<br><code>${esc(entry.installation_path)}</code></p>`:''}</details>`:''}</article>`).join('');
 return `<section class="installation-panel" aria-label="Где доступен навык"><h2>Где доступен навык</h2>${entries}${info.note?`<p class="installation-note">${esc(info.note)}</p>`:''}</section>`;
}

function mountActivation(card) {
 const control=card.activation;
 if(!control)return;
 const panel=document.createElement('section');panel.className='activation-panel';
 panel.innerHTML=`<div class="activation-row"><div><h2 id="activation-label">Использовать в Codex</h2><p id="activation-status" role="status"></p></div><button type="button" class="skill-switch" id="skill-activation" role="switch" aria-labelledby="activation-label" aria-describedby="activation-help"><span></span></button></div><p class="small-note" id="activation-help"></p>`;
 document.querySelector('.detail-actions').after(panel);
 const button=panel.querySelector('button'),status=panel.querySelector('#activation-status'),help=panel.querySelector('#activation-help');
 const paint=()=>{const a=ui.selected.activation;button.disabled=!a.supported;button.setAttribute('aria-checked',String(a.enabled===true));status.textContent=a.supported?(a.enabled?'Включено в настройках':'Отключено в настройках'):'Недоступно для этого навыка';help.textContent=a.message;document.querySelector('#copy-call').disabled=!ui.selected.application_allowed;if(ui.selected.application_allowed)document.querySelector('#availability-warning')?.remove();};
 paint();
 button.onclick=async()=>{
  const previous=ui.selected.activation;button.disabled=true;panel.setAttribute('aria-busy','true');status.textContent='Сохраняем и проверяем в Codex…';
  try {
   const result=await api('activation',{id:card.id,enabled:!previous.enabled,revision:previous.revision});
   const fresh=await api('skill?id='+encodeURIComponent(card.id));
   if(panel.isConnected&&ui.selected?.id===card.id){ui.selected=fresh;paint();status.textContent+=(result.unchanged?'':' · Требуется перезапуск Codex');}
   showSaved(result,result.activation.enabled?'Навык включён. Требуется перезапуск Codex.':'Навык отключён. Заметки сохранены. Требуется перезапуск Codex.');
   if(result.event&&!ui.data.events.some(event=>event.id===result.event.id))ui.data.events.push(result.event);
  } catch(error) {
   try {const fresh=await api('skill?id='+encodeURIComponent(card.id));if(panel.isConnected&&ui.selected?.id===card.id){ui.selected=fresh;paint();}}
   catch {button.disabled=true;status.textContent='Состояние не подтверждено. Откройте карточку повторно.';}
   toast(error.message,true);
  } finally {panel.removeAttribute('aria-busy');if(!button.disabled)button.focus();}
 };
}

async function openSkill(id) {
 const card=await api('skill?id='+encodeURIComponent(id));ui.selected=card;if(card.warning)toast(card.warning,true);
 const [ico,color]=typeFor(card);
 const section=(title,value)=>value?`<section class="detail-section"><h2>${title}</h2><p>${esc(Array.isArray(value)?value.join(', '):value)}</p></section>`:'';
 document.querySelector('#detail-content').innerHTML=`<div class="detail-head"><span>Карточка навыка</span><button class="icon-button" id="close-detail" aria-label="Закрыть карточку">${icon('close')}</button></div><div class="detail-body"><span class="skill-icon ${color}">${icon(ico)}</span><h1 id="skill-title">${esc(card.title_ru||card.name)}</h1><div class="technical-name">${esc(card.name)} · <span id="skill-origin-title">${esc(origins[card.origin])}</span></div><div class="tag-list">${(card.tasks||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>${installationSummary(card)}<div class="detail-actions"><button class="primary-button" id="copy-call">${icon('copy')}Скопировать вызов</button><button class="secondary-button" id="read-instruction">${icon('document')}Инструкция на русском</button></div><section class="detail-section"><h2>Происхождение</h2><p id="skill-origin-current">${esc(origins[card.origin])}</p><button class="secondary-button" id="edit-skill-origin">Изменить происхождение</button></section><section class="detail-section"><h2>Автор и ссылки</h2><div id="skill-author-current">${authorSummary(card)}</div><button class="secondary-button" id="edit-skill-author">Изменить автора и ссылки</button></section><section class="detail-section"><h2>Направления</h2><div id="skill-directions-current">${directionTags(card)}</div><button class="secondary-button" id="edit-skill-directions">Изменить направления</button></section>${capabilities(card)}${section('Чем поможет',card.helps||card.description)}${section('Что получится',card.output)}${section('Когда выбирать',card.choose_when)}${section('Что подготовить',card.prepare)}<section class="detail-section"><h2>Ваши заметки ${card.notes?.length?'· '+card.notes.length:''}</h2>${(card.notes||[]).map(n=>`<div class="note-item">${esc(n)}</div>`).join('')||'<p>Что сработало, чего не хватило, к чему вернуться — сохраняйте здесь.</p>'}<form id="skill-note-form"><textarea class="note-input" id="skill-note" aria-label="Новая заметка к навыку" placeholder="Ваше наблюдение об этом навыке…" maxlength="20000" required></textarea><button class="primary-button" type="submit">Сохранить заметку</button></form><button class="quiet-button" id="wish-from-skill">${icon('plus')}Записать пожелание к навыку</button></section><details><summary>Доступность и проверенный опыт</summary><p>${card.state==='present'?'Найден установленный комплект.':'Доступность при последней сверке не подтверждена.'} ${card.portability==='project_only'?'Навык относится к своему проекту.':''} Наличие в каталоге не гарантирует доступность в текущем чате Codex.</p><p>${card.verified_experience?.length?'Записано применений этой версии: '+card.verified_experience.length+'.':'Подтверждённый опыт этой версии пока не записан.'} ${(card.historical_experience||[]).length?'Сохраняется опыт прежних версий: '+card.historical_experience.length+'.':''}</p>${(card.verified_experience||[]).map(x=>`<div class="experience-item"><strong>${esc(x.task)}</strong><p>${esc(x.result)}</p><p class="small-note">${esc(x.date)}. ${esc(x.limitations||'')}</p></div>`).join('')}</details></div>`;
 document.querySelector('#close-detail').onclick=()=>{if(!document.querySelector('#skill-note').value.trim()||confirm('Заметка ещё не сохранена. Закрыть карточку?'))detailDialog.close();};if(!card.application_allowed){document.querySelector('#copy-call').disabled=true;const warning=document.createElement('div');warning.className='inline-warning';warning.id='availability-warning';warning.textContent=card.availability==='configured_disabled'?'Навык отключён в настройках Codex. Карточка и заметки сохранены.':card.portability==='project_only'?'Этот навык относится к своему проекту. Используйте его в чате этого проекта.':'Текущий источник инструкции не подтверждён. Обновите каталог или проверьте список навыков в чате Codex.';document.querySelector('.detail-actions').before(warning);}
 const language=card.instruction_localization;if(!language?.readable){document.querySelector('#read-instruction').disabled=true;const message=document.createElement('p');message.className='small-note';message.textContent=language?.message||'Русская инструкция пока не подготовлена.';document.querySelector('.detail-actions').after(message);}
 document.querySelector('#edit-skill-directions').onclick=()=>openDirectionAssignment(ui.selected);
 mountActivation(card);
 if(typeof mountSkillResources==='function')mountSkillResources(card);
 document.querySelector('#edit-skill-origin').onclick=()=>openOriginEditor(ui.selected);
 document.querySelector('#edit-skill-author').onclick=()=>openAuthorEditor(ui.selected);
 document.querySelector('#copy-call').onclick=guarded(async()=>{await navigator.clipboard.writeText('$'+card.name);toast('Вызов скопирован. Вставьте его в чат Codex вместе с задачей.');});
 document.querySelector('#read-instruction').onclick=guarded(async()=>{const doc=await api('instruction?id='+encodeURIComponent(id));openDocumentModal(doc.title,(doc.description?doc.description+'\n\n':'')+instructionBody(doc.markdown),doc.notice,doc.heading_aliases);});
 document.querySelector('#wish-from-skill').onclick=()=>openWishForm(card);
 document.querySelector('#skill-note-form').onsubmit=guarded(async event=>{event.preventDefault();const field=document.querySelector('#skill-note');const button=event.target.querySelector('button');button.disabled=true;try{const result=await api('note',{id,text:field.value});await load();await openSkill(id);document.querySelector('#skill-note').focus();showSaved(result,'Заметка сохранена в карточке и истории');}finally{button.disabled=false;}});
 detailDialog.setAttribute('aria-labelledby','skill-title');if(!detailDialog.open)detailDialog.showModal();
}
function inline(text,navigation=null) {
 const source=String(text),plain=value=>esc(value).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');let result='',pending='',i=0;
 const flush=()=>{result+=plain(pending);pending='';};
 while(i<source.length){
  if(source[i]==='`'){
   const run=source.slice(i).match(/^`+/)[0];let end=source.indexOf(run,i+run.length);
   while(end>=0&&(source[end-1]==='`'||source[end+run.length]==='`'))end=source.indexOf(run,end+run.length);
   if(end>=0){flush();result+=`<code>${esc(source.slice(i+run.length,end))}</code>`;i=end+run.length;continue;}
  }
  if(source.startsWith('[[',i)){
   const end=source.indexOf(']]',i+2);
   if(end>=0){flush();const [target,label]=source.slice(i+2,end).split('|');result+=`<a href="obsidian://open?vault=${encodeURIComponent(ui.data?.obsidian_vault||'')}&file=${encodeURIComponent(target.split('#')[0]+'.md')}">${esc(label||target.split('/').pop())}</a>`;i=end+2;continue;}
  }
  if(source[i]==='['){
   const labelEnd=source.indexOf('](',i+1);
   if(labelEnd>=0&&!/[\[\]\n]/.test(source.slice(i+1,labelEnd))){
    let end=labelEnd+2,depth=1;
    for(;end<source.length&&depth&&source[end]!=='\n';end++){if(source[end]==='\\'){end++;continue;}if(source[end]==='(')depth++;else if(source[end]===')')depth--;}
    if(!depth){flush();const label=inline(source.slice(i+1,labelEnd),navigation),destination=source.slice(labelEnd+2,end-1);result+=readerLink(label,destination,navigation);i=end;continue;}
   }
  }
  pending+=source[i++];
 }
 flush();return result;
}
function readerLink(label,destination,navigation) {
 const target=destination.trim();
 if(target.startsWith('#')){
  let key;try{key=decodeURIComponent(target.slice(1));}catch{key=null;}
  const id=key&&navigation?.targets.get(key);
  if(id)return `<a href="#${id}" data-document-anchor="${id}">${label}</a>`;
 }else if(/^https?:\/\//i.test(target)&&!/[\u0000-\u0020\u007f]/.test(target)){
  try{const url=new URL(target);if(['http:','https:'].includes(url.protocol)&&!url.username&&!url.password)return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${label}</a>`;}catch{}
 }
 return `${label} (<code>${esc(destination)}</code>)`;
}
function headingSlug(value) {
 return String(value).replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/<[^>]*>/g,'').replace(/[`*_~]/g,'').toLowerCase().replace(/[^\p{L}\p{N}_\s-]/gu,'').trim().replace(/\s/g,'-');
}
function documentNavigation(lines,aliases={}) {
 const targets=new Map(),nodes=new Map(),counts=new Map(),prefix=`catalog-document-${markdown.sequence=(markdown.sequence||0)+1}`;let fence=null;
 for(let i=0;i<lines.length;i++){
  const line=lines[i],marker=line.match(/^\s*(`{3,}|~{3,})(.*)$/);
  if(fence){if(marker&&marker[1][0]===fence[0]&&marker[1].length>=fence.length)fence=null;continue;}
  if(marker){fence=marker[1];continue;}
  if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i+1])){i++;while(i+1<lines.length&&lines[i+1].trim()&&lines[i+1].includes('|'))i++;continue;}
  const explicit=line.match(/^\s*<a\s+(?:id|name)=(['"])([\p{L}\p{N}_.:-]+)\1\s*>\s*<\/a>\s*$/u),heading=line.match(/^(#{1,6})\s+(.+)$/);let key;
  if(explicit)key=explicit[2];
  else if(heading){const base=headingSlug(heading[2]);const count=counts.get(base)||0;counts.set(base,count+1);key=base+(count?'-'+count:'');}
  if(key){const id=prefix+'-'+i;nodes.set(i,{id,explicit:!!explicit});if(!targets.has(key))targets.set(key,id);}
 }
 for(const [source,destination] of Object.entries(aliases||{})){if(!targets.has(source)&&typeof destination==='string'&&targets.has(destination))targets.set(source,targets.get(destination));}
 return {targets,nodes};
}
function followDocumentAnchor(event) {
 const link=event.target.closest?.('[data-document-anchor]'),root=link?.closest('.document-preview');if(!root)return;
 const target=[...root.querySelectorAll('[id]')].find(node=>node.id===link.dataset.documentAnchor);event.preventDefault();
 if(target){target.scrollIntoView({block:'start'});target.focus({preventScroll:true});}
}
function instructionBody(text) {
 return String(text).replace(/^\uFEFF?---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/,'');
}
function markdown(text,aliases={}) {
 const lines=String(text).replace(/\r\n/g,'\n').split('\n');const html=[],navigation=documentNavigation(lines,aliases),renderInline=value=>inline(value,navigation);
 let code=null,codeLines=[],paragraph=[],lists=[];
 const flushParagraph=()=>{if(paragraph.length){html.push(`<p>${renderInline(paragraph.join('\n')).replace(/\n/g,'<br>')}</p>`);paragraph=[];}};
 const closeLevel=()=>{const level=lists.pop();html.push(`</li></${level.kind}>`);};
 const closeList=()=>{while(lists.length)closeLevel();};
 const flush=()=>{flushParagraph();closeList();};
 const cells=line=>{const source=line.trim().replace(/^\|/,'').replace(/\|$/,'');const result=[];let cell='',ticks=0;for(let i=0;i<source.length;i++){if(source[i]==='\\'&&source[i+1]==='|'){cell+='|';i++;}else if(source[i]==='`'){let end=i;while(source[end]==='`')end++;const count=end-i;if(!ticks)ticks=count;else if(ticks===count)ticks=0;cell+=source.slice(i,end);i=end-1;}else if(source[i]==='|'&&!ticks){result.push(cell.trim());cell='';}else cell+=source[i];}result.push(cell.trim());return result;};
 for(let i=0;i<lines.length;i++) {
  const line=lines[i],fence=line.match(/^\s*(`{3,}|~{3,})(.*)$/);
  if(code){if(fence&&fence[1][0]===code[0]&&fence[1].length>=code.length){html.push(`<pre tabindex="0"><code>${esc(codeLines.join('\n'))}</code></pre>`);code=null;codeLines=[];}else codeLines.push(line);continue;}
  if(fence){flush();code=fence[1];continue;}
  if(!line.trim()){flush();continue;}
  const anchor=navigation.nodes.get(i);
  if(anchor?.explicit){flush();html.push(`<span id="${anchor.id}" tabindex="-1"></span>`);continue;}
  const heading=line.match(/^(#{1,6})\s+(.+)$/);
  if(heading){flush();html.push(`<h${heading[1].length}${anchor?` id="${anchor.id}" tabindex="-1"`:''}>${renderInline(heading[2])}</h${heading[1].length}>`);continue;}
  if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)){flush();html.push('<hr>');continue;}
  if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i+1])){
   flush();const headers=cells(line);i++;const rows=[];
   while(i+1<lines.length&&lines[i+1].trim()&&lines[i+1].includes('|')){rows.push(cells(lines[++i]));}
   html.push(`<div class="markdown-table" tabindex="0"><table><thead><tr>${headers.map(cell=>`<th>${renderInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${renderInline(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);continue;
  }
  if(/^\s*>/.test(line)){flush();html.push(`<blockquote>${renderInline(line.replace(/^\s*>\s?/,''))}</blockquote>`);continue;}
  const item=line.match(/^(\s*)(?:([-*+])\s+|(\d+)[.)]\s+)(.*)$/);
  if(item){flushParagraph();const kind=item[2]?'ul':'ol',indent=item[1].replace(/\t/g,'    ').length;while(lists.length&&indent<lists.at(-1).indent)closeLevel();if(lists.length&&indent===lists.at(-1).indent&&kind!==lists.at(-1).kind)closeLevel();if(!lists.length||indent>lists.at(-1).indent){html.push(`<${kind}${item[3]&&item[3]!=='1'?` start="${Number(item[3])}"`:''}>`);lists.push({kind,indent});}else html.push('</li>');html.push(`<li>${renderInline(item[4])}`);continue;}
  if(lists.length&&line.match(/^\s*/)[0].replace(/\t/g,'    ').length>lists.at(-1).indent){html.push(`<br>${renderInline(line.trim())}`);continue;}
  closeList();paragraph.push(line);
 }
 flush();if(code)html.push(`<pre tabindex="0"><code>${esc(codeLines.join('\n'))}</code></pre>`);
 return html.join('');
}
function openDocumentModal(title,text,notice='',aliases={}) {
 formDialog.classList.add('reading-document');
 document.querySelector('#form-content').innerHTML=`<div class="form-header"><h2>${esc(title)}</h2><button class="icon-button" data-close-form aria-label="Закрыть">${icon('close')}</button></div>${notice?`<p class="instruction-notice">${esc(notice)}</p>`:''}<div class="document-preview" lang="ru">${markdown(text,aliases)}</div>`;
 document.querySelector('[data-close-form]').onclick=requestFormClose;
 if(!formDialog.open)formDialog.showModal();
 formDialog.scrollTop=0;
}
formDialog.addEventListener('close',()=>formDialog.classList.remove('reading-document'));
document.addEventListener('click',followDocumentAnchor);

function renderSearch() {
 const completed=[...ui.data.events].reverse().filter(e=>e.kind==='search_completed');
 const latest=completed[0];
 content.innerHTML=`<div class="search-hero"><h1>Какой навык вам нужен?</h1><p>Опишите задачу своими словами. Менеджер найдёт опубликованные варианты и сохранит подборку в историю.</p><form id="search-form" class="search-launch"><label class="search-field">${icon('search')}<input id="new-query" aria-label="Задача для поиска новых навыков" type="search" placeholder="Например, плавная анимация персонажей" maxlength="500" required></label><button class="primary-button" ${ui.pendingJob?'disabled':''} type="submit">${icon('search')}Найти навыки</button></form><div class="suggestions">${['Дизайн интерфейсов','Анимация','Анализ данных'].map(t=>`<button class="suggestion" data-suggestion="${t}">${t}</button>`).join('')}</div></div><div id="search-job">${ui.pendingJob?'<div class="search-progress"><span class="spinner"></span><div>Собираем варианты<small>Можно перейти в другой раздел. Запрос уже сохраняется в истории.</small></div></div>':''}</div><div class="section-label"><h2>${latest?'Последняя подборка':'Ваши будущие подборки'}</h2><span>${latest?esc(date(latest.at,true)):''}</span></div><div id="proposals">${latest?proposalList(latest):empty('Начните с одной задачи','Результаты появятся здесь. Поиск предлагает варианты; установка выполняется после вашего выбора.')}</div><p class="small-note">Источники: опубликованные инструкции OpenAI, Anthropic и Remotion. Это подбор по известным источникам, охват не равен всему интернету.</p>`;
 document.querySelectorAll('[data-suggestion]').forEach(b=>b.onclick=()=>{document.querySelector('#new-query').value=b.dataset.suggestion;document.querySelector('#new-query').focus();});
 document.querySelector('#search-form').onsubmit=guarded(async event=>{event.preventDefault();const query=document.querySelector('#new-query').value;await runJob('search',{query});});
 bindProposalButtons();
}
function safeURL(value) {try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'#';}catch{return '#';}}
function proposalInfo(item){try{const u=new URL(item.url);const repo=u.hostname==='github.com'?u.pathname.split('/').slice(1,3).join('/'):'';return ui.data.proposal_labels?.[repo+':'+item.name];}catch{return null;}}
function proposalList(event) {
 const data=event.data;
 const prefix=`<p class="small-note">По запросу: <strong>${esc(data.query||'')}</strong></p>${(data.warnings||[]).map(w=>`<div class="inline-warning">Один из источников не ответил или оказался недоступен. Подборка может быть неполной.<details><summary>Подробности</summary>${esc(w)}</details></div>`).join('')}`;
 const cards=(data.candidates||[]).map((item,index)=>{
  const reviewed=item.review||{}, known=proposalInfo(item);
  const title=reviewed.title_ru||known?.title||item.name;
  const helps=reviewed.helps_ru||known?.helps||'Опубликованный вариант для этой задачи. Перед применением уточните назначение и условия в источнике или передайте его в Codex.';
  const prepare=reviewed.requirements_ru||known?.prepare;
  return `<article class="proposal-card"><div class="proposal-top"><span class="skill-icon">${icon('spark')}</span><span class="muted">${item.review?'Инструкция прочитана · оценка Codex':'Опубликованная инструкция'}</span><span class="tag">Предложено</span></div><h3>${esc(title)}</h3><span class="skill-name">${esc(item.name)}</span><p>${esc(helps)}</p>${prepare?`<p>${esc(prepare)}</p>`:''}<details class="source-description"><summary>${item.review?'Сравнение и условия':'Описание автора'}</summary><p>${esc(item.summary||item.description||'Описание отсутствует.')}</p></details><a href="${esc(safeURL(item.url))}" target="_blank" rel="noopener noreferrer">Открыть источник ↗</a><button class="quiet-button" data-proposal-copy="${index}" data-search-id="${event.id}">${icon('copy')}Передать в Codex</button><p class="small-note">${item.revision?'Версия: '+esc(item.revision.slice(0,12))+' · ':''}Установка и испытание этим результатом не подтверждены.</p></article>`;
 }).join('');
 return prefix+(cards||empty('Вариантов пока нет','Попробуйте точнее описать задачу. Ограничения поиска сохранены в истории.'));
}
function bindProposalButtons(){document.querySelectorAll('[data-proposal-copy]').forEach(b=>b.onclick=guarded(async()=>{const event=ui.data.events.find(e=>e.id===b.dataset.searchId);const item=event.data.candidates[Number(b.dataset.proposalCopy)];await navigator.clipboard.writeText(`Проверь навык ${item.name}: ${item.url}. Объясни пользу, зависимости и ограничения для моей задачи, затем помоги с установкой выбранного варианта. ID поиска: ${event.id}`);toast('Запрос скопирован. Вставьте его в чат Codex.');}));}
async function runJob(action,data={}) {
 if(ui.pendingJob)return toast('Дождитесь текущего действия.');
 const started=await api(action,data);ui.pendingJob=started.job_id;render();
 try {let result;while(true){result=await api('job?id='+encodeURIComponent(started.job_id));if(result.status!=='running')break;await new Promise(resolve=>setTimeout(resolve,1200));}if(result.status==='error')throw new Error(result.error);await load();showSaved(result.result,action==='search'?'Подборка сохранена в истории':'Каталог обновлён');}
 catch(error){try{await load();}catch{}toast(error.message,true);}
 finally{ui.pendingJob=null;render();}
}
function renderNotebook(){
 content.innerHTML=heading('Блокнот','Ваши мысли о навыках — без потерянных записей.',`<button id="new-wish" class="primary-button">${icon('plus')}Новое пожелание</button>`)+`<div class="tab-bar">${[['wishes','Пожелания'],['inbox','Быстрые заметки'],['skill-notes','Заметки к навыкам']].map(([id,title])=>`<button class="tab-button ${ui.notebook===id?'active':''}" data-notebook="${id}">${title}</button>`).join('')}</div><div id="notebook-content"></div>`;
 document.querySelector('#new-wish').onclick=()=>openWishForm();document.querySelectorAll('[data-notebook]').forEach(b=>b.onclick=()=>{if(document.querySelector('#inbox-editor')?.dataset.dirty==='true'&&!confirm('В заметке есть несохранённый текст. Перейти без сохранения?'))return;ui.notebook=b.dataset.notebook;renderNotebook();});
 const box=document.querySelector('#notebook-content');
 if(ui.notebook==='wishes'){box.innerHTML=`<p class="small-note">Пожелание сохраняет мысль. Работу или установку вы поручаете отдельно.</p><div class="wish-grid">${ui.data.wishes.map(w=>`<button class="wish-card" data-wish="${esc(w.id)}"><span class="skill-icon">${icon('book')}</span><div><span class="wish-id">${esc(w.id)}</span><h2>${esc(w.title)}</h2><p>${esc(w.next_step)}</p></div><span class="status-badge ${w.state==='Проверено'?'verified':''}">${esc(w.state)}</span></button>`).join('')||empty('Пожелания начинаются с одной мысли','Запишите, какого результата вам не хватает или что хотелось бы улучшить.')}</div>`;document.querySelectorAll('[data-wish]').forEach(b=>b.onclick=guarded(()=>viewDocument(b.dataset.wish,box)));}
 else if(ui.notebook==='inbox'){box.innerHTML='<div class="loading"><span class="spinner"></span>Открываем заметку…</div>';openInbox(box).catch(error=>{box.innerHTML=empty('Заметка недоступна',error.message);});}
 else {const notes=ui.data.skills.filter(c=>c.notes?.length);box.innerHTML=notes.map(card=>`<button class="wish-card" data-note-skill="${esc(card.id)}"><span class="skill-icon">${icon('pen')}</span><div><span class="wish-id">${esc(card.name)}</span><h2>${esc(card.title_ru||card.name)}</h2><p>${esc(card.notes[card.notes.length-1])}</p></div><span class="status-badge">${card.notes.length} заметок</span></button>`).join('')||empty('Здесь появится ваш опыт','Откройте карточку навыка и добавьте первое наблюдение.');document.querySelectorAll('[data-note-skill]').forEach(b=>b.onclick=guarded(()=>openSkill(b.dataset.noteSkill)));}
}
async function openInbox(box){const doc=await api('document?name=inbox');if(ui.page!=='notebook'||ui.notebook!=='inbox')return;box.innerHTML=`<div class="document-panel"><div class="document-toolbar"><span>Входящие мысли · обычная заметка Obsidian</span><button class="primary-button" id="save-inbox">Сохранить</button></div><textarea class="editor" id="inbox-editor" aria-label="Текст быстрых заметок" maxlength="100000">${esc(doc.markdown)}</textarea><span class="editor-help" id="editor-help">Изменения сохраняются по кнопке. Предыдущая версия остаётся в резерве.</span></div>`;const field=document.querySelector('#inbox-editor');field.oninput=()=>{field.dataset.dirty='true';document.querySelector('#editor-help').textContent='Есть несохранённые изменения';};document.querySelector('#save-inbox').onclick=guarded(async event=>{event.target.disabled=true;try{const saved=await api('document',{name:'inbox',text:field.value,revision:doc.revision});doc.revision=saved.revision;field.dataset.dirty='false';document.querySelector('#editor-help').textContent='Сохранено · '+new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'});showSaved(saved,'Заметка сохранена в Obsidian');await load();}finally{event.target.disabled=false;}});}
async function viewDocument(name,box){
 const doc=await api('document?name='+encodeURIComponent(name));
 const wish=ui.data.wishes.find(w=>w.id===name);
 box.innerHTML=`<div class="document-panel"><div class="document-toolbar"><button class="quiet-button" id="back-to-list">← К списку</button><a class="quiet-button" href="${esc(doc.obsidian_uri)}">Открыть в Obsidian ${icon('link')}</a></div><div class="document-preview">${markdown(doc.markdown)}</div>${wish?`<section class="detail-section"><h2>Добавить наблюдение или изменить состояние</h2><form id="wish-update-form"><select class="filter-select" id="wish-state" aria-label="Состояние пожелания">${wishStates.map(state=>`<option ${state===wish.state?'selected':''}>${state}</option>`).join('')}</select><label class="small-note" for="wish-next-step">Следующий шаг</label><input class="text-input" id="wish-next-step" value="${esc(wish.next_step)}" maxlength="400" required><textarea class="note-input" id="wish-comment" aria-label="Комментарий к пожеланию" placeholder="Наблюдение, уточнение или результат фактической проверки…" maxlength="20000"></textarea><button class="primary-button" type="submit">Сохранить</button><p class="small-note">Исходная формулировка останется прежней. Для новой отметки «Проверено» нужен комментарий о фактической проверке.</p></form></section>`:''}</div>`;
 document.querySelector('#back-to-list').onclick=()=>ui.page==='history'?renderHistory():renderNotebook();
 if(wish)document.querySelector('#wish-update-form').onsubmit=guarded(async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{const result=await api('wish-update',{id:name,revision:doc.revision,state:document.querySelector('#wish-state').value,comment:document.querySelector('#wish-comment').value,next_step:document.querySelector('#wish-next-step').value});await load();await viewDocument(name,box);showSaved(result,'Карточка и список пожеланий обновлены');}finally{button.disabled=false;}});
}
function openWishForm(card=null){const requestId=crypto.randomUUID();document.querySelector('#form-content').innerHTML=`<div class="form-header"><h2>Новое пожелание</h2><button class="icon-button" data-close-form aria-label="Закрыть">${icon('close')}</button></div><p>${card?'К навыку «'+esc(card.title_ru||card.name)+'». ':''}Запишите своими словами. Эта запись сама не запускает работу.</p><form id="wish-form"><label for="wish-title">Короткое название</label><input class="text-input" id="wish-title" placeholder="Что хотелось бы улучшить или получить?" maxlength="140" required><label for="wish-text">Ваша мысль</label><textarea class="note-input" id="wish-text" placeholder="Что сейчас мешает? Какой результат вам нужен?" maxlength="20000" required></textarea><div class="form-actions"><button type="button" class="secondary-button" data-cancel>Отмена</button><button type="submit" class="primary-button">Сохранить пожелание</button></div></form>`;document.querySelector('[data-close-form]').onclick=requestFormClose;document.querySelector('[data-cancel]').onclick=requestFormClose;document.querySelector('#wish-form').onsubmit=guarded(async event=>{event.preventDefault();const button=event.target.querySelector('[type="submit"]');button.disabled=true;try{const result=await api('wish',{title:document.querySelector('#wish-title').value,text:document.querySelector('#wish-text').value,skill_id:card?.id||null,request_id:requestId});formDialog.close();detailDialog.close();await load();ui.notebook='wishes';navigate('notebook');showSaved(result,'Пожелание '+result.id+' сохранено');}finally{button.disabled=false;}});if(!formDialog.open)formDialog.showModal();}
function renderHistory(){
 content.innerHTML=heading('История','Запросы, изменения и результаты — в порядке событий.')+`<div class="tab-bar"><button class="tab-button ${ui.history==='actions'?'active':''}" data-history="actions">Действия каталога</button><button class="tab-button ${ui.history==='journal'?'active':''}" data-history="journal">Журнал разработки</button></div><div id="history-content"></div>`;
 document.querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>{ui.history=b.dataset.history;renderHistory();});const box=document.querySelector('#history-content');
 if(ui.history==='journal'){box.innerHTML='<div class="loading"><span class="spinner"></span>Открываем журнал…</div>';viewDocument('journal',box).catch(e=>{box.innerHTML=empty('Журнал недоступен',e.message);});return;}
 box.innerHTML=`<div class="filter-row">${[['all','Все события'],['search','Поиск'],['operation','Установки и обновления'],['notes','Мои записи']].map(([key,title])=>`<button class="filter-chip ${ui.historyKind===key?'active':''}" data-kind="${key}">${title}</button>`).join('')}</div><div class="timeline" id="timeline"></div>`;document.querySelectorAll('[data-kind]').forEach(b=>b.onclick=()=>{ui.historyKind=b.dataset.kind;renderHistory();});
 const events=[...ui.data.events].reverse().filter(e=>ui.historyKind==='all'||ui.historyKind==='search'&&e.kind.startsWith('search_')||ui.historyKind==='operation'&&(e.kind.startsWith('operation_')||e.kind==='catalog_installed'||e.kind.startsWith('skill_activation_'))||ui.historyKind==='notes'&&['user_note_added','document_saved','wish_created','wish_updated','favorite_changed','direction_created','direction_renamed','skill_directions_changed','skill_origin_changed','skill_author_changed','skill_application_verified','project_added','project_recommendation_changed','project_application_recorded','resource_catalog_changed','skill_organization_changed','catalog_organization_migrated'].includes(e.kind));
 document.querySelector('#timeline').innerHTML=events.map(event=>{const d=event.data;const skill=ui.data.skills.find(c=>c.id===d.skill_id);let detail=d.query||d.title||d.task||(skill?skill.title_ru||skill.name:'');if(event.kind.startsWith('operation_'))detail=({install:'Установка',update:'Обновление',replace:'Замена',remove:'Удаление'}[d.action]||'Изменение')+': '+(d.target||'').split(/[\\/]/).pop();if(event.kind.startsWith('skill_activation_'))detail=(skill?skill.title_ru||skill.name:d.skill_name)+' · '+(d.actual_enabled===true?'Включено':d.actual_enabled===false?'Отключено':'Состояние не определено')+(d.restart_required?' · Требуется перезапуск Codex':'');if(event.kind==='skill_application_verified')detail=d.title+' · '+d.result;if(event.kind.startsWith('project_'))detail=(d.project_name||'Проект')+(d.skill_name?' · '+d.skill_name:'')+(d.application?.result?' · '+d.application.result:d.action==='unrecommend'?' · Убрано из рекомендаций':'');if(event.kind==='skill_origin_changed')detail=(skill?skill.title_ru||skill.name:d.skill_name)+' · '+(origins[d.before_origin]||d.before_origin)+' → '+(origins[d.origin]||d.origin);if(event.kind==='skill_author_changed')detail=(skill?skill.title_ru||skill.name:d.skill_name)+' · '+(d.author_profile?.name||'Автор не указан')+' · ссылок: '+(d.author_profile?.links?.length||0);if(event.kind==='direction_renamed')detail=d.before_title+' → '+d.title;if(event.kind==='skill_directions_changed')detail=(skill?skill.title_ru||skill.name:d.skill_name)+' · '+((d.direction_titles||[]).join(', ')||'Без направления');if(event.kind==='directions_initialized'||event.kind==='directions_seeded')detail='Навыков с исходными назначениями: '+d.skill_count;if(event.kind==='inventory_refreshed')detail='Список сверён с найденными установками. Старые записи и заметки сохранены.';if(event.kind==='catalog_installed')detail='Обновлена рабочая копия каталога. Личные данные сохранены.';if(event.kind==='document_saved')detail=d.document;if(event.kind==='wish_updated')detail=(ui.data.wishes.find(w=>w.id===d.wish_id)?.title||d.wish_id)+' · '+d.state;if(event.kind==='organization_completed')detail='Постоянный проект, документы и рабочий блокнот.';if(event.kind==='favorite_changed')detail=(d.favorite?'В избранное: ':'Из избранного: ')+detail;if(d.outcome)detail+=(detail?' · ':'')+({success:'изменения подтверждены',unchanged:'файлы не изменились',failure:'ошибка',unproven:'результат не подтверждён',interrupted:'прервано'}[d.outcome]||d.outcome);return `<article class="event"><span class="event-icon">${icon(event.kind.startsWith('search')?'search':event.kind.includes('note')||event.kind.includes('wish')?'pen':'history')}</span><div><h2>${esc(labels[event.kind]||'Служебное событие каталога')}</h2>${detail?`<p>${esc(detail)}</p>`:''}${event.kind==='search_completed'?`<p>Предложено вариантов: ${(d.candidates||[]).length}. Установка этим событием не подтверждается.</p><button class="event-more" data-view-search="${event.id}">Открыть подборку →</button>`:''}${event.kind==='search_failed'?`<p>${esc(d.error||'Не удалось прочитать источники.')}</p>`:''}</div><time datetime="${esc(event.at)}">${esc(date(event.at,true))}</time></article>`;}).join('') || empty('Событий пока нет','Здесь появятся ваши поиски, заметки и фактические изменения.');
 document.querySelectorAll('[data-view-search]').forEach(b=>b.onclick=()=>{const event=ui.data.events.find(e=>e.id===b.dataset.viewSearch);document.querySelector('#form-content').innerHTML=`<div class="form-header"><h2>Сохранённая подборка</h2><button class="icon-button" data-close-form aria-label="Закрыть">${icon('close')}</button></div>${proposalList(event)}`;document.querySelector('[data-close-form]').onclick=requestFormClose;bindProposalButtons();formDialog.showModal();});
}
function help() {openCatalogGuide();}
document.querySelector('#menu-button').innerHTML=icon('menu');
document.querySelector('#menu-button').onclick=()=>{document.querySelector('#sidebar').classList.toggle('open');document.querySelector('#sidebar-shade').classList.toggle('open');syncSidebar();if(sidebar.classList.contains('open'))sidebar.querySelector('.nav-item').focus();};
document.querySelector('#sidebar-shade').onclick=closeSidebar;
document.querySelector('#help-button').onclick=help;
document.querySelector('#refresh-button').onclick=guarded(()=>runJob('refresh'));
document.querySelector('.brand').onclick=event=>{event.preventDefault();navigate('skills');};
function hasUnsaved(){if(formDialog.dataset.directionSaving==="true")return true;if(formDialog.open&&document.querySelector('[data-direction-dirty="true"]'))return true;return document.querySelector('#inbox-editor')?.dataset.dirty==='true'||(detailDialog.open&&!!document.querySelector('#skill-note')?.value.trim())||(formDialog.open&&!!document.querySelector('#wish-form')&&!!(document.querySelector('#wish-title')?.value.trim()||document.querySelector('#wish-text')?.value.trim()));}
function requestFormClose(){if(formDialog.dataset.directionSaving==="true"){toast("Дождитесь завершения действия.");return;}if(document.querySelector('[data-direction-dirty="true"]')&&!confirm('Изменения ещё не сохранены. Закрыть форму?'))return;if(document.querySelector('#wish-form')&&(document.querySelector('#wish-title')?.value.trim()||document.querySelector('#wish-text')?.value.trim())&&!confirm('Пожелание ещё не сохранено. Закрыть форму?'))return;formDialog.close();}
detailDialog.addEventListener('cancel',event=>{if(document.querySelector('#skill-note')?.value.trim()&&!confirm('Заметка ещё не сохранена. Закрыть карточку?'))event.preventDefault();});
formDialog.addEventListener('cancel',event=>{if(formDialog.dataset.directionSaving==='true'){event.preventDefault();return;}if(document.querySelector('[data-direction-dirty="true"]')&&!confirm('Изменения ещё не сохранены. Закрыть форму?')){event.preventDefault();return;}if(document.querySelector('#wish-form')&&(document.querySelector('#wish-title')?.value.trim()||document.querySelector('#wish-text')?.value.trim())&&!confirm('Пожелание ещё не сохранено. Закрыть форму?'))event.preventDefault();});
window.addEventListener('beforeunload',event=>{if(hasUnsaved()){event.preventDefault();event.returnValue='';}});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!detailDialog.open&&!formDialog.open&&!guideDialog.open)closeSidebar();if(!detailDialog.open&&!formDialog.open&&!guideDialog.open&&(event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();navigate('skills');document.querySelector('#skill-search')?.focus();}});
window.addEventListener('hashchange',()=>{const page=location.hash.slice(1);if(['skills','connections','projects','search','notebook','history'].includes(page)&&page!==ui.page)navigate(page);});
(async()=>{try{await load();const page=location.hash.slice(1);if(['skills','connections','projects','search','notebook','history'].includes(page))ui.page=page;render();}catch(error){content.innerHTML=empty('Не удалось открыть каталог',error.message, '<button class="primary-button" id="retry-load">Попробовать ещё раз</button>');document.querySelector('#retry-load').onclick=()=>location.reload();}})();


// The guide reads the canonical Obsidian note; opening it never changes catalogue data.
const guideDialog=document.createElement('dialog');
guideDialog.className='guide-dialog';guideDialog.id='guide-dialog';guideDialog.setAttribute('aria-labelledby','guide-title');document.body.append(guideDialog);
const guideState={sections:[],selected:0,query:'',request:0,loading:false};
const guideWideScreen=matchMedia('(min-width:761px)');
guideWideScreen.addEventListener('change',event=>{const contents=guideDialog.querySelector('.guide-contents');if(contents)contents.open=event.matches;});
function guideSections(text){
 const sections=[];let current=null,intro=[],fence=null;
 for(const line of String(text).replace(/\r\n/g,'\n').split('\n')){
  const marker=line.match(/^\s*(`{3,}|~{3,})/);
  if(marker){if(!fence)fence=marker[1];else if(marker[1][0]===fence[0]&&marker[1].length>=fence.length)fence=null;}
  const title=!fence&&!marker&&line.match(/^## (.+?)\s*$/);
  if(title){current={title:title[1],lines:[]};sections.push(current);}
  else if(current)current.lines.push(line);else if(fence||marker||!/^# /.test(line))intro.push(line);
 }
 if(!sections.length)return [{title:'Инструкция',body:intro.join('\n')}];
 sections[0].lines.unshift(intro.join('\n'));
 return sections.map(section=>({title:section.title,body:section.lines.join('\n')}));
}
const guideSearchText=text=>String(text).toLocaleLowerCase('ru-RU').replace(/ё/g,'е');
function guideMatches(){const words=guideSearchText(guideState.query).trim().split(/\s+/).filter(Boolean);return guideState.sections.map((section,index)=>({section,index})).filter(({section})=>words.every(word=>guideSearchText(section.title+' '+section.body).includes(word)));}
async function openCatalogGuide(){
 if(guideDialog.open){guideDialog.querySelector('#guide-search')?.focus();return;}
 guideDialog.innerHTML=`<header class="guide-header"><div><p class="guide-eyebrow">Личный каталог · помощь</p><h2 id="guide-title">Как пользоваться каталогом</h2><p>Пошаговые действия в браузере и готовые запросы для Codex.</p></div><button class="icon-button" id="close-guide" aria-label="Закрыть инструкцию">${icon('close')}</button></header><div class="guide-tools"><label class="search-field">${icon('search')}<input id="guide-search" type="search" placeholder="Например, новый проект или установить" aria-label="Поиск по инструкции" value="${esc(guideState.query)}"></label><button class="quiet-button" id="guide-clear">Сбросить поиск</button><p id="guide-count" role="status"></p></div><div class="guide-layout"><details class="guide-contents" ${matchMedia('(min-width:761px)').matches?'open':''}><summary>Разделы инструкции</summary><nav id="guide-toc" aria-label="Разделы инструкции"></nav></details><section class="guide-reading" aria-label="Текст инструкции"><div id="guide-article"></div></section></div><footer class="guide-footer"><span>Текст из вашего Obsidian</span><button class="quiet-button" id="guide-reload">Перечитать справку</button><button class="quiet-button" id="guide-stop">Завершить работу менеджера</button></footer>`;
 guideDialog.querySelector('#close-guide').onclick=()=>guideDialog.close();
 guideDialog.querySelector('#guide-search').oninput=event=>{guideState.query=event.target.value;renderCatalogGuide();};
 guideDialog.querySelector('#guide-clear').onclick=()=>{guideState.query='';guideDialog.querySelector('#guide-search').value='';renderCatalogGuide();guideDialog.querySelector('#guide-search').focus();};
 guideDialog.querySelector('#guide-reload').onclick=readCatalogGuide;
 guideDialog.querySelector('#guide-stop').onclick=guarded(async()=>{
  if(hasUnsaved()){guideStatus('Сначала закройте справку и сохраните набранный текст.');return;}
  if(!confirm('Завершить работу менеджера? Его можно снова открыть ярлыком «Навыки».'))return;
  try{await api('stop',{});}catch(error){guideStatus('Не удалось завершить работу. '+error.message);return;}
  guideDialog.close();content.innerHTML=empty('Менеджер закрыт','Чтобы вернуться, откройте ярлык «Навыки» на рабочем столе.');
 });
 guideDialog.showModal();
 await readCatalogGuide();
}
function guideStatus(message){const count=guideDialog.querySelector('#guide-count');if(count)count.textContent=message;}
async function readCatalogGuide(){
 const request=++guideState.request;guideState.loading=true;guideState.sections=[];guideDialog.querySelector('#guide-reload').disabled=true;
 guideStatus('Загружаем инструкцию…');
 guideDialog.querySelector('#guide-article').innerHTML='<p class="guide-loading" role="status">Открываем пошаговую справку…</p>';
 guideDialog.querySelector('#guide-toc').replaceChildren();
 try{
  const doc=await api('document?name=guide');
  if(!guideDialog.open||request!==guideState.request)return;
  guideState.sections=guideSections(doc.markdown);guideState.loading=false;renderCatalogGuide();
 }catch(error){
  if(!guideDialog.open||request!==guideState.request)return;
  guideState.sections=[];guideState.loading=false;guideStatus('Справка пока недоступна');
  guideDialog.querySelector('#guide-article').innerHTML=`<h3>Не удалось прочитать справку</h3><p>Проверьте, доступна ли папка документов Obsidian на этом компьютере. Затем нажмите «Перечитать справку».</p><p class="small-note">${esc(error.message)}</p>`;
 }finally{if(guideDialog.open&&request===guideState.request)guideDialog.querySelector('#guide-reload').disabled=false;}
}
function renderCatalogGuide(){
 if(guideState.loading)return;
 const matches=guideMatches(),toc=guideDialog.querySelector('#guide-toc'),article=guideDialog.querySelector('#guide-article');
 if(!matches.some(item=>item.index===guideState.selected))guideState.selected=matches[0]?.index??0;
 guideStatus(guideState.query.trim()?`Найдено разделов: ${matches.length}`:`В инструкции ${matches.length} разделов`);
 toc.innerHTML=matches.map(({section,index})=>`<button type="button" data-guide-section="${index}" ${index===guideState.selected?'aria-current="true"':''}><span class="guide-section-number">${index+1}</span>${esc(section.title)}</button>`).join('');
 toc.querySelectorAll('button').forEach(button=>button.onclick=()=>{guideState.selected=Number(button.dataset.guideSection);renderCatalogGuide();if(matchMedia('(max-width:760px)').matches)guideDialog.querySelector('details').open=false;article.querySelector('h3')?.focus();});
 if(!matches.length){article.innerHTML='<h3>Раздел не найден</h3><p>Попробуйте другие слова: «проект», «автор», «заметки», «включить». Или нажмите «Сбросить поиск», чтобы вернуться к оглавлению.</p>';return;}
 const selected=guideState.sections[guideState.selected],position=matches.findIndex(item=>item.index===guideState.selected);
 article.innerHTML=`<p class="guide-eyebrow">Раздел ${guideState.selected+1} из ${guideState.sections.length}</p><h3 class="guide-section-title" tabindex="-1">${esc(selected.title)}</h3><div class="document-preview">${markdown(selected.body)}</div><div class="guide-pager"><button class="secondary-button" id="guide-previous" ${position===0?'disabled':''}>← Предыдущий раздел</button><button class="secondary-button" id="guide-next" ${position===matches.length-1?'disabled':''}>Следующий раздел →</button></div>`;
 article.querySelector('#guide-previous').onclick=()=>chooseGuideSection(matches[position-1].index);
 article.querySelector('#guide-next').onclick=()=>chooseGuideSection(matches[position+1].index);
 article.querySelectorAll('pre').forEach(pre=>{
  const text=pre.querySelector('code').textContent,button=document.createElement('button');
  button.type='button';button.className='secondary-button guide-copy';button.textContent='Скопировать запрос';pre.after(button);
  button.onclick=async()=>{try{await navigator.clipboard.writeText(text);if(!button.isConnected)return;button.textContent='Скопировано — вставьте в чат Codex';}catch{if(!button.isConnected)return;button.textContent='Выделите текст запроса и скопируйте вручную';pre.focus();}};
 });
 guideDialog.querySelector('.guide-reading').scrollTop=0;
}
function chooseGuideSection(index){guideState.selected=index;renderCatalogGuide();guideDialog.querySelector('.guide-section-title').focus();}
guideDialog.addEventListener('close',()=>{guideState.request++;});
guideDialog.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();guideDialog.querySelector('#guide-search')?.focus();}});

function skillOrganizationFilters(){return `<div class="resource-filters skill-resource-filters"><label>Тег<select class="filter-select" aria-label="Тег навыка" data-skill-facet="catalogTag"></select></label><label>Связанный ресурс<select class="filter-select" aria-label="Связанный ресурс" data-skill-facet="relatedResource"></select></label><label>Назначение проекту<select class="filter-select" aria-label="Назначение проекту" data-skill-facet="usageProject"></select></label></div>`;}
function paintSkillOrganizationFilters(){
 const cards=ui.data.skills,known=ui.data.resource_summaries||[];
 const options={catalogTag:[...new Set(cards.flatMap(c=>c.catalog_tags||[]))].sort((a,b)=>a.localeCompare(b,'ru')).map(x=>[x,x]),relatedResource:known.filter(r=>cards.some(c=>(c.resource_ids||[]).includes(r.id))).map(r=>[r.id,r.title]),usageProject:(ui.data.catalog_projects||[]).map(p=>[p.id,p.name])};
 document.querySelectorAll('[data-skill-facet]').forEach(select=>{const key=select.dataset.skillFacet;select.innerHTML='<option value="all">Все</option>'+options[key].map(([id,label])=>`<option value="${esc(id)}" ${ui[key]===id?'selected':''}>${esc(label)} · ${filteredCatalogCards(cards,{...ui,[key]:id}).length}</option>`).join('');});
 const task=document.querySelector('#task-filter');if(task){for(const option of task.options){const label=option.value==='all'?'Все направления':option.value==='unassigned'?'Без направления':ui.data.directions.find(x=>x.id===option.value)?.title||option.textContent;option.textContent=label+' · '+filteredCatalogCards(cards,{...ui,task:option.value}).length;}}
 document.querySelectorAll('[data-origin]').forEach(button=>{const key=button.dataset.origin;button.textContent=(key==='all'?'Все навыки':origins[key]||key)+' · '+filteredCatalogCards(cards,{...ui,origin:key}).length;});
}
Object.assign(labels,{resource_catalog_changed:'Изменены сведения ресурса',skill_organization_changed:'Изменены теги и связи навыка',catalog_organization_migrated:'Обновлена организация каталога'});
