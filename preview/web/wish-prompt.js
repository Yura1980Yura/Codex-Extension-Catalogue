import {showDialog,closeDialog} from './dialog.js';

const requests=new WeakMap();

// A separate dialog leaves any unsaved comment in the underlying card intact.
export async function showWishPrompt({document,api,id,isCurrent=()=>true,copyText=text=>navigator.clipboard.writeText(text)}){
 let dialog=document.querySelector('#wish-prompt-dialog');
 if(!dialog){
  dialog=document.createElement('dialog');dialog.id='wish-prompt-dialog';dialog.setAttribute('aria-labelledby','wish-prompt-title');
  dialog.innerHTML=`<header><h2 id="wish-prompt-title">Поручение для Codex</h2><button class="icon-button" aria-label="Закрыть поручение" autofocus>×</button></header><div class="wish-prompt-body"><p id="wish-prompt-name"></p><p class="tiny">Прочитайте запрос, скопируйте его и вставьте в чат нужного проекта Codex. Дополнительные пожелания можно дописать в чате перед отправкой.</p><label for="wish-prompt-text">Готовый текст поручения</label><textarea id="wish-prompt-text" readonly spellcheck="false" aria-describedby="wish-prompt-note"></textarea><p id="wish-prompt-note" class="tiny">Копирование не запускает работу и не меняет состояние карточки. После работы откройте «Пожелания» и нажмите «Обновить список».</p><div class="wish-prompt-footer"><button class="primary" id="wish-prompt-copy" disabled>Скопировать поручение для Codex</button><button class="secondary" id="wish-prompt-retry" hidden>Повторить подготовку</button></div><p id="wish-prompt-status" role="status"></p><p class="error" id="wish-prompt-error" role="alert"></p></div>`;
  document.body.append(dialog);
  const close=()=>{requests.delete(dialog);closeDialog(dialog,true);};
  dialog.querySelector('header button').onclick=close;
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  let outside=false;
  const isOutside=e=>{const r=dialog.getBoundingClientRect();return e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom;};
  dialog.addEventListener('pointerdown',e=>{outside=e.target===dialog&&isOutside(e);});
  dialog.addEventListener('click',e=>{if(outside&&e.target===dialog&&isOutside(e))close();outside=false;});
 }
 const $=s=>dialog.querySelector(s),request={};requests.set(dialog,request);
 const active=()=>requests.get(dialog)===request&&dialog.open&&isCurrent();
 $('#wish-prompt-name').textContent=id;$('#wish-prompt-text').value='';$('#wish-prompt-copy').disabled=true;
 $('#wish-prompt-retry').hidden=true;$('#wish-prompt-status').textContent='Готовим поручение из сохранённой карточки…';$('#wish-prompt-error').textContent='';
 showDialog(dialog,true);
 $('#wish-prompt-retry').onclick=()=>showWishPrompt({document,api,id,isCurrent,copyText});
 try{
  const value=await api('backlog',{action:'prompt',id});if(!active())return;
  $('#wish-prompt-name').textContent=`${value.id} · ${value.title} · ${value.state}`;
  $('#wish-prompt-text').value=value.prompt;$('#wish-prompt-copy').disabled=false;$('#wish-prompt-status').textContent='Текст готов. Проверьте его перед копированием.';
  $('#wish-prompt-copy').onclick=async()=>{
   const button=$('#wish-prompt-copy');button.disabled=true;$('#wish-prompt-error').textContent='';
   try{await copyText($('#wish-prompt-text').value);if(active())$('#wish-prompt-status').textContent='Поручение скопировано. Вставьте его в нужный чат Codex и отправьте.';}
   catch{if(active()){const field=$('#wish-prompt-text');field.focus();field.select();$('#wish-prompt-status').textContent='';$('#wish-prompt-error').textContent='Браузер не разрешил копирование. Текст выделен: нажмите Ctrl+C и вставьте его в Codex.';}}
   finally{if(active())button.disabled=false;}
  };
 }catch(error){if(active()){$('#wish-prompt-status').textContent='';$('#wish-prompt-error').textContent=error.message;$('#wish-prompt-retry').hidden=false;}}
 return dialog;
}
