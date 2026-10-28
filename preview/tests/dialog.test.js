import {test} from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {showDialog,closeDialog,clearDialogMotion} from '../web/dialog.js';

function fixture(){
 const dialog=new JSDOM('<dialog></dialog>').window.document.querySelector('dialog');
 let frames=[];globalThis.requestAnimationFrame=callback=>frames.push(callback);
 let complete,cancel;const finished=new Promise((resolve,reject)=>{complete=resolve;cancel=reject;});
 let closes=0;
 dialog.showModal=()=>{dialog.open=true;};
 dialog.close=()=>{dialog.open=false;closes++;clearDialogMotion(dialog);};
 dialog.getAnimations=()=>[{effect:{target:dialog},finished}];
 return {dialog,complete,cancel,frames,closes:()=>closes};
}
test('dialog remains modal until its exit actually finishes',async()=>{
 const f=fixture();showDialog(f.dialog);f.frames.shift()();
 const closing=closeDialog(f.dialog);await Promise.resolve();
 assert.equal(f.dialog.open,true);assert.equal(f.closes(),0);
 f.complete();await closing;assert.equal(f.dialog.open,false);assert.equal(f.closes(),1);
});
test('reopening during exit does not get closed by the older completion',async()=>{
 const f=fixture();showDialog(f.dialog);const closing=closeDialog(f.dialog);
 showDialog(f.dialog);f.complete();await closing;
 assert.equal(f.dialog.open,true);assert.equal(f.closes(),0);
});
test('keyboard or reduced motion closes immediately',async()=>{
 const f=fixture();showDialog(f.dialog,true);
 assert.equal(f.dialog.classList.contains('entering'),false);assert.equal(f.frames.length,0);
 await closeDialog(f.dialog,true);
 assert.equal(f.dialog.open,false);assert.equal(f.closes(),1);
});
test('cancelled transition and repeated close leave no stuck modal',async()=>{
 const f=fixture();showDialog(f.dialog);const first=closeDialog(f.dialog),second=closeDialog(f.dialog);
 f.cancel(new Error('interrupted'));await Promise.all([first,second]);
 assert.equal(f.dialog.open,false);assert.equal(f.closes(),1);
});
test('Escape followed by reopening is not affected by an older exit',async()=>{
 const f=fixture();showDialog(f.dialog);const closing=closeDialog(f.dialog);
 f.dialog.close();showDialog(f.dialog);f.complete();await closing;
 assert.equal(f.dialog.open,true);assert.equal(f.closes(),1);
});
test('unrelated child animation cannot delay dismissal',async()=>{
 const f=fixture();showDialog(f.dialog);
 f.dialog.getAnimations=()=>[{effect:{target:{}},finished:new Promise(()=>{})}];
 await closeDialog(f.dialog);assert.equal(f.dialog.open,false);
});
