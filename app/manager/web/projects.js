'use strict';

const projectsView = {data:null, selectedId:null, request:0};

function projectsSkill(data, id) {return (data.skills||[]).find(skill=>skill.id===id);}
function projectsSkillName(data, id) {const skill=projectsSkill(data,id);return skill?(skill.title_ru||skill.name):'Навык больше не найден в каталоге';}
function projectsEvidenceURL(value) {
 try {
  if(typeof value!=='string'||/[\s<>\\\u0000-\u001f]/.test(value))return '';
  const url=new URL(value);
  if(['http:','https:'].includes(url.protocol)&&url.hostname&&!url.username&&!url.password)return url.href;
  if(url.protocol==='obsidian:'&&url.hostname==='open'&&!url.username&&!url.password&&url.searchParams.get('vault')&&url.searchParams.get('file'))return url.href;
 }catch{}
 return '';
}
function projectsSkillButton(data,id) {
 const name=projectsSkillName(data,id);
 return projectsSkill(data,id)?`<button class="project-skill-link" data-project-skill="${esc(id)}">${esc(name)}</button>`:`<span class="project-missing-skill">${esc(name)} <code>${esc(id)}</code></span>`;
}
function projectsRecommendationHTML(data, project) {
 return (project.recommendations||[]).map(item=>`<article class="project-record"><div class="project-record-heading"><h3>${projectsSkillButton(data,item.skill_id)}</h3><div class="project-record-actions"><button class="quiet-button" data-project-recommend-edit="${esc(item.skill_id)}" aria-label="Изменить рекомендацию: ${esc(projectsSkillName(data,item.skill_id))}">Изменить</button><button class="quiet-button" data-project-recommend-remove="${esc(item.skill_id)}" aria-label="Убрать из рекомендаций: ${esc(projectsSkillName(data,item.skill_id))}">Убрать</button></div></div><p class="project-preserve-lines">${esc(item.reason||'Причина выбора пока не записана.')}</p></article>`).join('')||'<p class="project-empty">Выберите навыки, которые пригодятся этому проекту, и запишите, для каких задач. Рекомендация сама не устанавливает и не запускает навык.</p>';
}
function projectsApplicationsHTML(data, project) {
 return [...(project.applications||[])].reverse().map(item=>{
  const url=projectsEvidenceURL(item.evidence_url);
  const label=item.evidence_label||'Открыть результат';
  return `<article class="project-record project-application"><div class="project-record-heading"><h3>${projectsSkillButton(data,item.skill_id)}</h3><time datetime="${esc(item.date)}">${esc(item.date)}</time></div><h4>Задача</h4><p class="project-preserve-lines">${esc(item.task)}</p><h4>Результат</h4><p class="project-preserve-lines">${esc(item.result)}</p>${url?`<a class="project-evidence-link" href="${esc(url)}" ${url.startsWith('http')?'target="_blank" rel="noopener noreferrer"':''}>${icon('link')}${esc(label)}<span class="sr-only">${url.startsWith('http')?' (откроется в новой вкладке)':' (откроется в Obsidian)'}</span></a>`:'<p class="small-note">Ссылка на результат недоступна. Сама запись сохранена.</p>'}<p class="small-note">${item.verification_basis==='user_confirmation'?'Подтверждено пользователем.':'Основание подтверждения не указано.'} ${item.skill_sha256?'Версия навыка зафиксирована.':'Версия навыка не зафиксирована.'}</p></article>`;
 }).join('')||'<p class="project-empty">Подтверждённых применений пока нет. После работы запишите задачу, проверенный результат и ссылку на него. Каталог не собирает автоматически сведения из всех чатов.</p>';
}
function projectsPageHTML(data, selectedId) {
 const projects=data.projects||[];
 const project=projects.find(item=>item.id===selectedId)||projects[0];
 const duplicateNames=new Set(projects.filter((item,index)=>projects.some((other,otherIndex)=>otherIndex!==index&&other.name===item.name)).map(item=>item.name));
 const selector=projects.length?`<div class="projects-selection"><label for="project-selector">Проект<select id="project-selector" class="filter-select">${projects.map(item=>`<option value="${esc(item.id)}" ${item.id===project.id?'selected':''}>${esc(item.name+(duplicateNames.has(item.name)?' — '+item.path:''))}</option>`).join('')}</select></label><p class="project-path"><span>Папка проекта</span><code>${esc(project.path)}</code></p></div>`:'<div class="project-section"><h2>Добавьте первый проект</h2><p>Укажите название и существующую папку на этом компьютере. Это добавит проект в каталог навыков; его файлы останутся на месте.</p></div>';
 const sections=project?`<section class="project-section" aria-labelledby="project-recommendations-title"><div class="project-section-heading"><div><h2 id="project-recommendations-title">Рекомендованные навыки <span>${(project.recommendations||[]).length}</span></h2><p>Ваш выбор для будущих задач проекта.</p></div><button class="secondary-button" id="project-add-recommendation">${icon('plus')}Добавить рекомендацию</button></div><div class="project-records">${projectsRecommendationHTML(data,project)}</div></section><section class="project-section" aria-labelledby="project-applications-title"><div class="project-section-heading"><div><h2 id="project-applications-title">Подтверждённые применения <span>${(project.applications||[]).length}</span></h2><p>Фактические результаты, которые вы проверили.</p></div><button class="secondary-button" id="project-add-application">${icon('plus')}Записать применение</button></div><div class="project-records">${projectsApplicationsHTML(data,project)}</div></section><details class="project-section project-installed"><summary>Установленные в проекте · ${(project.installed_skill_ids||[]).length}</summary><p>Это навыки с известной установкой в папке этого проекта. Глобальные, встроенные и доступные через расширения навыки можно выбрать в рекомендациях отдельно. Установка не подтверждает применение.</p><ul>${(project.installed_skill_ids||[]).map(id=>`<li>${projectsSkillButton(data,id)}</li>`).join('')}</ul>${!(project.installed_skill_ids||[]).length?'<p class="project-empty">Проектных установок в каталоге пока не найдено.</p>':''}</details>`:'';
 return heading('Проекты','Рекомендации и проверенные результаты для каждого проекта.',`<button class="primary-button" id="project-add">${icon('plus')}Добавить проект</button>`)+`<div class="projects-workspace">${selector}${project?projectsServicesHTML(project):''}${sections}</div>`;
}
function projectsPaint(data) {
 if(ui.page!=='projects')return;
 projectsView.data=data;
 if(!(data.projects||[]).some(item=>item.id===projectsView.selectedId))projectsView.selectedId=data.projects?.[0]?.id||null;
 content.innerHTML=projectsPageHTML(data,projectsView.selectedId);
 content.querySelector('#project-add').onclick=()=>openProjectForm('add');
 const services=content.querySelector('#project-services-open');if(services)services.onclick=()=>{resourceView.project=projectsView.selectedId;resourceView.relation='linked';navigate('connections');};
 const addResource=content.querySelector('#project-resource-add');if(addResource)addResource.onclick=guarded(()=>openResourceBinding(null,projectsView.selectedId));
 content.querySelectorAll('[data-project-resource]').forEach(b=>b.onclick=guarded(()=>openResource(b.dataset.projectResource)));
 content.querySelectorAll('[data-project-resource-edit]').forEach(b=>b.onclick=guarded(()=>openResourceBinding(b.dataset.projectResourceEdit,projectsView.selectedId)));
 const selector=content.querySelector('#project-selector');
 if(selector)selector.onchange=event=>{projectsView.selectedId=event.target.value;projectsPaint(projectsView.data);content.querySelector('#project-selector').focus();};
 content.querySelectorAll('[data-project-skill]').forEach(button=>button.onclick=guarded(()=>openSkill(button.dataset.projectSkill)));
 const recommend=content.querySelector('#project-add-recommendation'),application=content.querySelector('#project-add-application');
 if(recommend)recommend.onclick=()=>openProjectForm('recommend',projectsView.selectedId);
 if(application)application.onclick=()=>openProjectForm('application',projectsView.selectedId);
 content.querySelectorAll('[data-project-recommend-edit]').forEach(button=>button.onclick=()=>openProjectForm('recommend',projectsView.selectedId,button.dataset.projectRecommendEdit));
 content.querySelectorAll('[data-project-recommend-remove]').forEach(button=>button.onclick=()=>openProjectForm('unrecommend',projectsView.selectedId,button.dataset.projectRecommendRemove));
}
async function renderProjects() {
 const request=++projectsView.request;
 content.innerHTML=heading('Проекты','Рекомендации и проверенные результаты для каждого проекта.')+'<div id="projects-loading" role="status">Загружаем проекты…</div>';
 const marker=content.querySelector('#projects-loading');
 try {
  const data=await api('projects');
  if(request!==projectsView.request||ui.page!=='projects'||!marker.isConnected)return;
  projectsPaint(data);
 }catch(error){
  if(request!==projectsView.request||ui.page!=='projects'||!marker.isConnected)return;
  marker.innerHTML=`<p>${esc(error.message)}</p><button class="secondary-button" id="projects-retry">Повторить загрузку</button>`;
  marker.querySelector('button').onclick=renderProjects;
 }
}
function projectsSkillOptions(data,selected) {
 const skills=data.skills||[];
 const missing=selected&&!skills.some(skill=>skill.id===selected);
 return '<option value="">Выберите навык</option>'+skills.map(skill=>`<option value="${esc(skill.id)}" ${skill.id===selected?'selected':''}>${esc((skill.title_ru||skill.name)+(skill.state!=='present'?' — доступность не подтверждена':''))}</option>`).join('')+(missing?`<option value="${esc(selected)}" selected>Ранее выбранный навык больше не найден</option>`:'');
}
function projectsToday() {return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function projectsFormFields(action,data,project,skillId) {
 if(action==='add')return '<p class="editor-help">Укажите существующую папку. Проект появится только в этом каталоге; его файлы не перемещаются.</p><label for="project-name">Название проекта<input class="text-input" id="project-name" name="name" maxlength="160" required></label><label for="project-path">Полный путь к папке<input class="text-input" id="project-path" name="path" maxlength="4096" placeholder="Например, C:\\Проекты\\Мой проект" required></label>';
 if(action==='unrecommend')return `<p>Убрать «${esc(projectsSkillName(data,skillId))}» из рекомендаций проекта «${esc(project.name)}»?</p><p class="editor-help">Установка, карточка навыка и подтверждённые применения сохранятся.</p><input name="skill_id" type="hidden" value="${esc(skillId)}">`;
 const skillSelect=`<label for="project-skill">Навык<select class="filter-select" id="project-skill" name="skill_id" required>${projectsSkillOptions(data,skillId)}</select></label>`;
 if(action==='recommend')return skillSelect+`<label for="project-reason">Для каких задач рекомендуете<textarea class="note-input" id="project-reason" name="reason" maxlength="4000" required>${esc(project.recommendations?.find(item=>item.skill_id===skillId)?.reason||'')}</textarea></label><p class="editor-help">Это план использования. Навык не будет установлен или запущен этой записью.</p>`;
 return skillSelect+`<label for="project-date">Дата применения<input class="text-input" type="date" id="project-date" name="date" value="${esc(projectsToday())}" required></label><label for="project-task">Какая задача решалась<textarea class="note-input" id="project-task" name="task" maxlength="4000" required></textarea></label><label for="project-result">Что получилось и что вы проверили<textarea class="note-input" id="project-result" name="result" maxlength="12000" required></textarea></label><label for="project-evidence">Ссылка на результат<input class="text-input" id="project-evidence" name="evidence" maxlength="4096" placeholder="https://… или [[путь заметки Obsidian#Заголовок]]" required></label><p class="editor-help">Подойдёт страница с результатом или существующая заметка в вашем Obsidian. Запись основана на вашем подтверждении; версия навыка автоматически не приписывается прошлой работе.</p><label class="project-confirm"><input type="checkbox" name="confirmed" required><span>Я проверил результат и подтверждаю применение навыка.</span></label>`;
}
function projectsReadForm(form) {
 const result={};
 for(const element of form.querySelectorAll('[name]'))result[element.name]=element.type==='checkbox'?element.checked:element.value;
 return result;
}
function openProjectForm(action,projectId=null,skillId='') {
 const data=projectsView.data;
 const project=data?.projects.find(item=>item.id===projectId);
 if(!data||(action!=='add'&&!project)){toast('Сначала откройте нужный проект.',true);return;}
 let revision=data.revision,requestId=crypto.randomUUID(),refreshRequest=0;
 const titles={add:'Добавить проект',recommend:'Рекомендация для проекта',unrecommend:'Убрать рекомендацию',application:'Записать подтверждённое применение'};
 const saveText={add:'Добавить проект',recommend:'Сохранить рекомендацию',unrecommend:'Убрать из рекомендаций',application:'Сохранить применение'};
 document.querySelector('#form-content').innerHTML=directionFormHeader(titles[action])+`<form id="project-form" class="project-form" aria-label="${esc(titles[action])}">${project?`<p class="project-form-context">${esc(project.name)}<br><code>${esc(project.path)}</code></p>`:''}${projectsFormFields(action,data,project,skillId)}<div class="form-actions"><button class="secondary-button" type="button" data-close-form>Отмена</button><button class="primary-button" type="submit">${saveText[action]}</button></div></form><button id="project-reload" class="quiet-button">Обновить сведения, сохранив мой ввод</button><p class="small-note" id="project-form-status" role="status"></p>`;
 const form=formDialog.querySelector('#project-form'),status=formDialog.querySelector('#project-form-status');
 formDialog.querySelectorAll('[data-close-form]').forEach(button=>button.onclick=requestFormClose);
 const changed=()=>{form.dataset.directionDirty='true';requestId=crypto.randomUUID();};
 form.oninput=changed;form.onchange=changed;
 form.onsubmit=async event=>{
  event.preventDefault();
  if(formDialog.dataset.directionSaving==='true')return;
  const fields=projectsReadForm(form),submittedId=requestId;
  directionBusy(true);status.textContent='Сохраняем…';
  try {
   const saved=await api('projects',{action,revision,project_id:projectId,request_id:submittedId,...fields});
   if(!form.isConnected||!formDialog.open)return;
   const publishedRequest=++projectsView.request;
   projectsView.data=saved;
   if(action==='add'){
    const added=(saved.projects||[]).find(item=>item.path.replace(/\\/g,'/').toLowerCase()===fields.path.trim().replace(/\\/g,'/').replace(/\/+$/,'').toLowerCase());
    if(added)projectsView.selectedId=added.id;
   }
   form.dataset.directionDirty='false';directionBusy(false);formDialog.close();
   showSaved(saved,action==='application'?'Применение сохранено с вашим подтверждением.':action==='unrecommend'?'Рекомендация убрана. Навык сохранён.':action==='add'?'Проект добавлен в каталог.':'Рекомендация сохранена.');
   try{await load();}catch(error){toast('Запись сохранена. Не удалось обновить список и историю: '+error.message,true);}
   if(ui.page==='projects'&&publishedRequest===projectsView.request)projectsPaint(projectsView.data);
   if(ui.page==='history'&&ui.history==='actions')renderHistory();
   if(!formDialog.open)content.querySelector(action==='add'?'#project-selector':action==='application'?'#project-add-application':'#project-add-recommendation')?.focus();
  }catch(error){
   if(!form.isConnected||!formDialog.open)return;
   status.textContent=error.status===409?'Сведения изменились. Обновите их кнопкой ниже и проверьте свой ввод перед повторным сохранением.':'Запись не подтверждена. Ваш ввод сохранён; повторная отправка без изменений не создаст дубликат.';
   directionError(error,form);
  }finally{if(form.isConnected)directionBusy(false);}
 };
 formDialog.querySelector('#project-reload').onclick=async()=>{
  const request=++refreshRequest;
  directionBusy(true);status.textContent='Обновляем сведения, сохраняя ваш ввод…';
  try {
   const fresh=await api('projects');
   if(request!==refreshRequest||!form.isConnected||!formDialog.open)return;
   projectsView.request++;projectsView.data=fresh;revision=fresh.revision;
   const select=form.querySelector('[name="skill_id"]');
   if(select?.tagName==='SELECT'){const selected=select.value;select.innerHTML=projectsSkillOptions(fresh,selected);select.value=selected;}
   status.textContent=action!=='add'&&!fresh.projects.some(item=>item.id===projectId)?'Проект больше не найден. Скопируйте свой ввод перед закрытием формы.':'Сведения обновлены. Ваш ввод сохранён; проверьте его и повторите сохранение.';
  }catch(error){if(form.isConnected&&formDialog.open)directionError(error,form);}
  finally{if(form.isConnected)directionBusy(false);}
 };
 formDialog.classList.remove('reading-document');
 if(!formDialog.open)formDialog.showModal();
 formDialog.scrollTop=0;
 form.querySelector('input:not([type="hidden"]),select,textarea')?.focus();
}

function projectsServicesHTML(project){
 return `<section class="project-section"><div class="project-section-heading"><div><h2>Ресурсы проекта <span>${(project.resources||[]).length}</span></h2><p>Рекомендации, использование через Codex и интеграции в приложение.</p></div><div><button class="secondary-button" id="project-resource-add">Назначить ресурс</button><button class="quiet-button" id="project-services-open">Посмотреть доступность</button></div></div>${(project.resources||[]).map(item=>`<article class="project-record"><h3><button class="project-skill-link" data-project-resource="${esc(item.id)}">${esc(item.name)}</button></h3><p><strong>${esc(resourceRoles[item.role]||'Рекомендован')}</strong></p><p>${esc(item.purpose)}</p><p class="small-note">${esc(connectionPolicies[item.policy]||'Правило не определено')}${item.evidence?' · Основание: '+esc(item.evidence):''}</p><button class="quiet-button" data-project-resource-edit="${esc(item.id)}">Изменить назначение</button></article>`).join('')||'<p class="project-empty">Назначений пока нет. Добавьте ресурс для задач проекта.</p>'}</section>`;
}
