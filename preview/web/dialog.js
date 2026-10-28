// Keep native dialog focus/inert behavior until the visible exit has finished.
const closing = new WeakMap();

export function showDialog(dialog, immediate=false){
 closing.delete(dialog);
 dialog.classList.toggle('no-motion',immediate);
 dialog.classList.remove('closing');
 if(dialog.open)return; // Reverse an interrupted close from its current position.
 dialog.classList.toggle('entering',!immediate);
 dialog.showModal();
 if(immediate)return;
 dialog.getBoundingClientRect(); // Establish the off-screen position before transition.
 requestAnimationFrame(()=>dialog.classList.remove('entering'));
}

export function clearDialogMotion(dialog){
 closing.delete(dialog);
 dialog.classList.remove('entering','closing');
}

export async function closeDialog(dialog, immediate=false){
 if(!dialog.open||closing.has(dialog))return;
 if(immediate){clearDialogMotion(dialog);dialog.close();return;}
 const request={};closing.set(dialog,request);
 dialog.classList.remove('no-motion');
 dialog.classList.add('closing');
 // CSS transitions retarget from the current position, including mid-entry.
 // No fixed timeout: reduced motion and interrupted/cancelled transitions settle too.
 await Promise.allSettled(dialog.getAnimations().filter(a=>a.effect?.target===dialog).map(a=>a.finished));
 if(closing.get(dialog)!==request)return;
 clearDialogMotion(dialog);
 if(dialog.open)dialog.close();
}
