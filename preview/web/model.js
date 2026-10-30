export const typeNames={skill:'Навыки',mcp:'MCP',plugin:'Плагины',app:'Приложения',program:'Программы'};
export const scopeNames={global:'Глобально',local:'Локально',unknown:'Область не уточнена'};
export const origins={asemic:'Asemic',builtin:'От OpenAI',personal:'Мои разработки',third_party:'Других авторов',unknown:'Источник не уточнён'};
const normal=p=>String(p||'').replaceAll('\\','/').replace(/\/$/,'').toLowerCase();
const inside=(p,r)=>normal(p)===normal(r)||normal(p).startsWith(normal(r)+'/');
export const values=v=>Array.isArray(v)?v:v?[v]:[];
const matches=(filter,value)=>!values(filter).length||values(filter).some(v=>values(value).includes(v));
export function metadataFor(addon,overlay={}){
 return {origins:overlay.origins??values(addon.origin),directions:overlay.directions??addon.directions??[],
  billings:overlay.billings??values(addon.billing),tags:overlay.tags_override??[...new Set([...(addon.tags||[]),...(overlay.tags||[])])]};
}
export function sortRows(rows,mode,order=[]){
 const date=a=>Number.isFinite(Date.parse(a.added_at))?Date.parse(a.added_at):null;
 return [...rows].sort((a,b)=>{
  if(mode==='newest'||mode==='oldest'){
   const x=date(a.addon),y=date(b.addon);
   if(x===null&&y!==null)return 1;
   if(y===null&&x!==null)return -1;
   if(x!==null&&y!==null&&x!==y)return mode==='newest'?y-x:x-y;
  }else{
   if(mode==='custom'){
    const x=order.includes(a.addon.id)?order.indexOf(a.addon.id):Infinity,y=order.includes(b.addon.id)?order.indexOf(b.addon.id):Infinity;
    if(x!==y)return x-y;
   }
   const favorite=Number(b.overlay.favorite??b.addon.favorite)-Number(a.overlay.favorite??a.addon.favorite);
   if(favorite)return favorite;
   if(mode==='composition'){
    const difference=new Set(b.parts.map(c=>c.kind)).size-new Set(a.parts.map(c=>c.kind)).size;
    if(difference)return difference;
   }
  }
  return a.addon.title.localeCompare(b.addon.title,'ru')||a.addon.id.localeCompare(b.addon.id);
 });
}
export function reorderIds(order, moving, target){
 const from=order.indexOf(moving),to=order.indexOf(target),result=[...order];
 if(from<0||to<0||from===to)return result;
 // Exchange the selected pair; every other position remains unchanged.
 [result[from],result[to]]=[result[to],result[from]];
 return result;
}

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
   if(project&&component.scope==='local'&&!(component.project_ids||[]).includes(project.id)&&!(component.project_path&&inside(project.skill_path||project.path,component.project_path)))continue;
   const next={...component};
   const observed=(component.observations||[]).filter(o=>o.kind==='discovery'&&project&&normal(o.cwd)===normal(project.skill_path||project.path));
   if(observed.length){
    const fresh=component.config_authoritative?observed.filter(o=>Date.parse(o.at)>=component.config_changed_at):observed;
    if(fresh.length)next.enabled=fresh.some(o=>o.enabled===true);
    else if(observed.some(o=>o.enabled!==component.enabled)){
     // A local override may differ from the user flag. Await a fresh project read.
     next.enabled=null;next.state_note='Настройка изменена; состояние в этом проекте ожидает свежей сверки.';
    }
   }
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
  const meta=metadataFor(addon,overlay);
  if(!matches(filters.direction,meta.directions))return [];
  if(!matches(filters.origin,meta.origins))return [];
  if(!matches(filters.billing,meta.billings))return [];
  if(!matches(filters.tag,meta.tags))return [];
  const matching=parts.filter(c=>(filters.presence!=='installed'||c.installed)&&(filters.presence!=='unconfirmed'||!c.installed)&&matches(filters.scope,c.scope)&&matches(filters.enabled,c.enabled===true?'on':c.enabled===false?'off':'unknown'));
  if((values(filters.scope).length||values(filters.enabled).length)&&!matching.length)return [];
  if(!ignoreType&&(filters.types||[]).some(t=>!matching.some(c=>c.kind===t)))return [];
  const q=(filters.query||'').toLocaleLowerCase().trim();
  if(q&&!`${addon.title} ${addon.description} ${meta.tags.join(' ')} ${parts.map(c=>c.name).join(' ')}`.toLocaleLowerCase().includes(q))return [];
  return [{addon,parts,matching,presence:found,overlay}];
 });
}
