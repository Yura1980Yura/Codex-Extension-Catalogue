export function skillManagementHTML(parts,esc,explain=true){
 const skills=parts.filter(c=>c.kind==='skill'&&c.path);
 return skills.map(c=>{
  const actions=`${c.file_actions?.remove?`<button type="button" class="secondary danger" data-remove-skill="${esc(c.id)}">Удалить навык из Codex…</button>`:''}${c.file_actions?.install?`<button type="button" class="secondary" data-install-skill="${esc(c.id)}">Подключить навык…</button>`:''}`;
  const reason=explain&&!c.file_actions?.remove&&(c.installed||c.managed_package)?`<p class="tiny">${esc(c.file_actions?.reason||'Удаление этой установки через каталог не поддерживается.')}</p>`:'';
  return actions||reason?`<div class="skill-management">${actions?`<div class="links">${actions}</div>`:''}${reason}</div>`:'';
 }).join('');
}

export function removedSkillsHTML(items,esc){
 if(!items?.length)return '';
 return `<section class="section"><h2>Удалённые инструкции навыков</h2><p>Папки, вспомогательные файлы и другие навыки сохранены. Восстановление возвращает только исходный SKILL.md и не заменяет существующий файл.</p>${items.map(item=>`<article class="page-note"><strong>${esc(item.name)}</strong><code class="source-path">${esc(item.source)}</code><p>${item.status==='restored'?'Инструкция восстановлена':item.status==='cancelled'?'Удаление было отменено':'Инструкция сохранена в резервной копии'}</p>${['removed','prepared'].includes(item.status)?`<button class="secondary" data-restore-skill="${esc(item.operation_id)}">Восстановить навык…</button>`:''}</article>`).join('')}</section>`;
}

export function bindSkillFileTools(ctx){
 const {data,addon,parts,api,esc,readPanel,toast,acceptState,closeReader}=ctx;
 for(const button of document.querySelectorAll('[data-copy-path]'))button.onclick=async()=>{try{await navigator.clipboard.writeText(button.dataset.copyPath);toast('Путь скопирован.');}catch{toast('Не удалось скопировать путь.');}};
 for(const button of document.querySelectorAll('[data-reveal-skill]'))button.onclick=async()=>{button.disabled=true;try{await api('reveal-skill',{id:addon.id,component_id:button.dataset.revealSkill});toast('Папка навыка открыта.');}catch(e){toast(e.message);}finally{button.disabled=false;}};
 const preview=async(action,componentId,projectId,operationId)=>{
  const payload=action==='restore'?{action,operation_id:operationId}:{id:addon.id,component_id:componentId,action,project_id:projectId||null};
  try{
   const plan=await api('skill-plan',payload);
   const removing=action==='remove',restoring=action==='restore';
   const warning=removing?`<p class="soft-note amber skill-removal-warning" role="note"><strong>Удалить этот навык из Codex?</strong> «${esc(plan.name)}» перестанет обнаруживаться по выбранной инструкции. Сначала проверьте файл и область ниже. До нажатия кнопки удаления ничего не изменится.</p>`:'';
   readPanel(removing?'Удалить выбранный навык из Codex':restoring?'Восстановить навык':'Подключить найденный навык',`${warning}<p><strong>${esc(plan.name)}</strong></p><p>${esc(plan.description)}</p><p>Область: ${esc(plan.target)}</p><p>${removing?'Будет удалён только этот файл:':restoring?'Резервная инструкция:':'Исходная папка:'}</p><code class="source-path">${esc(plan.source)}</code>${plan.destination?`<p>${restoring?'Восстановить в исходный файл:':'Папка установки:'}</p><code class="source-path">${esc(plan.destination)}</code>`:'<p>Папка навыка, скрипты, шаблоны, справочные материалы и вложенные навыки сохраняются. Удаляется только выбранный SKILL.md; остальные установки с таким именем остаются доступными.</p><p>Резервная копия инструкции сохранится отдельно от источников Codex. Восстановить её можно в разделе «История».</p>'}<p>Затрагиваемых файлов: ${plan.files}.</p><p>Открытые чаты могут сохранять прежнее состояние до перезапуска Codex. После операции нажмите «Сверить с Codex». ${removing?'':'Навык попадёт в основной список только после подтверждения Codex.'}</p><div class="links"><button class="${removing?'primary danger':'primary'}" id="confirm-skill-operation">${removing?'Удалить только этот SKILL.md':restoring?'Восстановить этот SKILL.md':'Подтвердить установку'}</button><button class="secondary" id="cancel-skill-operation">Отмена</button></div><p class="error" id="skill-operation-error" role="alert"></p>`);
   document.querySelector('#cancel-skill-operation').onclick=closeReader;
   document.querySelector('#confirm-skill-operation').onclick=async e=>{
    e.currentTarget.disabled=true;
    try{
     const response=await api('skill-change',{...payload,revision:plan.revision,confirmed:true});
     await closeReader();acceptState(response.state);
     toast(removing?'Удалён только SKILL.md. Остальные файлы сохранены. Восстановление — в «Истории».':restoring?'Инструкция восстановлена. Нажмите «Сверить с Codex».':'Файлы установлены. Нажмите «Сверить с Codex» для подтверждения доступности.');
    }catch(error){document.querySelector('#skill-operation-error').textContent=error.message;e.currentTarget.disabled=false;}
   };
  }catch(error){toast(error.message);}
 };
 for(const button of document.querySelectorAll('[data-remove-skill]'))button.onclick=()=>preview('remove',button.dataset.removeSkill);
 for(const button of document.querySelectorAll('[data-restore-skill]'))button.onclick=()=>preview('restore',null,null,button.dataset.restoreSkill);
 for(const button of document.querySelectorAll('[data-install-skill]'))button.onclick=()=>{
  const c=parts.find(c=>c.id===button.dataset.installSkill);
  readPanel('Куда подключить навык',`<p>${esc(c.title||c.name)}</p><p>Прочитайте инструкцию и проверьте её требования перед установкой. Копируется весь локальный комплект; код навыка не запускается.</p><label for="skill-target">Область установки</label><select id="skill-target"><option value="">Лично · все проекты</option>${data.projects.filter(p=>p.available).map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select><div class="links"><button class="primary" id="preview-skill-install">Посмотреть установку</button></div>`);
  document.querySelector('#preview-skill-install').onclick=()=>preview('install',c.id,document.querySelector('#skill-target').value);
 };
}
