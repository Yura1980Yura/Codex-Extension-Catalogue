// Presence and Codex confirmation are independent facts. Never add overlapping
// source lists in the browser or interpret an older snapshot with new semantics.
export function reconciliationHTML(result,esc){
 if(!result)return '';
 if(result.schema_version!==2)return '<section class="soft-note amber"><strong>Счётчики ожидают новой сверки</strong><p>Нажмите «Сверить с Codex», чтобы отдельно увидеть отсутствующие записи и найденные навыки без подтверждения Codex.</p></section>';
 const r=result;
 return `<section class="soft-note ${r.complete?'':'amber'}"><strong>${r.complete?'Все записи из списков сверки представлены':'Сопоставление требует внимания'}</strong><p>Сверяемые навыки: ${r.compared_skill_paths} · Подключения: ${r.connections} · Проекты: ${r.project_contexts}.</p><p><strong>Отсутствующие записи: ${r.missing_record_count}.</strong></p><p>Найдены, но не подтверждены Codex: ${r.unconfirmed_skill_paths.length}.</p><p class="tiny">Это навыки из указанных списков сверки. Подтверждение — наличие в ответе Codex, а не проверка работы.</p><p>Повторяющиеся части: ${r.duplicate_component_ids.length}.</p>${r.source_failures.length?`<p>Не удалось полностью прочитать источники: ${r.source_failures.length}.</p>`:''}<p>${esc(r.limits)}</p></section>`;
}
