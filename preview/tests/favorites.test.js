import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import * as model from '../web/model.js';

// Load the actual page and handlers. No duplicate routing/filter implementation.
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
const source=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8')
 .replace(/^import .*;\r?$/gm,'').replace(/\nload\(\);\s*$/,'');
const part=(id,kind='skill',project)=>({id,kind,name:id,installed:true,enabled:true,
 scope:project?'local':'global',...(project?{project_ids:[project]}:{})});
const addon=(id,components,favorite=false)=>({id,title:id,description:id,components,favorite,
 directions:['design'],tags:[],origin:'personal',billing:'free',notes:[],skills:[],related:[],bindings:[]});
function fixture(t,{hash='#all',stored='false'}={}){
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8772/'+hash});
 t.after(()=>dom.window.close());
 dom.window.scrollTo=()=>{};
 dom.window.localStorage.setItem('catalog-favorites-only',stored);
 const requests=[],snapshot={version:'test',updated_at:'2026-10-28T12:00:00Z',legacy_url:'http://127.0.0.1:8768',
  projects:[{id:'zoo',name:'Zoo',path:'C:/Zoo'},{id:'other',name:'Other',path:'C:/Other'}],
  directions:[{id:'design',title:'Дизайн'}],overlay:{revision:1,items:{excluded:{favorite:false}}},
  addons:[addon('global',[part('g')],true),addon('local-zoo',[part('z','skill','zoo')],true),
   addon('local-other',[part('o','skill','other')],true),addon('bundle',[part('bs'),part('bm','mcp')],true),
   addon('ordinary',[part('n')]),addon('excluded',[part('e')],true)]};
 const context={...model,window:dom.window,document:dom.window.document,location:dom.window.location,
  history:dom.window.history,localStorage:dom.window.localStorage,URLSearchParams,URL,AbortSignal,
  setTimeout:dom.window.setTimeout.bind(dom.window),clearTimeout:dom.window.clearTimeout.bind(dom.window),
  matchMedia:()=>({matches:false}),selectSettingsProject(){},
  fetch:async(url,options)=>{
   const body=JSON.parse(options.body);requests.push({url,body});
   assert.equal(url,'/api/annotate');assert.equal(body.action,'favorite');
   snapshot.overlay={...snapshot.overlay,revision:snapshot.overlay.revision+1,
    items:{...snapshot.overlay.items,[body.id]:{favorite:body.value}}};
   return {ok:true,json:async()=>snapshot.overlay};
  }};
 vm.createContext(context);vm.runInContext(source,context);
 context.snapshot=snapshot;vm.runInContext('data=snapshot;parseRoute();renderPage();',context);
 const doc=dom.window.document;
 const click=selector=>{const element=doc.querySelector(selector);assert.ok(element,selector);element.click();};
 const ids=()=>Array.from(doc.querySelectorAll('#grid [data-addon]'),el=>el.dataset.addon).sort();
 const route=async hash=>{const changed=new Promise(resolve=>dom.window.addEventListener('hashchange',resolve,{once:true}));dom.window.location.hash=hash;await changed;};
 return {dom,context,doc,click,ids,route,requests};
}

test('favorites combines with multiple types, project scope and name; all types preserves favorites',async t=>{
 const f=fixture(t);f.click('#favorite-filter');
 assert.equal(f.doc.querySelector('#favorite-filter').getAttribute('aria-pressed'),'true');
 assert.deepEqual(f.ids(),['bundle','global','local-other','local-zoo']);
 f.click('[data-type=mcp]');f.click('[data-type=skill]');assert.deepEqual(f.ids(),['bundle']);
 await f.route('#project=zoo');assert.deepEqual(f.ids(),['bundle']);
 f.click('[data-type=all]');assert.deepEqual(f.ids(),['bundle','global','local-zoo']);
 f.click('[data-multi-filter=scope][value=local]');assert.deepEqual(f.ids(),['local-zoo']);
 const search=f.doc.querySelector('#search');search.value='not found';search.dispatchEvent(new f.dom.window.Event('input'));
 assert.deepEqual(f.ids(),[]);assert.equal(f.doc.querySelector('#favorite-count').textContent,'0');
});

test('favorite mode survives all/project/guide navigation and browser reload',async t=>{
 const f=fixture(t);f.click('#favorite-filter');
 await f.route('#project=zoo');assert.deepEqual(f.ids(),['bundle','global','local-zoo']);
 await f.route('#project=other');assert.deepEqual(f.ids(),['bundle','global','local-other']);
 await f.route('#page=guide');await f.route('#all');
 assert.equal(f.doc.querySelector('#favorite-filter').getAttribute('aria-pressed'),'true');
 const reloaded=fixture(t,{hash:'#project=zoo',stored:f.dom.window.localStorage.getItem('catalog-favorites-only')});
 assert.deepEqual(reloaded.ids(),['bundle','global','local-zoo']);
 reloaded.click('#favorite-filter');
 await reloaded.route('#all');assert.equal(reloaded.doc.querySelector('#favorite-filter').getAttribute('aria-pressed'),'false');
 assert.ok(reloaded.ids().includes('ordinary'));
});

test('sidebar shortcut enables the same filter; switching off leaves the favorite route consistently',async t=>{
 const f=fixture(t);await f.route('#page=favorites');
 assert.equal(f.doc.querySelector('#favorite-filter').getAttribute('aria-pressed'),'true');
 assert.equal(f.dom.window.localStorage.getItem('catalog-favorites-only'),'true');
 f.click('#favorite-filter');
 assert.equal(f.dom.window.location.hash,'#all');assert.equal(f.doc.querySelector('h1').textContent,'Весь Codex');
 assert.equal(f.doc.activeElement.id,'favorite-filter');
 assert.equal(f.dom.window.localStorage.getItem('catalog-favorites-only'),'false');
});

test('reset clears filtering even in an empty favorites view without removing stars',async t=>{
 const f=fixture(t,{hash:'#page=favorites'});f.click('[data-type=program]');assert.deepEqual(f.ids(),[]);
 f.click('#empty-reset');
 assert.equal(f.doc.querySelector('#favorite-filter').getAttribute('aria-pressed'),'false');
 assert.equal(f.dom.window.location.hash,'#all');assert.equal(f.ids().length,6);
 assert.equal(f.doc.querySelector('[data-favorite=global]').getAttribute('aria-pressed'),'true');
 assert.deepEqual(f.requests,[]);
 await f.route('#project=zoo');f.click('#favorite-filter');f.click('#reset-filters');
 assert.equal(f.dom.window.location.hash,'#project=zoo');assert.ok(f.ids().includes('ordinary'));
});

test('unmarking a card updates results and count immediately and persists through navigation',async t=>{
 const f=fixture(t);f.click('#favorite-filter');
 f.click('[data-favorite=global]');await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(f.ids(),['bundle','local-other','local-zoo']);
 assert.equal(f.doc.querySelector('#favorite-count').textContent,'3');
 assert.equal(f.requests.length,1);assert.equal(f.requests[0].body.value,false);
 await f.route('#project=zoo');assert.deepEqual(f.ids(),['bundle','local-zoo']);
 assert.equal(f.doc.querySelector('#favorite-count').textContent,'2');
});

test('favorite toggle is named, independent of type selection, and retains focus',t=>{
 const f=fixture(t),button=f.doc.querySelector('#favorite-filter');
 assert.equal(button.closest('[aria-label="Состав надстройки"]'),null);
 assert.match(button.textContent,/Избранное/);assert.equal(button.type,'button');
 button.focus();button.click();assert.equal(f.doc.activeElement,button);
 assert.equal(f.doc.querySelector('[data-type=all]').getAttribute('aria-pressed'),'true');
 assert.equal(f.doc.querySelector('#favorite-count').textContent,'4');
});
