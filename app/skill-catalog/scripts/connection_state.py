"""Evidence-based presentation states; catalogue notes never grant connection status."""

LABELS = {'connected':'Подключено', 'available':'Можно подключить', 'needs_check':'Требует проверки', 'disabled':'Отключено'}


def evaluate(card, check=None):
    def result(state, reason, basis, checked_at=None):
        return {'state':state, 'label':LABELS[state], 'reason':reason, 'basis':basis, 'checked_at':checked_at}
    if card.get('configured') and card.get('enabled') is False:
        return result('disabled','Подключение отключено в выбранной области настроек.','Настройки Codex')
    if card.get('runtime')=='app_reported':
        if card.get('callable') is True and card.get('enabled') is True:
            return result('connected','Codex сообщает, что инструменты приложения доступны.','Codex: список приложений')
        if card.get('callable') is False:
            return result('available','Codex не предоставляет инструменты приложения. Нужен вход или настройка доступа.','Codex: список приложений')
        return result('needs_check','Приложение обнаружено, доступность инструментов не подтверждена.','Codex: список приложений')
    if check:
        if check.get('status')=='discovered' and isinstance(check.get('tool_count'),int) and check['tool_count']>0 and check.get('authentication')!='notLoggedIn':
            if check.get('authentication')=='oAuth':
                return result('connected','MCP отвечает и предоставляет инструменты; вход выполнен через OAuth. Операции ресурса отдельно не проверялись.','Обнаружение MCP и состояние OAuth в Codex',check.get('checked_at'))
            return result('connected','MCP отвечает и предоставляет инструменты. Доступ к аккаунту сервиса проверяется отдельно.','Обнаружение MCP в отдельном процессе',check.get('checked_at'))
        if check.get('authentication')=='notLoggedIn':
            return result('available','MCP требует входа в аккаунт.','Проверка авторизации MCP',check.get('checked_at'))
        return result('needs_check','Проверка не подтвердила доступность инструментов MCP.','Обнаружение MCP в отдельном процессе',check.get('checked_at'))
    credential=card.get('credential_state') or {}
    if card.get('id')=='service:meshy' and card.get('configured') and card.get('enabled') is True and credential.get('configured'):
        if credential.get('key_saved') and credential.get('check',{}).get('status')=='verified':
            return result('connected','MCP настроен, ключ сохранён, доступ к Meshy проверен бесплатным запросом баланса.','Настройки Codex и проверка API Meshy',credential['check'].get('checked_at'))
        if not credential.get('key_saved'):
            return result('available','MCP настроен; для подключения нужно сохранить API-ключ.','Настройки локального подключения Meshy')
    if card.get('configured'):
        return result('needs_check','Есть запись в настройках. Работа инструментов и вход в сервис не подтверждены.','Настройки Codex')
    return result('available','Способ подключения описан; действующее подключение не обнаружено.','Справочник каталога')
