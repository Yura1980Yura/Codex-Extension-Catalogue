import {test} from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
const dom=new JSDOM('');
globalThis.window=dom.window;globalThis.document=dom.window.document;
const {markdown}=await import('../web/markdown.js');
test('Markdown renders headings, GFM tables and lists; hides YAML header',()=>{
 const result=markdown('---\nname: example\n---\n# Title\n\n| A | B |\n| --- | --- |\n| **Strong** | X |\n\n- One\n- Two');
 assert.match(result,/<h1>Title<\/h1>/);assert.match(result,/<table>/);assert.match(result,/<strong>Strong<\/strong>/);assert.match(result,/<li>Two<\/li>/);assert.doesNotMatch(result,/name: example/);
});
test('instructions cannot run scripts, event handlers, active URLs or fetch images',()=>{
 const result=markdown('<script>alert(1)</script><img src="https://example.com/track" onerror="alert(1)"><a href="javascript:alert(1)">run</a><iframe src="https://example.com"></iframe><form><input></form>');
 assert.doesNotMatch(result,/<script|onerror|javascript:|<img|<iframe|<form|<input/i);
});
test('external links open safely and raw code is inert',()=>{
 const result=markdown('[docs](https://example.com)\n\n```html\n<img onerror="evil()">\n```');
 assert.match(result,/rel="noopener noreferrer"/);assert.match(result,/&lt;img/);assert.doesNotMatch(result,/<img/);
});
test('only known package documents become clickable internal navigation',()=>{
 const result=markdown('[Read](../README.md) [Missing](missing.md) [Escape](../../README.md) [Local](file:///README.md)',{currentDocument:'references/usage.md',documents:{'README.md':{}}});
 const host=document.createElement('div');host.innerHTML=result;
 assert.equal(host.querySelectorAll('[data-document-target]').length,1);
 assert.equal(host.querySelector('[data-document-target]').dataset.documentTarget,'README.md');
 assert.equal(host.querySelectorAll('a[href]').length,0);
});
