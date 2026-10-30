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
const settle=()=>new Promise(setImmediate);
function fixture(t,fail=false){
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8772/#all'});t.after(()=>dom.window.close());dom.window.scrollTo=()=>{};
 const addon=(id,date)=>({id,title:id,description:id,added_at:date,origin:'builtin',billing:'included',tags:['initial','remove'],directions:['code'],skills:[],notes:[],related:[],bindings:[],components:[{id:'c-'+id,kind:'skill',name:id,installed:true,enabled:true,scope:'global',source_locations:[{id:'known',path:'C:/skills/example/SKILL.md',available:true,label:'Файл'}]}]});
 const snapshot={updated_at:'2026-10-30T12:00:00Z',addons:[addon('old','2026-10-20T12:00:00Z'),addon('new','2026-10-30T12:00:00Z')],projects:[{id:'zoo',name:'Zoo'}],directions:[{id:'code',title:'Код'},{id:'design',title:'Дизайн'}],overlay:{revision:4,items:{},events:[]},events:[]};
 const requests=[],ctx={...model,...activationUI,...invocationUI,...skillActions,bindSkillFileTools(){},window:dom.window,document:dom.window.document,location:dom.window.location,history:dom.window.history,
  localStorage:dom.window.localStorage,URLSearchParams,URL,AbortSignal,setTimeout:dom.window.setTimeout.bind(dom.window),clearTimeout:dom.window.clearTimeout.bind(dom.window),
  matchMedia:()=>({matches:true}),selectSettingsProject(){},renderGuide(){},openNativeDialog:dialog=>dialog.setAttribute('open',''),closeNativeDialog:dialog=>dialog.removeAttribute('open'),
  fetch:async(url,options)=>{
   const payload=JSON.parse(options.body);requests.push({url,payload});
   if(url==='/api/reveal-source')return {ok:true,json:async()=>({opened:true,foreground:true})};
   if(fail)return {ok:false,json:async()=>({error:'Запись изменилась в другом окне.'})};
   assert.equal(url,'/api/annotate');assert.equal(payload.revision,snapshot.overlay.revision);
   const item=snapshot.overlay.items[payload.id]??={};
   if(payload.action==='metadata')for(const key of ['origins','directions','billings'])item[key]=payload[key];
   if(payload.action==='tags')item.tags_override=payload.text.split(',').map(t=>t.trim()).filter(Boolean);
   snapshot.overlay.revision++;return {ok:true,json:async()=>structuredClone(snapshot.overlay)};
  }};
 vm.createContext(ctx);vm.runInContext(source,ctx);ctx.snapshot=snapshot;
 vm.runInContext('data=snapshot;parseRoute();renderPage();',ctx);
 const doc=dom.window.document,open=()=>vm.runInContext("openAddon('old')",ctx);
 return {dom,ctx,doc,requests,open};
}
test('actual editor saves multiple values, replaces all tags and opens only the known source',async t=>{
 const f=fixture(t);f.open();
 const form=f.doc.querySelector('#metadata-form');
 for(const input of form.querySelectorAll('input'))input.checked=['personal','third_party','free','paid','design'].includes(input.value);
 form.dispatchEvent(new f.dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert.deepEqual(f.requests[0].payload.origins,['personal','third_party']);assert.deepEqual(f.requests[0].payload.billings,['free','paid']);
 assert.match(f.doc.querySelector('.info-grid').textContent,/Мои разработки, Других авторов/);
 assert.equal(f.doc.querySelector('#tags-input').value,'initial, remove');
 f.doc.querySelector('#tags-input').value='initial, renamed';
 f.doc.querySelector('#tags-form').dispatchEvent(new f.dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert.equal(f.doc.querySelector('#tags-input').value,'initial, renamed');assert.doesNotMatch(f.doc.querySelector('.tag-list').textContent,/remove/);
 f.doc.querySelector('[data-tab="sources"]').click();
 f.doc.querySelector('[data-source-folder]').click();await settle();
 assert.deepEqual(f.requests.at(-1),{url:'/api/reveal-source',payload:{id:'old',component_id:'c-old',context:'all',source_id:'known'}});
});

test('one source block owns file paths while removal stays below the single Codex switch',t=>{
 const f=fixture(t),addon=f.ctx.snapshot.addons[0],c=addon.components[0];
 Object.assign(c,{path:'C:/skills/example/SKILL.md',file_actions:{remove:true},control:{supported:true,enabled:true,revision:'r'}});
 f.open();
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path').length,0);
 assert.equal(f.doc.querySelectorAll('[data-remove-skill]').length,1);
 const management=f.doc.querySelector('.drawer-management');
 assert.ok(management.querySelector('[data-activation]'));
 assert.ok(management.querySelector('[data-remove-skill]'));
 assert.ok(management.querySelector('[data-activation]').compareDocumentPosition(management.querySelector('[data-remove-skill]'))&4);
 f.doc.querySelector('[data-tab="sources"]').click();
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-source-folder]').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-copy-path]').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-remove-skill]').length,0);
 f.doc.querySelector('[data-tab="composition"]').click();
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path,#drawer-panel .path').length,0);
 assert.equal(f.doc.querySelectorAll('[data-remove-skill]').length,1);
});

test('shared sources appear once and a removable skill without a supported switch still has management',t=>{
 const f=fixture(t),addon=f.ctx.snapshot.addons[0],c=addon.components[0];
 Object.assign(c,{path:'C:/skills/example/SKILL.md',file_actions:{remove:true},control:{supported:false,message:'Нет выключателя'}});
 addon.components.push({...c,id:'second',name:'second',source_locations:[{id:'same-file',path:'c:\\skills\\example\\SKILL.md',available:true,label:'Настройка Codex'}],file_actions:{},kind:'mcp'});
 f.open();
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-remove-skill]').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path').length,0);
 f.doc.querySelector('[data-tab="sources"]').click();
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-copy-path]').length,1);
 assert.equal(f.doc.querySelectorAll('#drawer-panel [data-remove-skill]').length,0);
 assert.match(f.doc.querySelector('.source-evidence').textContent,/old/);
 assert.match(f.doc.querySelector('.source-evidence').textContent,/second/);
 f.doc.querySelector('[data-tab="composition"]').click();
 const component=f.doc.querySelector('.component');
 assert.match(component.textContent,/Нет выключателя/);
 assert.ok(component.querySelector('[data-remove-skill]'));
 assert.equal(f.doc.querySelectorAll('#drawer-panel .source-path,#drawer-panel .path').length,0);
});
test('conflicting save preserves all selected values and shows the error in the form',async t=>{
 const f=fixture(t,true);f.open();const form=f.doc.querySelector('#metadata-form');
 form.querySelector('[value=paid]').checked=true;
 form.dispatchEvent(new f.dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert.equal(f.doc.querySelector('#metadata-form'),form);assert.equal(form.querySelector('[value=paid]').checked,true);
 assert.match(form.querySelector('.error').textContent,/другом окне/);
});
test('date sort persists while navigating to a project and keeps both date choices available',async t=>{
 const f=fixture(t);const sort=f.doc.querySelector('#sort');sort.value='newest';sort.dispatchEvent(new f.dom.window.Event('change'));
 const ids=()=>[...f.doc.querySelectorAll('#grid [data-addon]')].map(el=>el.dataset.addon);
 assert.deepEqual(ids(),['new','old']);assert.equal(f.dom.window.localStorage.getItem('catalog-sort'),'newest');
 const changed=new Promise(resolve=>f.dom.window.addEventListener('hashchange',resolve,{once:true}));f.dom.window.location.hash='#project=zoo';await changed;
 assert.equal(f.doc.querySelector('#sort').value,'newest');assert.deepEqual(ids(),['new','old']);
 f.doc.querySelector('#sort').value='oldest';f.doc.querySelector('#sort').dispatchEvent(new f.dom.window.Event('change'));assert.deepEqual(ids(),['old','new']);
});
