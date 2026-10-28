// A new check time alone must never rebuild the page.
const volatile=new Set(['updated_at','source_updated_at','checked_at','first_seen','last_seen','at','timestamp','config_changed_at','history']);
export function contentKey(data){
 return JSON.stringify({addons:data.addons,projects:data.projects,source_settings:data.source_settings,directions:data.directions,documents:data.documents,overlay:data.overlay,events:data.events,removed_skills:data.removed_skills,control_revision:data.control_revision},(key,value)=>volatile.has(key)?undefined:value);
}
export const pollDelay=state=>state.job?.state==='running'?2000:null;
export function preserveView(host,render,win=window){
 const open=[...host.querySelectorAll('details[open]')].map(el=>({source:el.closest('[data-source]')?.dataset.source,id:el.id,summary:el.querySelector('summary')?.textContent}));
 const focus=host.ownerDocument.activeElement?.id,x=win.scrollX,y=win.scrollY;
 render();
 for(const item of open){
  for(const el of host.querySelectorAll('details'))if((item.id&&el.id===item.id)||(!item.id&&el.closest('[data-source]')?.dataset.source===item.source&&el.querySelector('summary')?.textContent===item.summary))el.open=true;
 }
 if(focus)host.ownerDocument.getElementById(focus)?.focus({preventScroll:true});
 win.scrollTo(x,y);
}
