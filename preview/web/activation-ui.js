// A single switch represents exactly one component, never an entire mixed bundle.
export function singleControl(parts){
 return parts.length===1&&parts[0].control?.supported?parts[0]:null;
}
export function switchHTML(c,esc,context='all'){
 const name=c.title||c.name;
 return `<button class="codex-switch" role="switch" aria-checked="${c.control.enabled}" aria-label="Использовать в Codex: ${esc(name)}" data-activation="${esc(c.id)}" data-context="${esc(c.contextId||context)}"><span class="switch-track" aria-hidden="true"></span><span>${c.control.enabled?'Включено':'Отключено'}</span></button>`;
}
export function headerControlHTML(parts,esc,context='all'){
 const c=singleControl(parts);
 return c?`<div class="header-control"><span>Использовать в Codex</span>${switchHTML(c,esc,context)}</div>`:'';
}
export function controlContextNote(c){
 return c.state_note||(typeof c.enabled==='boolean'&&c.enabled!==c.control.enabled?`В этом проекте: ${c.enabled?'включено':'отключено'}. Его действующая настройка отличается от общей.`:'');
}
export const controlGuidance='Глобально · на этом компьютере. После изменения перезапустите Codex. Уже прочитанные инструкции остаются в истории открытого чата.';
