import {test} from 'node:test';
import assert from 'node:assert/strict';
import {componentsFor,visible,presence,reorderIds} from '../web/model.js';
const global={id:'s1',kind:'skill',scope:'global',installed:true,enabled:true};
const local={id:'s2',kind:'skill',scope:'local',project_path:'C:/projects/game',installed:true,enabled:true};
const project={id:'game',path:'C:/projects/game'};
const addon={id:'bundle',title:'Bundle',description:'',directions:[],tags:[],components:[global,local,{id:'m',kind:'mcp',scope:'global',installed:true,enabled:true}]};
const data={projects:[project],addons:[addon],overlay:{items:{}}};

test('old project discovery cannot contradict a freshly changed user flag',()=>{
 const x={...addon,components:[{...global,enabled:false,config_authoritative:true,config_changed_at:2000,observations:[{kind:'discovery',cwd:project.path,enabled:true,at:'1970-01-01T00:00:01Z'}]}]};
 assert.equal(componentsFor(x)[0].enabled,false);
 assert.equal(componentsFor(x,project)[0].enabled,null);
 assert.equal(visible({...data,addons:[x]},{project:'game',enabled:'on'}).length,0);
});
test('fresh project discovery can override the user skill flag',()=>{
 const x={...addon,components:[{...global,config_authoritative:true,config_changed_at:2000,observations:[{kind:'discovery',cwd:project.path,enabled:false,at:'1970-01-01T00:00:03Z'}]}]};
 assert.equal(componentsFor(x)[0].enabled,true);
 assert.equal(componentsFor(x,project)[0].enabled,false);
});
test('project inherits globals and gets its own local skill',()=>assert.equal(componentsFor(addon,project).length,3));
test('another project cannot inherit unrelated local skill',()=>assert.equal(componentsFor(addon,{id:'other',path:'C:/projects/other'}).length,2));
test('sibling prefix is not a descendant',()=>assert.equal(componentsFor(addon,{id:'other',path:'C:/projects/game2'}).length,2));
test('a compound extension appears independently under both types',()=>{for(const type of ['skill','mcp'])assert.equal(visible(data,{types:[type]}).length,1);});
test('multiple types require all chosen types',()=>{assert.equal(visible(data,{types:['skill','mcp']}).length,1);assert.equal(visible(data,{types:['skill','plugin']}).length,0);});
test('scope and type refer to the same part',()=>assert.equal(visible(data,{types:['mcp'],scope:'local'}).length,0));
test('project enablement overrides global config without changing all-Codex',()=>{
 const x={...addon,components:[{id:'m',kind:'mcp',contexts:{all:{scope:'global',installed:true,enabled:true},game:{scope:'local',installed:true,enabled:false}}}]};
 assert.equal(componentsFor(x,project)[0].enabled,false);assert.equal(componentsFor(x)[0].enabled,true);
});
test('disabled plugin disables contained skills but retains installation',()=>{
 const x={...addon,components:[global,{id:'p',kind:'plugin',scope:'global',installed:true,enabled:false}]};
 const parts=componentsFor(x);assert.equal(parts[0].enabled,false);assert.equal(presence(parts),'installed');
});
test('suggestions stay separate from installed inventory',()=>{const d={...data,addons:[{...addon,components:[],suggested:true}]};assert.equal(visible(d,{presence:'known'}).length,0);assert.equal(visible(d,{presence:'suggested'}).length,1);});
test('annotations do not confer installation or permissions',()=>{const d={...data,addons:[{...addon,components:[],suggested:true}],overlay:{items:{bundle:{favorite:true,tags:['ready']}}}};assert.equal(visible(d,{presence:'installed'}).length,0);});
test('unconfirmed skill cannot satisfy installed skill plus MCP filter',()=>{
 const d={...data,addons:[{...addon,components:[{...global,installed:false},{id:'m',kind:'mcp',scope:'global',installed:true,enabled:true}]}]};
 assert.equal(visible(d,{presence:'installed',types:['skill','mcp']}).length,0);
 assert.equal(visible(d,{presence:'unconfirmed',types:['skill']}).length,1);
});
test('multiselect is OR within one facet and AND across facets',()=>{
 const d={...data,addons:[{...addon,directions:['design'],origin:'personal',tags:['a']},{...addon,id:'second',directions:['development'],origin:'builtin',tags:['b']}]};
 assert.equal(visible(d,{direction:['design','development']}).length,2);
 assert.equal(visible(d,{direction:['design','development'],origin:['personal']}).length,1);
 assert.equal(visible(d,{scope:['global','local'],types:['mcp'],tag:['a','b']}).length,2);
 assert.equal(visible(d,{scope:['local'],types:['mcp']}).length,0);
 assert.equal(visible(d,{direction:[],scope:[],enabled:[],tag:[]}).length,2);
});
test('reorder retains filtered-out cards and never duplicates an item',()=>{
 assert.deepEqual(reorderIds(['a','hidden','b','c'],'c','a'),['c','a','hidden','b']);
 assert.deepEqual(reorderIds(['a','b'],'unknown','a'),['a','b']);
 assert.deepEqual(reorderIds(['a','b'],'a','a'),['a','b']);
});
