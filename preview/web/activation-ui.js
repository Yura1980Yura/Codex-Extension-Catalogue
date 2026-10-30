// A single switch represents exactly one component, never an entire mixed bundle.
export function singleControl(parts){
 return parts.length===1&&parts[0].control?.supported?parts[0]:null;
}
export function switchHTML(c,esc,context='all'){
 const name=c.title||c.name;
 return `<button class="codex-switch" role="switch" aria-checked="${c.control.enabled}" aria-label="Использовать в Codex: ${esc(name)}" title="${esc(c.path||c.control.message||'')}" data-activation="${esc(c.id)}" data-context="${esc(c.contextId||context)}"><span class="switch-track" aria-hidden="true"></span><span>${c.control.enabled?'Включено':'Отключено'}</span></button>`;
}
export function headerControlHTML(parts,esc,context='all'){
 const c=singleControl(parts);
 return c?`<div class="header-control"><span>Использовать в Codex</span>${switchHTML(c,esc,context)}</div>`:'';
}
export function controlContextNote(c){
 return c.state_note||(typeof c.enabled==='boolean'&&c.enabled!==c.control.enabled?`В этом проекте: ${c.enabled?'включено':'отключено'}. Его действующая настройка отличается от общей.`:'');
}
export function controlScope(c){
 return c.control?.scope==='installation'?'Эта установка навыка':c.control?.scope==='local'?'Настройка проекта':'Глобально · на этом компьютере';
}
export const controlGuidance='После изменения перезапустите Codex. Уже прочитанные инструкции остаются в истории открытого чата.';

export function unavailableControlsHTML(parts,esc){
 const unavailable=parts.filter(c=>!c.control?.supported);
 if(!unavailable.length)return '';
 const title=unavailable.length===parts.length?'Почему нет выключателя':'Почему не у всех частей есть выключатель';
 return `<details class="control-explanation"><summary>${title}</summary>${unavailable.map(c=>`<p>${parts.length>1?`<strong>${esc(c.title||c.name)}</strong><br>`:''}${esc(c.control?.message||'Управление этой частью в каталоге пока недоступно.')}</p>`).join('')}</details>`;
}

export function tileControlsHTML(parts,esc,context='all'){
 const available=parts.filter(c=>c.control?.supported);
 const explanation=unavailableControlsHTML(parts,esc);
 if(!available.length)return explanation?`<div class="tile-controls">${explanation}</div>`:'';
 const kinds={skill:'Навык',mcp:'MCP',plugin:'Плагин',app:'Приложение'};
 const row=c=>`<div class="tile-control-row"><div class="tile-control-label">${available.length>1?`<span class="badge ${c.kind}">${kinds[c.kind]||'Часть'}</span><strong>${esc(c.title||c.name)}</strong>`:`<span>${parts.length===1?'В Codex':kinds[c.kind]||'Часть'}</span>`}<small>${esc(controlScope(c))}</small></div>${switchHTML(c,esc,context)}</div>${controlContextNote(c)?`<p class="tile-control-note">${esc(controlContextNote(c))}</p>`:''}`;
 const hint='Настройка Codex на этом компьютере. После изменения перезапустите Codex.';
 return `<div class="tile-controls" title="${hint}">${available.length===1?row(available[0]):`<details class="tile-control-menu"><summary>Включение частей <span>${available.length}</span><span class="tile-control-chevron" aria-hidden="true">⌄</span></summary><div class="tile-control-options">${available.map(row).join('')}<p class="tile-control-note">${hint}</p></div></details>`}${explanation}<p class="tile-control-result" role="status" aria-live="polite"></p></div>`;
}
