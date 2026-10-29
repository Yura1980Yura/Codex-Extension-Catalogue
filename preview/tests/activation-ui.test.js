import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {singleControl,headerControlHTML,controlGuidance,controlContextNote,tileControlsHTML} from '../web/activation-ui.js';
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
const part={id:'skill:design',kind:'skill',title:'Дизайн',control:{supported:true,enabled:true}};
test('single component has a labelled on/off control and preserves the project context',()=>{
 const dom=new JSDOM(headerControlHTML([part],esc,'project:zoo'));
 const button=dom.window.document.querySelector('button');
 assert.equal(button.getAttribute('role'),'switch');
 assert.equal(button.getAttribute('aria-checked'),'true');
 assert.equal(button.dataset.context,'project:zoo');
 assert.equal(button.dataset.activation,part.id);
 assert.equal(button.getAttribute('aria-label'),'Использовать в Codex: Дизайн');
 assert.match(button.textContent,/Включено/);dom.window.close();
 const off=new JSDOM(headerControlHTML([{...part,control:{supported:true,enabled:false}}],esc));
 assert.equal(off.window.document.querySelector('button').getAttribute('aria-checked'),'false');
 assert.match(off.window.document.body.textContent,/Отключено/);off.window.close();
});
test('mixed bundles and unsupported skills never get a misleading master switch',()=>{
 for(const parts of [[],[{...part,control:{supported:false}}],[part,{id:'program',kind:'program'}],[part,{...part,id:'other'}]]){
  assert.equal(singleControl(parts),null);assert.equal(headerControlHTML(parts,esc),'');
 }
 assert.match(controlGuidance,/перезапустите Codex/);
 assert.match(controlGuidance,/истории открытого чата/);
});
test('project overrides and stale discovery remain explicit next to the global switch',()=>{
 assert.match(controlContextNote({...part,enabled:false}),/В этом проекте: отключено/);
 assert.equal(controlContextNote({...part,enabled:null,state_note:'Ожидает свежей сверки'}),'Ожидает свежей сверки');
 assert.equal(controlContextNote({...part,enabled:true}),'');
 assert.equal(controlContextNote({...part,enabled:null}),'');
});

test('unavailable parts explain the reason without creating a switch or interpreting markup',t=>{
 const locked={id:'skill:story',title:'<img src=x>',kind:'skill',control:{supported:false,message:'Известная ошибка каталога <script>unsafe</script>'}};
 for(const parts of [[locked],[part,locked]]){
  const dom=new JSDOM(tileControlsHTML(parts,esc));t.after(()=>dom.window.close());const doc=dom.window.document;
  assert.equal(doc.querySelectorAll('[role=switch]').length,parts.length-1);
  assert.ok(doc.querySelector('.control-explanation>summary'));
  assert.match(doc.querySelector('.control-explanation').textContent,/Известная ошибка каталога/);
  assert.equal(doc.querySelectorAll('img,script').length,0);
 }
});
