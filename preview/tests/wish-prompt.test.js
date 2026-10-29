import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {showWishPrompt} from '../web/wish-prompt.js';
import {renderBacklog} from '../web/backlog.js';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const value=id=>({id,title:'Моя идея',state:'Записано',prompt:`Поручение ${id}\n</textarea><script>bad()</script>\nТочный текст`});
function setup(t){
 const dom=new JSDOM('<main></main><section id="reader"><textarea id="draft">Не потерять комментарий</textarea></section>');t.after(()=>dom.window.close());
 dom.window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 dom.window.HTMLDialogElement.prototype.close=function(){this.open=false;};
 return {dom,document:dom.window.document};
}
test('preview reads selected card, escapes text and copies exactly the visible prompt',async t=>{
 const f=setup(t),calls=[],copied=[];
 const dialog=await showWishPrompt({...f,id:'BK-2026-004',api:async(path,p)=>{calls.push(p);return value(p.id);},copyText:async text=>copied.push(text)});
 assert.equal(dialog.open,true);assert.equal(dialog.querySelector('script'),null);
 assert.equal(dialog.querySelector('textarea').value,value('BK-2026-004').prompt);
 dialog.querySelector('#wish-prompt-copy').click();await settle();
 assert.deepEqual(copied,[value('BK-2026-004').prompt]);assert.deepEqual(calls,[{action:'prompt',id:'BK-2026-004'}]);
 dialog.querySelector('header button').click();
 assert.equal(dialog.open,false);assert.equal(f.document.querySelector('#draft').value,'Не потерять комментарий');
});
test('clipboard failure preserves selectable text and gives a manual fallback',async t=>{
 const f=setup(t);const dialog=await showWishPrompt({...f,id:'BK-2026-001',api:async()=>value('BK-2026-001'),copyText:async()=>{throw Error('denied');}});
 dialog.querySelector('#wish-prompt-copy').click();await settle();
 const field=dialog.querySelector('textarea');
 assert.match(dialog.querySelector('[role=alert]').textContent,/Ctrl\+C/);
 assert.equal(field.selectionStart,0);assert.equal(field.selectionEnd,field.value.length);
 assert.equal(dialog.querySelector('#wish-prompt-copy').disabled,false);
});
test('cancel during loading cannot reopen a dialog or overwrite a newer selection',async t=>{
 const f=setup(t);let finish;
 const pending=showWishPrompt({...f,id:'BK-2026-001',api:()=>new Promise(resolve=>finish=resolve)});
 const dialog=f.document.querySelector('dialog');dialog.dispatchEvent(new f.dom.window.Event('cancel',{cancelable:true}));
 assert.equal(dialog.open,false);
 await showWishPrompt({...f,id:'BK-2026-002',api:async()=>value('BK-2026-002')});
 finish(value('BK-2026-001'));await pending;
 assert.equal(dialog.querySelector('textarea').value,value('BK-2026-002').prompt);
});
test('unavailable card leaves copy disabled and can be retried',async t=>{
 const f=setup(t);let fail=true;
 const dialog=await showWishPrompt({...f,id:'BK-2026-001',api:async()=>{if(fail)throw Error('Диск недоступен');return value('BK-2026-001');}});
 assert.equal(dialog.querySelector('#wish-prompt-copy').disabled,true);
 assert.match(dialog.querySelector('[role=alert]').textContent,/недоступен/);
 fail=false;dialog.querySelector('#wish-prompt-retry').click();await settle();
 assert.equal(dialog.querySelector('#wish-prompt-copy').disabled,false);
});
test('every list card has handoff and keyboard-accessible help; detail preserves its form',async t=>{
 const f=setup(t),host=f.document.querySelector('main'),ids=['BK-2026-001','BK-2026-002'];
 const api=async(path,p)=>p.action==='load'?{items:ids.map(id=>({id,title:id,state:'Записано',next_step:'Продолжить'})),events:[],document:{markdown:''}}:p.action==='read'?{markdown:'Текст',revision:'rev'}:value(p.id);
 renderBacklog(host,{api,esc:s=>String(s),markdown:s=>s,readPanel:(title,html)=>f.document.querySelector('#reader').innerHTML=html,acceptEvents(){},toast(){}});await settle();
 assert.equal(host.querySelectorAll('[data-wish-prompt]').length,2);
 const help=host.querySelector('.wish-help-button');help.click();assert.equal(help.getAttribute('aria-expanded'),'true');assert.equal(f.document.getElementById(help.getAttribute('aria-controls')).hidden,false);
 help.click();assert.equal(f.document.getElementById(help.getAttribute('aria-controls')).hidden,true);
 host.querySelector('[data-wish]').click();await settle();
 const form=f.document.querySelector('#wish-update');form.querySelector('textarea').value='Черновик';
 f.document.querySelector('#reader [data-wish-prompt]').click();await settle();
 assert.equal(f.document.querySelector('dialog textarea').value,value(ids[0]).prompt);
 f.document.querySelector('dialog header button').click();assert.equal(form.querySelector('textarea').value,'Черновик');
});
