import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import * as model from '../web/model.js';
import * as activationUI from '../web/activation-ui.js';

const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const source=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8')
 .replace(/^import .*;\r?$/gm,'').replace(/\nload\(\);\s*$/,'');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const part=(id,kind='skill',supported=true)=>({id,kind,name:id,installed:true,enabled:true,scope:'global',
 control:{supported,enabled:true,revision:'initial'}});
const addon=(id,components)=>({id,title:id,description:id,components,favorite:false,directions:[],tags:[],
 origin:'personal',billing:'free',notes:[],skills:[],related:[],bindings:[]});
function fixture(t,{hash='#all',fail=false}={}){
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8772/'+hash});t.after(()=>dom.window.close());
 dom.window.scrollTo=()=>{};
 const snapshot={version:'test',updated_at:'2026-10-29',legacy_url:'http://127.0.0.1:8768',
  projects:[{id:'zoo',name:'Zoo',path:'C:/Zoo'}],directions:[],documents:[],events:[],overlay:{revision:1,items:{}},
  addons:[addon('design',[part('skill:design')]),addon('blender',[part('mcp:blender','mcp'),part('skill:blender')]),
   addon('pdf',[part('plugin:pdf','plugin'),part('skill:pdf','skill',false)]),addon('managed',[part('plugin:managed','plugin',false)])]};
 const requests=[];let finish;
 const ctx={...model,...activationUI,window:dom.window,document:dom.window.document,location:dom.window.location,
  history:dom.window.history,localStorage:dom.window.localStorage,URLSearchParams,URL,AbortSignal,
  setTimeout:dom.window.setTimeout.bind(dom.window),clearTimeout:dom.window.clearTimeout.bind(dom.window),
  matchMedia:()=>({matches:false}),selectSettingsProject(){},renderGuide(){},
  fetch:async(url,options)=>{
   if(!options.body)return {ok:true,json:async()=>structuredClone(snapshot)};
   const body=JSON.parse(options.body);requests.push({url,body});
   assert.equal(url,'/api/activation');
   await new Promise(resolve=>finish=resolve);
   if(fail)return {ok:false,json:async()=>({error:'Настройки изменились в другом окне.'})};
   const c=snapshot.addons.find(a=>a.id===body.id).components.find(c=>c.id===body.component_id);
   c.enabled=body.enabled;c.control={...c.control,enabled:body.enabled,revision:'changed'};
   return {ok:true,json:async()=>({state:structuredClone(snapshot),result:{verification:'codex_config_read'}})};
  }};
 vm.createContext(ctx);vm.runInContext(source,ctx);ctx.snapshot=structuredClone(snapshot);
 vm.runInContext('data=snapshot;parseRoute();renderPage();selected="managed";',ctx);
 const doc=dom.window.document;
 const tile=id=>doc.querySelector(`[data-addon="${id}"]`);
 const button=(id,component)=>tile(id).querySelector(component?`[data-activation="${component}"]`:'[data-activation]');
 const route=async hash=>{const event=new Promise(resolve=>dom.window.addEventListener('hashchange',resolve,{once:true}));dom.window.location.hash=hash;await event;};
 return {dom,ctx,doc,tile,button,requests,route,snapshot,finish:async()=>{finish();await settle();}};
}

test('tile switch targets its own addon, waits for confirmation and restores focus without opening a drawer',async t=>{
 const f=fixture(t);const b=f.button('design');b.focus();b.click();
 assert.equal(f.requests.length,1);assert.equal(f.requests[0].body.id,'design');
 assert.equal(f.requests[0].body.component_id,'skill:design');assert.equal(f.requests[0].body.context,'all');
 assert.equal(b.getAttribute('aria-checked'),'true');assert.equal(b.disabled,true);
 assert.equal(b.getAttribute('aria-busy'),'true');assert.match(f.tile('design').textContent,/Сохраняем в Codex/);
 b.click();assert.equal(f.requests.length,1);
 await f.finish();assert.equal(f.button('design').getAttribute('aria-checked'),'false');
 assert.equal(f.doc.activeElement,f.button('design'));assert.equal(f.doc.querySelector('#details').open,false);
 assert.match(f.tile('design').textContent,/Сохранено в Codex и истории/);
 f.button('design').click();await f.finish();assert.equal(f.button('design').getAttribute('aria-checked'),'true');
 assert.deepEqual(f.requests.map(r=>r.body.enabled),[false,true]);
});

test('compound tile controls change only the chosen component and keep the list open',async t=>{
 const f=fixture(t);const menu=f.tile('blender').querySelector('details');menu.open=true;
 const b=f.button('blender','mcp:blender');b.focus();b.click();await f.finish();
 assert.equal(f.tile('blender').querySelector('details').open,true);
 assert.equal(f.button('blender','mcp:blender').getAttribute('aria-checked'),'false');
 assert.equal(f.button('blender','skill:blender').getAttribute('aria-checked'),'true');
 assert.equal(f.doc.activeElement,f.button('blender','mcp:blender'));
 assert.match(f.tile('blender').textContent,/Включена частично/);
});

test('focus returns when the browser blurs a temporarily disabled switch',async t=>{
 const f=fixture(t);const b=f.button('design');b.focus();b.click();
 // jsdom does not reproduce Chrome's automatic blur on disabled buttons.
 f.doc.body.tabIndex=-1;f.doc.body.focus();
 assert.equal(f.doc.activeElement,f.doc.body);await f.finish();
 assert.equal(f.doc.activeElement,f.button('design'));
});

test('a single available plugin control names the part and does not invent a skill switch',async t=>{
 const f=fixture(t);assert.equal(f.tile('pdf').querySelectorAll('[data-activation]').length,1);
 assert.equal(f.tile('pdf').querySelector('details'),null);
 assert.equal(f.tile('pdf').querySelector('.tile-control-label>span').textContent,'Плагин');
 f.button('pdf').click();await f.finish();
 assert.match(f.tile('pdf').querySelector('.addon-state-line').textContent,/отключённые/);
 assert.equal(f.tile('managed').querySelector('[data-activation]'),null);
});

test('failed write displays the error and restores the actual state without false success',async t=>{
 const f=fixture(t,{fail:true});f.button('design').click();await f.finish();
 assert.equal(f.button('design').getAttribute('aria-checked'),'true');
 assert.equal(f.button('design').disabled,false);assert.equal(f.button('design').hasAttribute('aria-busy'),false);
 assert.match(f.tile('design').textContent,/Настройки изменились в другом окне/);
 assert.doesNotMatch(f.tile('design').textContent,/Сохранено в Codex/);
});

test('project and favorite views preserve the activation context',async t=>{
 const f=fixture(t,{hash:'#project=zoo'});
 f.snapshot.overlay.items.design={favorite:true};
 vm.runInContext('data.overlay.items.design={favorite:true};',f.ctx);
 f.doc.querySelector('#favorite-filter').click();assert.equal(f.doc.querySelectorAll('#grid .addon').length,1);
 f.button('design').click();await f.finish();assert.equal(f.requests[0].body.context,'zoo');
 assert.equal(f.button('design').getAttribute('aria-checked'),'false');
 await f.route('#all');assert.equal(f.button('design').getAttribute('aria-checked'),'false');
});

test('late responses keep navigation and do not steal focus',async t=>{
 const f=fixture(t);const old=f.button('design');old.focus();old.click();
 await f.route('#project=zoo');const search=f.doc.querySelector('#search');search.focus();
 assert.equal(f.button('design').disabled,true);f.button('design').click();assert.equal(f.requests.length,1);
 await f.finish();assert.equal(f.dom.window.location.hash,'#project=zoo');
 assert.equal(f.requests[0].body.context,'all');assert.equal(f.doc.activeElement,search);
 assert.equal(f.button('design').getAttribute('aria-checked'),'false');
});

test('switching a tile out of the active enabled filter moves focus to results',async t=>{
 const f=fixture(t);f.doc.querySelector('[data-multi-filter=enabled][value=on]').click();
 const b=f.button('design');b.focus();b.click();await f.finish();
 assert.equal(f.tile('design'),null);assert.equal(f.doc.activeElement.id,'result-count');
});

test('compound list closes on outside click and Escape returns focus to its summary',t=>{
 const f=fixture(t);let menu=f.tile('blender').querySelector('details');menu.open=true;
 f.doc.querySelector('h1').click();assert.equal(menu.open,false);
 menu.open=true;f.button('blender','mcp:blender').focus();
 f.doc.dispatchEvent(new f.dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
 assert.equal(menu.open,false);assert.equal(f.doc.activeElement,menu.querySelector('summary'));
});
