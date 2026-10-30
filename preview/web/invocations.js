// Prompts are text for a later Codex request. Opening or copying never runs tools.
const kinds={skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение',program:'Программа'};
const tasks={
 'frontend-design':[
  ['Создать экран','Создай интерфейс [назначение экрана] для [пользователи]. Материалы и файлы: [пути или ссылки]. Учти существующий стиль проекта и реализуй результат.'],
  ['Улучшить существующий интерфейс','Улучши интерфейс [экран или компонент]: композицию, типографику, цвет и удобство действий. Файлы и замечания: [укажите]. Сохрани необходимую функциональность и проверь результат.']],
 'animate':[
  ['Добавить анимацию','Добавь анимацию для [компонент и действие]. Цель движения: [что оно помогает понять]. Учти прерывание, закрытие, клавиатуру и уменьшенное движение.'],
  ['Настроить переход панели','Настрой открытие и закрытие [панель или окно] в [файлы проекта]. Движение должно помогать понять действие и корректно реагировать на быстрые повторные нажатия.']],
 'ui-ux-pro-max':[
  ['Проверить удобство интерфейса','Проверь [экран или приложение]: навигацию, читаемость, контраст, работу с клавиатуры и понятность действий. Материалы: [файлы или снимки]. Дай приоритетный список улучшений с объяснениями.']],
 'code-analysis-ensemble':[
  ['Найти причину ошибки','В проекте или программе [путь] найди причину [ошибка и шаги воспроизведения]. Выбери подходящие средства анализа и объясни выводы с подтверждениями.'],
  ['Оценить последствия правки','Для проекта [путь] оцени изменение [описание правки]. Покажи затрагиваемые функции, связи и риски и предложи подходящую проверку.'],
  ['Сравнить версии','Сравни [первый выпуск или папка] и [второй выпуск или папка] по возможности [конкретный вопрос]. Раздели доказанные изменения и оставшиеся неизвестными.'],
  ['Исправить и проверить','В проекте [путь] исправь [конкретная проблема]. Сначала подтверди причину, затем внеси правку, проверь результат и сохрани его в журнале проекта.']],
 'reverse-engineer-anything':[
  ['Разобрать готовую программу','Разбери готовую поставку [файл или пакет] и объясни [конкретная функция или поведение]. Используй подтверждения из этой поставки и сохрани результаты исследования.'],
  ['Сравнить готовые выпуски','Сравни готовые поставки [первая] и [вторая] по функции [вопрос]. Покажи подтверждения, различия и ограничения анализа.']]
};

function skillName(skill,component){
 const name=skill?.name||component?.name||'';
 if(skill?.id?.startsWith('plugin:')&&!name.includes(':'))return skill.id.split(':')[1].split('@')[0]+':'+name;
 return name;
}

export function invocationFor(addons,id){
 const skill=addons.flatMap(a=>a.skills||[]).find(s=>s.id===id);
 const component=addons.flatMap(a=>a.components||[]).find(c=>c.skill_id===id||c.name===id);
 return skill?.default_prompt||`Используй навык $${skillName(skill,component)||id} для моей задачи.`;
}

function published(value){
 if(!Array.isArray(value))return [];
 return value.filter(row=>row&&typeof row.title==='string'&&typeof row.text==='string'&&row.text.trim());
}

export function callsFor(addon,parts,{skillId,examplesOnly=false}={}){
 const rows=[],seen=new Set(),push=(title,text,source,component)=>{
  if(typeof text!=='string'||!text.trim())return;
  if(/meshy/i.test(addon.id+' '+addon.title)&&/каталога$/.test(source))text+='\nПеред платной операцией согласуй со мной задачу, число вариантов, модель и лимит кредитов.';
  if(seen.has(text.trim()))return;
  seen.add(text.trim());rows.push({title,text,source,component:component?.title||component?.name||addon.title,
   kind:component?.kind||'addon',note:component?.installed===false?'Установка не подтверждена.':component?.enabled===false?'Эта часть отключена в Codex.':''});
 };
 const allowed=parts.filter(c=>!skillId||c.skill_id===skillId);
 const selectedSkills=new Set();
 if(!examplesOnly)for(const c of allowed){
  if(c.kind==='skill'){
   if(selectedSkills.has(c.skill_id))continue;
   selectedSkills.add(c.skill_id);
   const skill=(addon.skills||[]).find(s=>s.id===c.skill_id),name=skillName(skill,c);
   if(!name)continue;
   if(skill?.default_prompt)push('Основной вызов автора',skill.default_prompt,'Из пакета навыка',c);
   for(const p of published(skill?.prompts))push(p.title,p.text,'Из пакета навыка',c);
   push('Применить к моей задаче',`Используй навык $${name} для моей задачи.\nЗадача: [опишите, что нужно сделать].\nМатериалы: [файлы, ссылки или текст].`,'Шаблон каталога',c);
   for(const [title,task] of tasks[skill?.name||c.name]||[])push(title,`Используй навык $${name}. ${task}`,'Сценарий каталога',c);
   push('Что подготовить для работы',`Прочитай инструкцию навыка $${name} и объясни, какие материалы нужны для задачи [описание], какие у него ограничения и какой результат я получу.`,'Шаблон каталога',c);
  }else{
   const label=kinds[c.kind]||'Надстройка',name=c.title||c.name||addon.title,withLabel=({plugin:'плагином',app:'приложением',program:'программой',mcp:'подключением MCP'})[c.kind]||'надстройкой';
   const use=c.kind==='program'?`Помоги выполнить задачу [описание] с установленной программой «${name}». Материалы: [файлы или ссылки]. Сначала проверь доступный способ работы с ней в этом чате.`:
    `Для задачи [описание] используй ${label==='MCP'?'подключение MCP':label.toLowerCase()} «${name}». Материалы: [файлы или ссылки]. Сначала проверь доступность в текущем чате; если доступа нет, объясни, что нужно подготовить.`;
   push(c.kind==='program'?'Использовать программу':'Использовать для задачи',use,'Шаблон каталога',c);
   push('Возможности и подготовка',`Объясни, как пользоваться ${withLabel} «${name}» в Codex: для каких задач оно подходит, что подготовить и как начать с моей задачей [описание].`,'Шаблон каталога',c);
  }
 }
 if(!skillId){
  for(const p of published(addon.profile?.prompts))push(p.title,p.text,'Из карточки надстройки');
  const examples=Array.isArray(addon.profile?.example)?addon.profile.example:[addon.profile?.example];
  examples.forEach((text,i)=>push(examples.length>1?'Пример из карточки '+(i+1):'Пример из карточки',text,'Из карточки надстройки'));
  if(!examplesOnly)for(const capability of (Array.isArray(addon.profile?.capabilities)?addon.profile.capabilities:[])){
   if(typeof capability!=='string'||!capability.trim())continue;
   push(capability,`Используй надстройку «${addon.title}» для возможности «${capability}».\nМоя задача: [описание].\nМатериалы: [файлы, ссылки или текст].\nСначала проверь доступность подходящих частей надстройки в текущем чате.`,'Сценарий каталога');
  }
 }
 if(!rows.length&&!skillId&&!examplesOnly)push('Подготовить использование',`Помоги воспользоваться надстройкой «${addon.title}» для задачи [описание]. Объясни необходимые подключения и материалы и сначала проверь её доступность в текущем Codex.`,'Шаблон каталога');
 return rows;
}

export function promptMenuHTML(rows,esc){
 if(!rows.length)return '';
 const first=rows[0];
 return `<details class="invocation-menu"><summary>Скопировать вызов <span class="invocation-count">${rows.length}</span><span aria-hidden="true">⌄</span></summary><div class="invocation-body"><p class="tiny">Выберите задачу, прочитайте промпт и скопируйте его в чат Codex. Заполните места в квадратных скобках.</p><div class="invocation-options" role="group" aria-label="Варианты вызова">${rows.map((r,i)=>`<button type="button" class="invocation-option" data-invocation-option data-prompt-text="${esc(r.text)}" data-prompt-source="${esc(r.source)}" data-prompt-note="${esc(r.note)}" aria-pressed="${i===0}"><strong>${esc(r.title)}</strong><small>${esc((kinds[r.kind]||'Надстройка')+' · '+r.component)}</small></button>`).join('')}</div><p class="tiny invocation-source">${esc(first.source)}</p><p class="tiny invocation-note">${esc(first.note)}</p><label class="invocation-preview">Текст выбранного вызова<textarea readonly rows="5" aria-label="Текст выбранного вызова">${esc(first.text)}</textarea></label><button type="button" class="secondary invocation-copy">Скопировать промпт</button><p class="invocation-result tiny" role="status" aria-live="polite"></p><p class="tiny">Копирование не включает надстройку и не запускает действие.</p></div></details>`;
}

export function bindPromptMenus(host,{copy,toast=()=>{}}){
 for(const menu of host.querySelectorAll('.invocation-menu')){
  menu.addEventListener('toggle',()=>{if(menu.isConnected&&menu.open)host.ownerDocument.querySelectorAll('.invocation-menu[open]').forEach(other=>{if(other!==menu)other.open=false;});});
  const text=menu.querySelector('textarea'),result=menu.querySelector('.invocation-result'),button=menu.querySelector('.invocation-copy');
  menu.querySelectorAll('[data-invocation-option]').forEach(option=>option.onclick=()=>{
   menu.querySelectorAll('[data-invocation-option]').forEach(other=>other.setAttribute('aria-pressed',String(other===option)));
   text.value=option.dataset.promptText;menu.querySelector('.invocation-source').textContent=option.dataset.promptSource;
   menu.querySelector('.invocation-note').textContent=option.dataset.promptNote;result.textContent='';
  });
  button.onclick=async()=>{
   if(button.disabled)return;
   const value=text.value;button.disabled=true;
   try{await copy(value);if(menu.isConnected&&text.value===value){result.textContent='Промпт скопирован. Вставьте его в чат Codex.';toast('Промпт скопирован.');}}
   catch{if(menu.isConnected){result.textContent='Не удалось обратиться к буферу. Выделите текст и скопируйте его вручную: Ctrl+C.';if(menu.open){text.focus();text.select();}}}
   finally{button.disabled=false;}
  };
 }
}
