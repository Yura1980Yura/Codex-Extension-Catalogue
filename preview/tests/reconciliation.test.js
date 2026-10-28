import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {reconciliationHTML} from '../web/reconciliation.js';

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const base={schema_version:2,compared_skill_paths:65,connections:26,project_contexts:4,
 missing_record_count:0,missing_record_paths:[],missing_connection_ids:[],
 unconfirmed_skill_paths:Array.from({length:17},(_,i)=>`skill-${i}`),
 duplicate_component_ids:[],source_failures:[],complete:true,limits:'Проверены местные источники.'};
const documentFor=r=>new JSDOM(reconciliationHTML(r,esc)).window.document;

test('found but unconfirmed skills are separate from missing records',()=>{
 const doc=documentFor(base),text=doc.body.textContent;
 assert.match(text,/Отсутствующие записи: 0/);
 assert.match(text,/Найдены, но не подтверждены Codex: 17/);
 assert.match(text,/Сверяемые навыки: 65/);
 assert.doesNotMatch(text,/Пропуски:|34/);
 assert.equal(doc.querySelector('.amber'),null);
});

test('actual omissions and failed sources are not hidden by the new labels',()=>{
 const doc=documentFor({...base,missing_record_count:2,complete:false,source_failures:['all']});
 assert.match(doc.body.textContent,/Отсутствующие записи: 2/);
 assert.match(doc.body.textContent,/Не удалось полностью прочитать источники: 1/);
 assert.ok(doc.querySelector('.amber'));
});

test('old cached calculation is not presented as new or replaced with invented zeros',()=>{
 const doc=documentFor({complete:false,missing_skill_paths:Array(17),missing_session_paths:Array(17)});
 assert.match(doc.body.textContent,/Нажмите «Сверить с Codex»/);
 assert.doesNotMatch(doc.body.textContent,/Пропуски:|Отсутствующие записи:|34/);
});

test('missing audit and untrusted diagnostic text remain safe',()=>{
 assert.equal(reconciliationHTML(null,esc),'');
 const doc=documentFor({...base,limits:'<img src=x onerror=alert(1)>'});
 assert.equal(doc.querySelector('img'),null);
 assert.match(doc.body.textContent,/<img/);
});
