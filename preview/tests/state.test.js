import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {contentKey,pollDelay,preserveView} from '../web/state.js';

test('manual checks and new timestamps do not create background polling or content changes',()=>{
 const a={job:{state:'done'},updated_at:'one',addons:[{id:'a',components:[{checked_at:'one',enabled:true,observations:[{at:'one',enabled:true}]}]}]};
 const b=structuredClone(a);b.updated_at='two';b.addons[0].components[0].checked_at='two';b.addons[0].components[0].observations[0].at='two';
 assert.equal(contentKey(a),contentKey(b));assert.equal(pollDelay(a),null);
 assert.equal(pollDelay({job:{state:'running'}}),2000);
 b.addons[0].components[0].enabled=false;assert.notEqual(contentKey(a),contentKey(b));
});
test('render preserves an expanded source and scroll position',()=>{
 const dom=new JSDOM('<main><article data-source="one"><details open><summary>Навыки</summary></details></article></main>');
 const host=dom.window.document.querySelector('main'),html=host.innerHTML;let scroll;
 preserveView(host,()=>host.innerHTML=html.replace(' open=""',''),{scrollX:0,scrollY:420,scrollTo(x,y){scroll=[x,y];}});
 assert.equal(host.querySelector('details').open,true);assert.deepEqual(scroll,[0,420]);
});
