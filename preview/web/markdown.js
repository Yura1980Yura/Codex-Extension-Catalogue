import {marked} from './vendor/marked.js';
import DOMPurify from './vendor/purify.js';

// Instructions are untrusted content. Parse locally, then remove executable HTML
// and embedded media. Reading an instruction never executes its commands.
export function markdown(text,{documents={},currentDocument='SKILL.md'}={}){
 const body=String(text||'').replace(/^\uFEFF/,'').replace(/^---\s*\r?\n[\s\S]*?\r?\n---\s*(?:\r?\n|$)/,'');
 const clean=DOMPurify.sanitize(marked.parse(body,{gfm:true,breaks:false}),{
  USE_PROFILES:{html:true},FORBID_TAGS:['img','video','audio','iframe','style','form','input','button'],
  FORBID_ATTR:['style','id','name'],ALLOW_DATA_ATTR:false
 });
 const template=document.createElement('template');template.innerHTML=clean;
 for(const a of template.content.querySelectorAll('a')){
  const href=a.getAttribute('href')||'';
  if(!/^https?:\/\//i.test(href)){
   const target=packageTarget(href,currentDocument,documents);
   if(target){const button=document.createElement('button');button.type='button';button.className='secondary document-inline-link';button.dataset.documentTarget=target;button.textContent=a.textContent;a.replaceWith(button);}
   else a.removeAttribute('href');
   continue;
  }
  a.target='_blank';a.rel='noopener noreferrer';
 }
 for(const table of template.content.querySelectorAll('table')){
  const wrapper=document.createElement('div');wrapper.className='table-scroll';wrapper.tabIndex=0;
  wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label','Таблица инструкции');
  table.replaceWith(wrapper);wrapper.append(table);
 }
 return '<div class="markdown">'+template.innerHTML+'</div>';
}

function packageTarget(href,current,documents){
 let path;try{path=decodeURIComponent(href.split('#')[0]);}catch{return null;}
 if(!path||path.startsWith('/')||/[\\:?]/.test(path))return null;
 const parts=current.split('/').slice(0,-1);
 for(const part of path.split('/')){if(part==='..'){if(!parts.length)return null;parts.pop();}else if(part&&part!=='.')parts.push(part);}
 const normalized=parts.join('/');
 const keys=Object.keys(documents).filter(key=>key.toLocaleLowerCase()===normalized.toLocaleLowerCase());
 return keys.length===1?keys[0]:null;
}
