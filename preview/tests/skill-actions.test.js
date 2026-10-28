import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {skillFileTools,bindSkillFileTools,removedSkillsHTML} from '../web/skill-actions.js';

test('installation previews the selected project and only writes after explicit confirmation',async()=>{
 const dom=new JSDOM('<main></main><section id="reader"></section>');
 const previous=globalThis.document;globalThis.document=dom.window.document;
 try{
  const c={id:'c',kind:'skill',name:'example',path:'C:/finding/example/SKILL.md',file_actions:{install:true}};
  document.querySelector('main').innerHTML=skillFileTools([c],String);
  const calls=[],plan={name:'example',description:'Example',source:'C:/finding/example',destination:'C:/project/.agents/skills/example',target:'Project',files:2,revision:'revision'};
  let accepted,closed=false;
  bindSkillFileTools({data:{projects:[{id:'p',name:'Project',available:true}]},addon:{id:'a'},parts:[c],esc:String,toast(){},readPanel(title,html){document.querySelector('#reader').innerHTML=html;},closeReader(){closed=true;},acceptState(state){accepted=state;},api:async(name,body)=>{calls.push({name,body});return name==='skill-plan'?plan:{state:{confirmed:false}};}});
  document.querySelector('[data-install-skill]').onclick();
  document.querySelector('#skill-target').value='p';
  await document.querySelector('#preview-skill-install').onclick();
  assert.equal(calls.length,1);assert.equal(calls[0].name,'skill-plan');assert.equal(calls[0].body.project_id,'p');
  assert.match(document.querySelector('#reader').textContent,/C:\/project\/\.agents\/skills\/example/);
  const button=document.querySelector('#confirm-skill-operation');await button.onclick({currentTarget:button});
  assert.equal(calls[1].name,'skill-change');assert.equal(calls[1].body.confirmed,true);assert.equal(calls[1].body.revision,'revision');
  assert.equal(closed,true);assert.deepEqual(accepted,{confirmed:false});
 }finally{globalThis.document=previous;}
});

test('cancelled removal never calls the file mutation endpoint',async()=>{
 const dom=new JSDOM('<main></main><section id="reader"></section>');
 const previous=globalThis.document;globalThis.document=dom.window.document;
 try{
  const c={id:'c',kind:'skill',name:'example',path:'C:/skills/example/SKILL.md',installed:true,file_actions:{remove:true}};
  document.querySelector('main').innerHTML=skillFileTools([c],String);const calls=[];let closed=false;
  bindSkillFileTools({data:{projects:[]},addon:{id:'a'},parts:[c],esc:String,toast(){},readPanel(title,html){document.querySelector('#reader').innerHTML=html;},closeReader(){closed=true;},api:async(name)=>{calls.push(name);return {name:'example',source:'C:/skills/example/SKILL.md',target:'All projects',files:1};}});
  await document.querySelector('[data-remove-skill]').onclick();
  assert.match(document.querySelector('#reader').textContent,/Удаляется только выбранный SKILL.md/);
  assert.equal(document.querySelector('#confirm-skill-operation').textContent,'Удалить только этот SKILL.md');
  document.querySelector('#cancel-skill-operation').onclick();
  assert.deepEqual(calls,['skill-plan']);assert.equal(closed,true);
 }finally{globalThis.document=previous;}
});

test('history restores a known backup with a preview and explicit confirmation',async()=>{
 const dom=new JSDOM('<main></main><section id="reader"></section>');
 const previous=globalThis.document;globalThis.document=dom.window.document;
 try{
  document.querySelector('main').innerHTML=removedSkillsHTML([{operation_id:'known',name:'example',source:'C:/skills/example/SKILL.md',status:'removed'}],String);
  const calls=[];
  bindSkillFileTools({data:{projects:[]},addon:null,parts:[],esc:String,toast(){},readPanel(title,html){document.querySelector('#reader').innerHTML=html;},closeReader(){},acceptState(){},api:async(name,payload)=>{calls.push({name,payload});return name==='skill-plan'?{name:'example',source:'C:/backup/SKILL.md',destination:'C:/skills/example/SKILL.md',files:1,revision:'r',target:'Personal'}:{state:{}};}});
  await document.querySelector('[data-restore-skill]').onclick();
  assert.deepEqual(calls[0],{name:'skill-plan',payload:{action:'restore',operation_id:'known'}});
  const button=document.querySelector('#confirm-skill-operation');assert.equal(button.textContent,'Восстановить этот SKILL.md');
  await button.onclick({currentTarget:button});
  assert.equal(calls[1].payload.confirmed,true);assert.equal(calls[1].payload.action,'restore');
 }finally{globalThis.document=previous;}
});
