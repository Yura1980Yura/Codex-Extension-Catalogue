import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {JSDOM} from 'jsdom';
import {reorderIds} from '../web/model.js';

// Exercise the actual UI handlers, including the saved full order with hidden tiles.
const source=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8');
const handlers=source.slice(source.indexOf('function fullOrder('),source.indexOf('function reconciliationHTML('));
function fixture(){
 const order=['a','hidden','b','c','d','e','f'];
 const rows=order.filter(id=>id!=='hidden').map(id=>({addon:{id}}));
 const dom=new JSDOM('<main><div id="grid">'+rows.map(({addon:{id}})=>`<article class="addon" data-addon="${id}"><button data-drag="${id}"></button><button data-move="${id}" data-step="-1"></button><button data-move="${id}" data-step="1"></button></article>`).join('')+'</div></main>');
 const requests=[],context={document:dom.window.document,sortMode:'custom',dragged:null,orderSaving:false,
  data:{addons:order.map(id=>({id})),overlay:{revision:1,orders:{project:order}}},filters:{project:'project'},
  reorderIds,project:()=>({name:'Project'}),$:selector=>dom.window.document.querySelector(selector),paintGrid(){},toast(){},
  api:async(path,body)=>{requests.push({path,body});return {revision:2,orders:{project:body.order}};}};
 vm.createContext(context);vm.runInContext(handlers,context);context.bindOrdering(rows);
 return {context,requests,document:dom.window.document,order};
}

for(const [moving,target] of [['a','b'],['b','a'],['a','f'],['f','a'],['c','e'],['e','c']]){
 test(`drag ${moving} onto ${target} exchanges only these tiles and saves the project order`,async()=>{
  const {context,requests,document,order}=fixture();
  const handle=document.querySelector(`[data-drag="${moving}"]`),card=document.querySelector(`[data-addon="${target}"]`);
  const transfer={setData(){}};handle.ondragstart({dataTransfer:transfer});
  let permitted=false;card.ondragover({preventDefault(){permitted=true;},dataTransfer:transfer});
  assert.equal(permitted,true);assert.equal(card.classList.contains('drop-target'),true);
  card.ondrop({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length,1);assert.equal(requests[0].path,'order');assert.equal(requests[0].body.context,'project');
  const expected=reorderIds(order,moving,target);assert.deepEqual(Array.from(requests[0].body.order),expected);
  assert.equal(expected[1],'hidden');assert.equal(context.dragged,null);assert.equal(context.orderSaving,false);
 });
}

test('arrows use the same exchange operation across filtered-out tiles',async()=>{
 const {requests,document}=fixture();
 document.querySelector('[data-move="a"][data-step="1"]').onclick();await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(Array.from(requests[0].body.order),['b','hidden','a','c','d','e','f']);
});
