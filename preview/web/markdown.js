import {marked} from './vendor/marked.js';
import DOMPurify from './vendor/purify.js';

// Instructions are untrusted content. Parse locally, then remove executable HTML
// and embedded media. Reading an instruction never executes its commands.
export function markdown(text){
 const body=String(text||'').replace(/^\uFEFF/,'').replace(/^---\s*\r?\n[\s\S]*?\r?\n---\s*(?:\r?\n|$)/,'');
 const clean=DOMPurify.sanitize(marked.parse(body,{gfm:true,breaks:false}),{
  USE_PROFILES:{html:true},FORBID_TAGS:['img','video','audio','iframe','style','form','input','button'],
  FORBID_ATTR:['style','id','name'],ALLOW_DATA_ATTR:false
 });
 const template=document.createElement('template');template.innerHTML=clean;
 for(const a of template.content.querySelectorAll('a')){
  const href=a.getAttribute('href')||'';
  if(!/^https?:\/\//i.test(href)){a.removeAttribute('href');continue;}
  a.target='_blank';a.rel='noopener noreferrer';
 }
 for(const table of template.content.querySelectorAll('table')){
  const wrapper=document.createElement('div');wrapper.className='table-scroll';wrapper.tabIndex=0;
  wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label','Таблица инструкции');
  table.replaceWith(wrapper);wrapper.append(table);
 }
 return '<div class="markdown">'+template.innerHTML+'</div>';
}
