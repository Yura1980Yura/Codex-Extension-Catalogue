import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {callsFor,promptMenuHTML,bindPromptMenus} from '../web/invocations.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const skill={id:'s',name:'code-analysis-ensemble',default_prompt:'Используй $code-analysis-ensemble: авторский текст.',prompts:[{title:'От автора','text':'Ещё один авторский промпт'}]};
const component={id:'c',kind:'skill',name:skill.name,skill_id:'s',installed:true,enabled:true};
const addon={id:'a',title:'Анализ',skills:[skill],components:[component],profile:{example:'Готовый пример'}};
const settle=()=>new Promise(setImmediate);

test('all authored prompts and examples survive alongside useful task scenarios without duplicates',()=>{
 const rows=callsFor(addon,[component]);
 assert.equal(rows[0].text,skill.default_prompt);
 for(const text of [skill.default_prompt,skill.prompts[0].text,addon.profile.example])assert.equal(rows.filter(r=>r.text===text).length,1);
 assert.ok(rows.some(r=>r.title==='Найти причину ошибки'));
 assert.ok(rows.some(r=>r.title==='Сравнить версии'));
 assert.ok(rows.some(r=>r.title==='Исправить и проверить'));
 assert.equal(new Set(rows.map(r=>r.text)).size,rows.length);
 assert.equal(callsFor(addon,[component,component]).filter(r=>r.title==='Основной вызов автора').length,1);
});
test('MCP, plugins, apps and programs receive actual natural-language prompts, never fictional skill commands',()=>{
 for(const kind of ['mcp','plugin','app','program']){
  const rows=callsFor({id:'a',title:'Подключение',skills:[]},[{id:kind,kind,name:'Example',installed:true,enabled:false}]);
  assert.equal(rows.length,2);assert.ok(rows.every(r=>!r.text.includes('$Example')));
  assert.match(rows[0].text,/Example/);assert.match(rows[0].text,/\[описание\]/);assert.match(rows[0].note,/отключена/);
 }
});
test('plugin skills are qualified and each selected skill has only its own calls',()=>{
 const one={id:'plugin:pdf@runtime:pdf',name:'pdf'},two={id:'plugin:other@runtime:pdf',name:'pdf'};
 const parts=[{...component,id:'one',name:'pdf',skill_id:one.id},{...component,id:'two',name:'pdf',skill_id:two.id}];
 const rows=callsFor({title:'PDF',skills:[one,two]},parts,{skillId:one.id});
 assert.match(rows[0].text,/\$pdf:pdf/);assert.equal(rows.some(r=>r.text.includes('$other:pdf')),false);
});
test('Meshy templates retain the required paid-operation agreement without running a service',()=>{
 const rows=callsFor({id:'resource:meshy',title:'Meshy',skills:[]},[{kind:'mcp',name:'Meshy'}]);
 assert.ok(rows.every(r=>r.text.includes('лимит кредитов')));
});
test('the visible choice is copied exactly; opening and choosing do not copy or execute',async t=>{
 const rows=callsFor(addon,[component]),dom=new JSDOM(promptMenuHTML(rows,esc));t.after(()=>dom.window.close());
 const doc=dom.window.document,copied=[];bindPromptMenus(doc.body,{copy:async text=>copied.push(text)});
 const menu=doc.querySelector('details');menu.open=true;
 assert.deepEqual(copied,[]);const options=doc.querySelectorAll('[data-invocation-option]');options[2].click();
 const preview=doc.querySelector('textarea');assert.equal(preview.value,rows[2].text);assert.deepEqual(copied,[]);
 doc.querySelector('.invocation-copy').click();await settle();assert.deepEqual(copied,[preview.value]);
 assert.match(doc.querySelector('[role=status]').textContent,/скопирован/);
});
test('unsafe metadata is escaped and clipboard failure leaves selectable text in the same menu',async t=>{
 const rows=[{title:'<img onerror=bad>',text:'<script>bad</script> " &',source:'<b>source</b>',component:'x',kind:'skill',note:''}];
 const dom=new JSDOM(promptMenuHTML(rows,esc));t.after(()=>dom.window.close());const doc=dom.window.document;
 bindPromptMenus(doc.body,{copy:async()=>{throw Error('denied');}});
 doc.querySelector('details').open=true;
 doc.querySelector('.invocation-copy').click();await settle();
 assert.equal(doc.querySelectorAll('script,img,b').length,0);assert.equal(doc.querySelector('textarea').value,rows[0].text);
 assert.match(doc.querySelector('[role=status]').textContent,/Ctrl\+C/);assert.equal(doc.activeElement,doc.querySelector('textarea'));
});
test('repeat clicks while copying are blocked and a late failure cannot move focus to a detached menu',async t=>{
 const dom=new JSDOM(promptMenuHTML(callsFor(addon,[component]),esc));t.after(()=>dom.window.close());const doc=dom.window.document;
 let reject,calls=0;bindPromptMenus(doc.body,{copy:()=>{calls++;return new Promise((_,r)=>reject=r);}});
 const button=doc.querySelector('.invocation-copy');button.click();button.click();assert.equal(calls,1);
 doc.body.innerHTML='<input id="new">';doc.querySelector('input').focus();reject(Error('denied'));await settle();
 assert.equal(doc.activeElement.id,'new');
});
