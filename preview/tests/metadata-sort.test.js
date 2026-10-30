import test from 'node:test';
import assert from 'node:assert/strict';
import {metadataFor,visible,sortRows} from '../web/model.js';

const addon=(id,added_at)=>({id,title:id,added_at,origin:'builtin',billing:'included',directions:['code'],tags:['source','remove'],components:[{id,kind:'skill',installed:true,enabled:true,scope:'global'}]});
const row=a=>({addon:a,overlay:{},parts:a.components});
test('date sorting is strict in both directions, independent of favorites, with unknown dates last',()=>{
 const rows=[row(addon('unknown',null)),row(addon('old','2026-10-20T12:00:00Z')),row(addon('new','2026-10-30T12:00:00Z')),row(addon('invalid','bad'))];
 rows[1].overlay.favorite=true;
 assert.deepEqual(sortRows(rows,'newest').map(x=>x.addon.id),['new','old','invalid','unknown']);
 assert.deepEqual(sortRows(rows,'oldest').map(x=>x.addon.id),['old','new','invalid','unknown']);
 assert.equal(rows[0].addon.id,'unknown');
});
test('personal values override discovery, legacy extra tags migrate and removed tags cannot reappear',()=>{
 const a=addon('a');
 assert.deepEqual(metadataFor(a,{tags:['extra']}).tags,['source','remove','extra']);
 const overlay={origins:['personal','third_party'],billings:['free','paid'],directions:['design','code'],tags_override:['renamed'],tags:['old-extra']};
 const data={addons:[a],projects:[],overlay:{items:{a:overlay}}};
 for(const filter of [{origin:['third_party']},{billing:['paid']},{direction:['design']},{tag:['renamed']},{query:'renamed'}])assert.equal(visible(data,filter).length,1);
 for(const filter of [{origin:['builtin']},{billing:['included']},{tag:['remove']},{tag:['old-extra']}])assert.equal(visible(data,filter).length,0);
 assert.deepEqual(metadataFor(a,{tags_override:[]}).tags,[]);
});
test('filters still intersect in a project and sorting leaves manual order intact',()=>{
 const a=addon('a','2026-10-20T12:00:00Z'),b=addon('b','2026-10-30T12:00:00Z');
 const data={addons:[a,b],projects:[{id:'p'}],overlay:{items:{a:{origins:['personal'],tags_override:['chosen']}}}};
 const filtered=visible(data,{project:'p',origin:['personal'],tag:['chosen'],types:['skill']});
 assert.deepEqual(sortRows(filtered,'newest').map(x=>x.addon.id),['a']);
 assert.deepEqual(sortRows([row(a),row(b)],'custom',['b','a']).map(x=>x.addon.id),['b','a']);
});
