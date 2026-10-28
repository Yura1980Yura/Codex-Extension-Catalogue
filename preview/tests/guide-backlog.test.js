import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {chapters,renderGuide} from '../web/guide.js';
import {renderBacklog,backlogText} from '../web/backlog.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const view=()=>({items:[{id:'BK-2026-012',title:'Анимация',state:'Записано',next_step:'Уточнить',revision:'rev1'}],document:{markdown:'Бэклог'},events:[{kind:'wish_created'}],path:'C:/docs',result:{id:'BK-2026-012'}});
function setup(t,api){
 const dom=new JSDOM('<main></main><section id="reader"></section>',{url:'http://localhost/'});t.after(()=>dom.window.close());
 const host=dom.window.document.querySelector('main'),events=[];
 const ctx={api,esc,markdown:x=>`<p>${esc(x)}</p>`,readPanel:(title,html)=>{dom.window.document.querySelector('#reader').innerHTML=html;},acceptEvents:x=>events.push(x),toast(){}};
 return {dom,host,ctx,events,submit:form=>form.dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}))};
}
test('five chapters, safe local paths, deep links and coverage action',t=>{
 const f=setup(t);const data={addons:[{components:[{kind:'skill',path:'C:/<img src=x onerror=bad>/SKILL.md'}]}]};
 let calls=0;const ctx={data,esc,icon:()=>'',coverage:()=>calls++};
 renderGuide(f.host,{...ctx,hash:'#page=guide'});
 assert.equal(f.host.querySelectorAll('.guide-card').length,5);
 for(const [id] of chapters){
  renderGuide(f.host,{...ctx,hash:`#page=guide&chapter=${id}`});
  assert.equal(f.host.querySelectorAll('h1').length,1);
  assert.equal(f.host.querySelector('[aria-current=page]').hash,`#page=guide&chapter=${id}`);
 }
 renderGuide(f.host,{...ctx,hash:'#page=guide&chapter=entities&topic=mcp'});
 assert.equal(f.host.querySelector('#guide-mcp').open,true);
 assert.equal(f.host.querySelectorAll('img,script').length,0);
 renderGuide(f.host,{...ctx,hash:'#page=guide&chapter=catalog'});
 f.host.querySelector('#guide-coverage').click();assert.equal(calls,1);
 assert.match(f.host.textContent,/Сверка ручная/);
 renderGuide(f.host,{...ctx,hash:'#page=guide&chapter=records&topic=wishes'});
 assert.equal(f.host.querySelector('#guide-wishes').open,true);
});
test('wish is saved to shared backlog and event list; duplicate submit is blocked',async t=>{
 const calls=[];let finish;
 const f=setup(t,async(path,payload)=>{assert.equal(path,'backlog');calls.push(payload);if(payload.action==='create')return new Promise(resolve=>finish=resolve);return view();});
 renderBacklog(f.host,f.ctx);await settle();
 f.host.querySelector('#wish-title').value='Анимация';f.host.querySelector('#wish-text').value='Точная мысль';
 const form=f.host.querySelector('form');f.submit(form);f.submit(form);
 assert.equal(calls.filter(x=>x.action==='create').length,1);
 finish(view());await settle();
 assert.equal(f.host.querySelector('#wish-text').value,'');
 assert.match(f.host.querySelector('#backlog-status').textContent,/BK-2026-012/);
 assert.equal(f.events.length,2);
 assert.equal(f.host.querySelectorAll('.wish-card').length,1);
});
test('failed save retains text and retries with the same request ID',async t=>{
 const requests=[];let fail=true;
 const f=setup(t,async(path,payload)=>{if(payload.action==='create'){requests.push(payload);if(fail)throw Error('Диск недоступен');}return view();});
 renderBacklog(f.host,f.ctx);await settle();
 f.host.querySelector('#wish-title').value='Анимация';f.host.querySelector('#wish-text').value='Исходные слова';
 f.submit(f.host.querySelector('form'));await settle();
 assert.equal(f.host.querySelector('#wish-text').value,'Исходные слова');
 assert.match(f.host.querySelector('.error').textContent,/Диск недоступен/);
 fail=false;f.submit(f.host.querySelector('form'));await settle();
 assert.equal(requests[0].request_id,requests[1].request_id);
});
test('a late response cannot replace another page',async t=>{
 let finish;const f=setup(t,()=>new Promise(resolve=>finish=resolve));
 renderBacklog(f.host,f.ctx);f.host.innerHTML='<h1>Другой раздел</h1>';finish(view());await settle();
 assert.equal(f.host.textContent,'Другой раздел');
});
test('editing uses document revision and retains comment on conflict',async t=>{
 const f=setup(t,async(path,p)=>{if(p.action==='read')return {markdown:'Исходная формулировка',revision:'rev1'};if(p.action==='update'){assert.equal(p.revision,'rev1');throw Error('Карточка изменилась');}return view();});
 renderBacklog(f.host,f.ctx);await settle();f.host.querySelector('[data-wish]').click();await settle();
 const form=f.dom.window.document.querySelector('#wish-update');form.querySelector('textarea').value='Мой комментарий';f.submit(form);await settle();
 assert.equal(form.querySelector('textarea').value,'Мой комментарий');
 assert.match(form.querySelector('.error').textContent,/изменилась/);
});


test('Obsidian aliases do not split backlog table columns or expose raw paths',()=>{
 const text='| Тема | [[vault/project/Бэклог/BK-2026-012|BK-2026-012]] |';
 assert.equal(backlogText(text),'| Тема | BK-2026-012 |');
 assert.equal(backlogText('[[vault/project/REPORT]]'),'REPORT');
 assert.equal(backlogText('[[vault/note|<b>я | ты</b>]]'),String.raw`\<b\>я \| ты\</b\>`);
});
