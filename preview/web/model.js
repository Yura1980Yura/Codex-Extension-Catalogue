export const typeNames={skill:'Навыки',mcp:'MCP',plugin:'Плагины',app:'Приложения',program:'Программы'};
export const scopeNames={global:'Глобально',local:'Локально',unknown:'Область не уточнена'};
export const origins={builtin:'От OpenAI',personal:'Мои разработки',third_party:'Других авторов',unknown:'Источник не уточнён'};
const normal=p=>String(p||'').replaceAll('\\','/').replace(/\/$/,'').toLowerCase();
const inside=(p,r)=>normal(p)===normal(r)||normal(p).startsWith(normal(r)+'/');

export function componentsFor(addon,project=null){
 const result=[];
 for(const component of addon.components){
  if(component.contexts){
   if(project){const facts=component.contexts[project.id];if(facts)result.push({...component,...facts});}
   else{
    const base=component.contexts.all;
    if(base)result.push({...component,...base});
    for(const [id,facts] of Object.entries(component.contexts)){
     if(id==='all')continue;
     if(!base||facts.scope==='local')result.push({...component,...facts,contextId:id});
    }
   }
  }else{
   if(project&&component.scope==='local'&&!inside(project.path,component.project_path))continue;
   const next={...component};
   const observed=(component.observations||[]).filter(o=>o.kind==='discovery'&&project&&normal(o.cwd)===normal(project.path));
   if(observed.length)next.enabled=observed.some(o=>o.enabled===true);
   result.push(next);
  }
 }
 // A disabled bundle also disables its skills in this context. It does not remove files.
 const plugins=result.filter(c=>c.kind==='plugin');
 if(plugins.length&&plugins.every(c=>c.enabled===false))for(const c of result)if(c.kind==='skill')c.enabled=false;
 return result;
}

export function presence(parts){return parts.some(c=>c.installed)?'installed':parts.length?'unconfirmed':'suggested';}
export function status(parts){
 const values=parts.filter(c=>c.installed&&c.kind!=='program');
 if(!values.length)return {key:'unknown',label:parts.length?'Не подтверждено':'Можно добавить'};
 const yes=values.some(c=>c.enabled===true),no=values.some(c=>c.enabled===false);
 if(yes&&no)return {key:'mixed',label:'Включена частично'};
 if(no&&!yes)return {key:'off',label:'Есть отключённые части'};
 if(yes)return {key:'on',label:'Есть включённые части'};
 return {key:'unknown',label:'Включение не проверено'};
}

export function visible(data,filters,ignoreType=false){
 const project=data.projects.find(p=>p.id===filters.project)||null;
 return data.addons.flatMap(addon=>{
  const parts=componentsFor(addon,project),found=presence(parts);
  if(project&&!parts.length&&!addon.suggested)return [];
  if(filters.presence==='known'&&found==='suggested')return [];
  if(filters.presence==='installed'&&!parts.some(c=>c.installed))return [];
  if(filters.presence==='unconfirmed'&&!parts.some(c=>!c.installed))return [];
  if(filters.presence==='suggested'&&found!=='suggested')return [];
  const overlay=data.overlay?.items?.[addon.id]||{};
  if(filters.favorite&&!(overlay.favorite??addon.favorite))return [];
  if(filters.direction&&!addon.directions.includes(filters.direction))return [];
  if(filters.origin&&addon.origin!==filters.origin)return [];
  if(filters.billing&&addon.billing!==filters.billing)return [];
  if(filters.tag&&![...addon.tags,...(overlay.tags||[])].includes(filters.tag))return [];
  const matching=parts.filter(c=>(filters.presence!=='installed'||c.installed)&&(filters.presence!=='unconfirmed'||!c.installed)&&(!filters.scope||c.scope===filters.scope)&&(!filters.enabled||(filters.enabled==='on'?c.enabled===true:filters.enabled==='off'?c.enabled===false:c.enabled==null)));
  if((filters.scope||filters.enabled)&&!matching.length)return [];
  if(!ignoreType&&(filters.types||[]).some(t=>!matching.some(c=>c.kind===t)))return [];
  const q=(filters.query||'').toLocaleLowerCase().trim();
  if(q&&!`${addon.title} ${addon.description} ${addon.tags.join(' ')} ${parts.map(c=>c.name).join(' ')}`.toLocaleLowerCase().includes(q))return [];
  return [{addon,parts,matching,presence:found,overlay}];
 });
}
