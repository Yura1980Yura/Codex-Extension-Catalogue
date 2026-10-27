"""Local Meshy credential form backend. Only the free balance endpoint is called."""
from pathlib import Path
import hashlib
import json
import re
import tomllib
import urllib.error
import urllib.request

import journal
from storage import atomic_json, locked, now, read_json
import windows_credentials as vault

BALANCE_URL = "https://api.meshy.ai/openapi/v1/balance"


def root(home=None):
    return Path(home or Path.home())/".codex/service-connectors/meshy"


def validate_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"msy_[A-Za-z0-9_-]{20,1000}", value.strip()):
        raise ValueError("Введите API-ключ Meshy, начинающийся с msy_. Значение ключа не отображается.")
    return value.strip()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect blocked", headers, fp)


def balance(key, opener=None):
    key = validate_key(key)
    request = urllib.request.Request(BALANCE_URL, method="GET", headers={"Authorization": "Bearer "+key, "Accept": "application/json", "User-Agent": "Naviki-Meshy-Setup/1.0"})
    try:
        client = opener or urllib.request.build_opener(NoRedirect())
        with client.open(request, timeout=15) as response:
            raw = json.loads(response.read(65536).decode("utf-8"))
        if not isinstance(raw, dict) or isinstance(raw.get("balance"), bool) or not isinstance(raw.get("balance"), (int, float)) or raw["balance"] < 0:
            raise ValueError("Unexpected balance response")
        return {"status": "verified", "checked_at": now(), "balance": raw["balance"], "endpoint": "GET /openapi/v1/balance", "cost_credits": 0}
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("Meshy не принял ключ или не разрешил доступ к API. Проверьте ключ в кабинете Meshy. Прежний сохранённый ключ не заменён.") from None
        raise ValueError("Meshy не подтвердил проверку баланса. Прежний ключ не заменён; попробуйте позже.") from None
    except Exception:
        raise ValueError("Не удалось безопасно проверить баланс Meshy. Прежний ключ не заменён; проверьте подключение и повторите позже.") from None


def _configuration(home):
    path = Path(home)/".codex/config.toml"
    try:
        config = tomllib.loads(path.read_text("utf-8-sig"))
        names = [n for n in config.get("mcp_servers", {}) if "meshy" in n.lower()]
        return config, names
    except Exception:
        return {}, []


def status(home=None):
    home = Path(home or Path.home())
    base = root(home)
    manifest = read_json(base/"connection.json", {})
    if not manifest:
        return {"configured": False, "key_saved": False, "paid_tools_enabled": False, "credential_input_available": False, "revision": "not-installed"}
    config, names = _configuration(home)
    name = manifest.get("server_name")
    server = config.get("mcp_servers", {}).get(name, {})
    expected_launcher = str(home/"Applications/Naviki/manager/meshy_launcher.py")
    configured = bool(server.get("enabled", True) and expected_launcher in server.get("args", []))
    allowed = server.get("enabled_tools")
    tools = allowed if isinstance(allowed, list) else manifest.get("tool_names", [])
    paid = configured and any(t in manifest.get("paid_tool_names", []) for t in tools)
    try:
        key_saved = vault.read(presence_only=True)
        vault_available = True
    except vault.CredentialError:
        key_saved, vault_available = False, False
    check = read_json(base/"connection-state.json", {})
    # The browser receives no credential, credential fingerprint or raw config.
    revision = hashlib.sha256(json.dumps({"check": check, "key_saved": key_saved, "server": name, "configured": configured}, sort_keys=True).encode()).hexdigest()
    return {"configured": configured, "key_saved": key_saved, "credential_input_available": configured and vault_available,
            "version": manifest.get("version"), "server_name": name, "paid_tools_enabled": paid,
            "approval_mode": server.get("default_tools_approval_mode", "default"),
            "tool_count": len(tools), "check": {k: check[k] for k in ("status", "checked_at", "balance", "cost_credits") if k in check},
            "revision": revision, "storage": "Диспетчер учётных данных Windows", "restart_after_replacement": True}


def save_key(directory, home, key, revision, check_fn=balance, write_fn=vault.write):
    key = validate_key(key)
    before = status(home)
    if not before["credential_input_available"]:
        raise ValueError("Сначала завершите настройку локального подключения Meshy.")
    if revision != before["revision"]:
        raise ValueError("Настройки изменились. Закройте форму и откройте её заново перед вводом ключа.")
    verified = check_fn(key)  # Explicit user action; only free GET /balance.
    with locked(directory):
        if status(home)["revision"] != revision:
            raise ValueError("Настройки изменились во время проверки. Ключ не заменён.")
        journal.read_events(directory)
        write_fn(key)
        atomic_json(root(home)/"connection-state.json", verified)
        journal.record_locked(directory, "service_connection_verified", {"service_name": "Meshy", "key_saved": True, "verification": "free_balance_endpoint", "paid_generation_started": False})
    return {"saved": True, "state": status(home), "message": "Ключ сохранён в Windows и проверен бесплатным запросом баланса. Перезапустите сервер Meshy в настройках Codex, чтобы уже открытые подключения использовали новый ключ."}


def verify_stored(directory, home=None):
    key = vault.read()
    if not key:
        raise ValueError("Ключ ещё не сохранён.")
    verified = balance(key)
    with locked(directory):
        atomic_json(root(home)/"connection-state.json", verified)
        journal.record_locked(directory, "service_connection_verified", {"service_name": "Meshy", "key_saved": True, "verification": "free_balance_endpoint", "paid_generation_started": False})
    return {"verified": True, "cost_credits": 0, "checked_at": verified["checked_at"]}
