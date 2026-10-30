import {test} from 'node:test';
import assert from 'node:assert/strict';
import {componentsFor,localProjectsFor,visible,presence,reorderIds} from '../web/model.js';
const global={id:'s1',kind:'skill',scope:'global',installed:true,enabled:true};
const local={id:'s2',kind:'skill',scope:'local',project_path:'C:/projects/game',installed:true,enabled:true};
const project={id:'game',path:'C:/projects/game'};
const addon={id:'bundle',title:'Bundle',description:'',directions:[],tags:[],components:[global,local,{id:'m',kind:'mcp',scope:'global',installed:true,enabled:true}]};
const data={projects:[project],addons:[addon],overlay:{items:{}}};

test('local installation projects exclude inherited globals, findings and unrelated registrations',()=>{
 const projects=[project,{id:'sibling',name:'Sibling',path:'C:/projects/game2'},{id:'other',name:'Other',path:'C:/other'}];
 const x={components:[global,local,{...local,id:'found',installed:false,project_ids:['other']}]};
 const rows=localProjectsFor(x,projects);
 assert.deepEqual(rows.map(row=>row.project.id),['game']);
 assert.deepEqual(rows[0].components.map(c=>c.id),[local.id]);
 assert.deepEqual(localProjectsFor(x,projects.slice(1)),[]);
});

test('local context settings retain disabled installations without labeling global inheritance local',()=>{
 const x={components:[{id:'m',kind:'mcp',contexts:{all:{scope:'global',installed:true,enabled:true},game:{scope:'local',installed:true,enabled:false},other:{scope:'global',installed:true,enabled:true}}}]};
 const rows=localProjectsFor(x,[project,{id:'other',path:'C:/other'}]);
 assert.deepEqual(rows.map(row=>row.project.id),['game']);assert.equal(rows[0].components[0].enabled,false);
});

test('local installation list follows updated project names and ids, not saved catalogue bindings',()=>{
 const x={components:[{id:'s',scope:'local',installed:true,project_ids:['game','other']}],bindings:[{project_name:'Stale'}]};
 const projects=[{...project,name:'Renamed'},{id:'other',name:'Other',available:false}];
 assert.deepEqual(localProjectsFor(x,projects).map(row=>row.project.name),['Renamed','Other']);
 assert.deepEqual(localProjectsFor(x,projects.slice(1)).map(row=>row.project.id),['other']);
});

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
 assert.deepEqual(reorderIds(['a','hidden','b','c'],'c','a'),['c','hidden','b','a']);
 assert.deepEqual(reorderIds(['a','b'],'unknown','a'),['a','b']);
 assert.deepEqual(reorderIds(['a','b'],'a','unknown'),['a','b']);
 assert.deepEqual(reorderIds(['a','b'],'a','a'),['a','b']);
});

test('adjacent tiles exchange places in both directions',()=>{
 assert.deepEqual(reorderIds(['a','b','c'],'a','b'),['b','a','c']);
 assert.deepEqual(reorderIds(['a','b','c'],'b','a'),['b','a','c']);
});

test('any pair in a grid swaps symmetrically without shifting other tiles',()=>{
 const order=['top-left','top-middle','top-right','bottom-left','bottom-middle','bottom-right'];
 for(let from=0;from<order.length;from++)for(let to=0;to<order.length;to++){
  const result=reorderIds(order,order[from],order[to]);
  assert.equal(result[from],order[to]);assert.equal(result[to],order[from]);
  for(let i=0;i<order.length;i++)if(i!==from&&i!==to)assert.equal(result[i],order[i]);
  assert.deepEqual(reorderIds(result,order[from],order[to]),order);
  assert.deepEqual(order,['top-left','top-middle','top-right','bottom-left','bottom-middle','bottom-right']);
 }
});

test('selected project folder replaces the old local scope without promoting files',()=>{
 const selected={...project,skill_path:'C:/real/game'};
 const candidate={id:'found',kind:'skill',scope:'local',installed:false,file_found:true,project_ids:['game']};
 const x={...addon,components:[global,local,{...local,id:'new',project_path:'C:/real/game'},candidate]};
 assert.deepEqual(componentsFor(x,selected).map(c=>c.id),['s1','new','found']);
 assert.equal(componentsFor(x,{id:'other',path:'C:/other'}).some(c=>c.id==='found'),false);
 assert.equal(componentsFor(x,selected).find(c=>c.id==='found').installed,false);
});
