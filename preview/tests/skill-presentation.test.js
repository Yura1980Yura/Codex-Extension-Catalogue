import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import * as model from '../web/model.js';
import * as activationUI from '../web/activation-ui.js';
import * as invocationUI from '../web/invocations.js';
import * as skillActions from '../web/skill-actions.js';

const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const source=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8').replace(/^import .*;\r?$/gm,'').replace(/\nload\(\);\s*$/,'');

test('copy uses the selected installation prompt; README opens from the known instruction snapshot',async t=>{
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8772/#all'});t.after(()=>dom.window.close());
 dom.window.scrollTo=()=>{};
 const copied=[],requests=[];
 const context={...model,...activationUI,...invocationUI,...skillActions,bindSkillFileTools(){},window:dom.window,document:dom.window.document,location:dom.window.location,history:dom.window.history,
  localStorage:dom.window.localStorage,URLSearchParams,URL,AbortSignal,setTimeout:dom.window.setTimeout.bind(dom.window),clearTimeout:dom.window.clearTimeout.bind(dom.window),
  matchMedia:()=>({matches:true}),openNativeDialog:dialog=>dialog.setAttribute('open',''),closeNativeDialog:dialog=>dialog.removeAttribute('open'),navigator:{clipboard:{writeText:async value=>copied.push(value)}},markdown:text=>text.replaceAll('<','&lt;'),
  fetch:async url=>{requests.push(url);return {ok:true,json:async()=>({text:'Инструкция',path:'C:/skills/example/SKILL.md',documents:{'README.md':{title:'Назначение',text:'Проверенная документация',path:'C:/skills/example/README.md'}}})};}};
 const card=(id,prompt)=>({id,name:'same-name',default_prompt:prompt,documentation:[{id:'README.md',title:'Назначение'}]});
 context.snapshot={addons:[{id:'a',title:'Навык',skills:[card('selected','Используй $same-name: разверни только инфраструктуру.')],components:[{id:'c',kind:'skill',name:'same-name',skill_id:'selected',installed:true,enabled:true,scope:'global'}],notes:[],tags:[],directions:[],bindings:[],related:[],profile:{},origin:'personal'},
  {id:'b',skills:[card('another','Другой вариант')],components:[]}],projects:[],overlay:{revision:0,items:{}}};
 vm.createContext(context);vm.runInContext(source,context);vm.runInContext("data=snapshot;openAddon('a');",context);
 dom.window.document.querySelector('[data-tab="documentation"]').click();
 dom.window.document.querySelector('[data-open-calls]').click();
 dom.window.document.querySelector('.invocation-copy').click();await new Promise(setImmediate);
 assert.deepEqual(copied,['Используй $same-name: разверни только инфраструктуру.']);
 assert.equal(dom.window.document.querySelectorAll('[data-invocation-option]').length,3);
 assert.equal(dom.window.document.querySelector('.invocation-menu>summary').textContent.includes('Скопировать вызов'),true);
 assert.equal(dom.window.document.querySelector('.prompt-dialog .invocation-menu').open,true);
 dom.window.document.querySelector('#reader-close').click();await new Promise(setImmediate);
 dom.window.document.querySelector('[data-instruction="selected"]').click();await new Promise(setImmediate);
 assert.equal(dom.window.document.querySelector('#reader-actions .invocation-menu'),null);
 dom.window.document.querySelector('#reader-close').click();await new Promise(setImmediate);
 vm.runInContext("openAddon('a','sources')",context);
 assert.equal(dom.window.document.querySelector('[data-skill-document]'),null);
 vm.runInContext("openAddon('a','documentation')",context);
 assert.equal(dom.window.document.querySelectorAll('[data-skill-document]').length,1);
 dom.window.document.querySelector('[data-skill-document="selected"]').click();await new Promise(setImmediate);
 assert.deepEqual(requests,['/api/instruction?id=selected','/api/instruction?id=selected']);
 assert.match(dom.window.document.querySelector('#reader-content').textContent,/Проверенная документация/);
 vm.runInContext("copyInvocation('missing-skill')",context);await new Promise(setImmediate);
 assert.equal(copied.at(-1),'Используй навык $missing-skill для моей задачи.');
 context.navigator.clipboard.writeText=async()=>{throw new Error('Clipboard unavailable');};
 vm.runInContext("copyInvocation('selected')",context);await new Promise(setImmediate);
 assert.equal(dom.window.document.querySelector('#reader-content textarea').value,copied[0]);
});
