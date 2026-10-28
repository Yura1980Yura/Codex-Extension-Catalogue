const states=['Записано','Разбираем','В работе','Проверено','Отложено'];

// Obsidian's alias separator is not a table column. Show readable labels in
// the browser; keep the original links untouched in the source documents.
export function backlogText(text){
 return String(text||'').replace(/\[\[([^\]\r\n]+)\]\]/g,(_,target)=>{
  const split=target.indexOf('|'),label=split<0?target.split('/').pop():target.slice(split+1);
  return label.replace(/[\\`*_{}\[\]()#+.!|<>]/g,'\\$&');
 });
}

export function renderBacklog(host,{api,esc,markdown,readPanel,acceptEvents,toast}){
 const documentHTML=text=>markdown(backlogText(text));
 host.innerHTML=`<header class="page-heading"><div><h1>Пожелания</h1><p>Единый список идей и будущих задач. Каждая запись сохраняется в бэклоге и истории.</p></div></header><div id="backlog-root"><div class="backlog-toolbar"><button class="secondary" id="backlog-refresh">Обновить список</button><button class="quiet" id="backlog-document" disabled>Документ бэклога</button><a href="#page=guide&chapter=records&topic=wishes">Как это работает</a></div><details class="backlog-new" open><summary>Новое пожелание</summary><form class="note-form" id="wish-form"><label for="wish-title">Короткое название</label><input id="wish-title" required maxlength="140" placeholder="Например, анимация персонажей"><label for="wish-text">Что вы хотите улучшить или получить?</label><textarea id="wish-text" required maxlength="20000" rows="3" placeholder="Опишите своими словами. Этого достаточно, чтобы сохранить идею."></textarea><button class="primary" type="submit">Сохранить пожелание</button><p class="error" role="alert"></p><p class="tiny">Запись сохраняет идею. Выполнение начинается по вашему поручению.</p></form></details><p id="backlog-status" role="status">Читаем бэклог…</p><div id="backlog-list" class="backlog-list"></div></div>`;
 const root=host.querySelector('#backlog-root'),$=selector=>root.querySelector(selector);
 let current=null,request=null,busy=false;
 const alive=()=>host.querySelector('#backlog-root')===root;
 function accept(next){
  current=next;acceptEvents(next.events||[]);
  if(!alive())return;
  $('#backlog-document').disabled=false;
  $('#backlog-status').textContent=`${next.items.length} пожеланий · Общие документы с прежним каталогом`;
  $('#backlog-list').innerHTML=next.items.map(w=>`<article class="page-note wish-card"><div><small>${esc(w.id)}</small><span class="wish-status" data-state="${esc(w.state)}">${esc(w.state)}</span></div><h2><button class="quiet" data-wish="${esc(w.id)}">${esc(w.title)}</button></h2><p>${esc(w.next_step)}</p><button class="secondary" data-wish="${esc(w.id)}">Открыть и дополнить</button></article>`).join('')||'<p class="page-note">Пока нет пожеланий. Запишите первую идею в форме выше.</p>';
  root.querySelectorAll('[data-wish]').forEach(b=>b.onclick=()=>open(b.dataset.wish));
 }
 async function reload(){
  if(busy)return;busy=true;$('#backlog-refresh').disabled=true;
  try{accept(await api('backlog',{action:'load'}));}
  catch(error){if(alive())$('#backlog-status').textContent=error.message;}
  finally{busy=false;if(alive())$('#backlog-refresh').disabled=false;}
 }
 async function open(id){
  try{
   const doc=await api('backlog',{action:'read',id});if(!alive())return;
   const row=current.items.find(x=>x.id===id);if(!row)return;
   readPanel(row.title,`<p class="tiny">${esc(id)} · Исходная формулировка сохраняется</p>${documentHTML(doc.markdown)}<form class="note-form" id="wish-update"><h2>Дополнить пожелание</h2><label for="wish-state">Состояние</label><select id="wish-state">${states.map(s=>`<option ${s===row.state?'selected':''}>${s}</option>`).join('')}</select><label for="wish-step">Следующий шаг</label><input id="wish-step" required maxlength="400" value="${esc(row.next_step)}"><label for="wish-comment">Комментарий</label><textarea id="wish-comment" maxlength="20000" rows="3" placeholder="Что уточнили, решили или проверили"></textarea><p class="tiny">Для отметки «Проверено» опишите результат или укажите отчёт.</p><button class="primary" type="submit">Сохранить изменения</button><p class="error" role="alert"></p><p role="status" class="wish-saved"></p></form>`);
   const form=host.ownerDocument.querySelector('#wish-update');let revision=doc.revision;
   form.onsubmit=async e=>{
    e.preventDefault();const b=form.querySelector('button');b.disabled=true;form.querySelector('.error').textContent='';
    try{
     const next=await api('backlog',{action:'update',id,revision,state:form.querySelector('select').value,next_step:form.querySelector('input').value,comment:form.querySelector('textarea').value});
     accept(next);revision=next.items.find(x=>x.id===id).revision;
     form.querySelector('textarea').value='';form.querySelector('.wish-saved').textContent='Изменения сохранены в карточке, бэклоге и истории.';
     // Reopen from disk so the reader shows the saved comment and state as well.
     await open(id);toast('Пожелание обновлено.');
    }catch(error){form.querySelector('.error').textContent=error.message;}
    finally{b.disabled=false;}
   };
  }catch(error){toast(error.message);}
 }
 $('#backlog-refresh').onclick=reload;
 $('#backlog-document').onclick=()=>{if(current)readPanel('Бэклог навыков',`<p class="path">${esc(current.path)}</p>${documentHTML(current.document.markdown)}`);};
 const form=$('#wish-form');
 form.onsubmit=async e=>{
  e.preventDefault();const b=form.querySelector('button');if(b.disabled)return;b.disabled=true;form.querySelector('.error').textContent='';
  const title=$('#wish-title').value.trim(),text=$('#wish-text').value.trim(),fingerprint=JSON.stringify([title,text]);
  if(!request||request.fingerprint!==fingerprint)request={fingerprint,id:crypto.randomUUID()};
  try{
   const next=await api('backlog',{action:'create',title,text,request_id:request.id});accept(next);
   if(alive()){form.reset();root.querySelector('.backlog-new').open=false;$('#backlog-status').textContent=`${next.result.id}: пожелание сохранено в бэклоге и истории.`;$('#backlog-status').tabIndex=-1;$('#backlog-status').focus();}
   request=null;toast('Пожелание сохранено в бэклоге.');
  }catch(error){if(alive())form.querySelector('.error').textContent=error.message;}
  finally{b.disabled=false;}
 };
 reload();
}
