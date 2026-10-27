"""Service registry and secret-free Codex inspection. Never writes Codex config."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit
import uuid

import directions as transactions
import discovery
import journal
import meshy_setup
import service_profiles
import connection_state
from storage import atomic_json, locked, now, read_json

KEY = "service_catalog"
POLICIES = {"inherit": "По правилам Codex", "explicit": "Только по явной команде", "ask": "С подтверждением операции", "blocked": "Не использовать"}
MESHY = {"id": "service:meshy", "name": "Meshy", "kind": "planned", "description": "Генерация и обработка 3D-моделей, изображений и текстур.", "documentation": "https://docs.meshy.ai/en/api/ai", "paid": True, "policy": "explicit"}


class Conflict(ValueError):
    pass


def project_id(path):
    return "project:" + hashlib.sha256(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:24]


def project_choices(directory):
    user = read_json(Path(directory)/"user.json", {})
    inventory = read_json(Path(directory)/"inventory.json", {})
    found = {}
    for path in inventory.get("projects", []):
        if isinstance(path, str) and Path(path).is_absolute():
            found[project_id(path)] = {"id": project_id(path), "name": Path(path).name, "path": path}
    for key, item in user.get("project_catalog", {}).get("projects", {}).items():
        found[key] = {"id": key, "name": item["name"], "path": item["path"]}
    return sorted(found.values(), key=lambda item: (item["name"].casefold(), item["id"]))


def registry(user):
    value = user.get(KEY, {"schema": 1, "services": {}, "bindings": {}})
    if not isinstance(value, dict) or value.get("schema") != 1 or any(not isinstance(value.get(k), dict) for k in ("services", "bindings")):
        raise ValueError("Повреждены сведения сервисов. Прежние данные сохранены.")
    for key, item in value["services"].items():
        if not isinstance(item, dict) or item.get("policy", "explicit") not in POLICIES:
            raise ValueError("Повреждена карточка сервиса.")
    for key, bindings in value["bindings"].items():
        if not isinstance(bindings, dict) or any(not isinstance(v, dict) or v.get("policy") not in POLICIES for v in bindings.values()):
            raise ValueError("Повреждены связи сервисов с проектами.")
    return deepcopy(value)


def text(value, label, maximum=2000, optional=False):
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in "\n\r\t" for c in value) or (not optional and not value.strip()):
        raise ValueError("Проверьте поле «"+label+"».")
    # A catalogue note must not become an accidental credential store.
    if re.search(r"\b(?:msy_|sk-)[A-Za-z0-9_-]{12,}|Bearer\s+\S{12,}|(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+", value, re.I):
        raise ValueError("Не сохраняйте ключи и пароли в каталоге. Здесь нужны только описание и назначение.")
    return value.strip()


def source_info(layer):
    name = layer.get("name", {})
    path = name.get("file") or (str(Path(name["dotCodexFolder"])/"config.toml") if name.get("dotCodexFolder") else "")
    return {"scope": name.get("type", "unknown"), "path": path, "applied": not bool(layer.get("disabledReason"))}


def public_entry(section, name, raw, sources):
    """Allow-list output: no command args, env values, URLs, headers or raw errors."""
    item = {"id": section+":"+name, "name": name, "kind": section, "configured": True, "enabled": raw.get("enabled") if isinstance(raw.get("enabled"), bool) else None, "sources": sources, "runtime": "not_checked", "authentication": "not_checked"}
    if section == "mcp":
        # A hash invalidates discovery evidence after any configuration edit.
        # The raw command, arguments and credential settings are never returned.
        item["configuration_revision"] = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        try:
            endpoint = urlsplit(raw.get("url", ""))
            if endpoint.scheme == "https" and endpoint.hostname == "mcp.cloudflare.com" and endpoint.path.rstrip("/") == "/mcp" and not endpoint.username:
                item["provider_identity"] = "cloudflare"
        except (ValueError, TypeError):
            pass
        item["enabled"] = raw.get("enabled", True)
        item["transport"] = "STDIO" if "command" in raw else "HTTP" if "url" in raw else "Не определён"
        item["credential_configured"] = bool(raw.get("env") or raw.get("env_vars") or raw.get("bearer_token_env_var") or raw.get("http_headers") or raw.get("env_http_headers"))
        allowed = raw.get("enabled_tools")
        item["tool_limit"] = len(allowed) if isinstance(allowed, list) else None
        mode = raw.get("default_tools_approval_mode")
        item["approval"] = mode if mode in ("auto", "prompt", "writes", "approve") else "default"
    return item


def sanitize_config(response):
    config = response.get("config", {})
    layers = response.get("layers") or []
    result = []
    for section, field in (("mcp", "mcp_servers"), ("plugin", "plugins"), ("app", "apps")):
        entries = config.get(field) or {}
        if not isinstance(entries, dict):
            continue
        for name, raw in entries.items():
            if not isinstance(raw, dict) or name.startswith("_"):
                continue
            sources = [source_info(layer) for layer in layers if name in (layer.get("config", {}).get(field) or {})]
            result.append(public_entry(section, name, raw, sources))
    return result


def inspect(home, cwd=None, explicit=None, request_fn=discovery.request):
    timestamp = now()
    try:
        response, client = request_fn("config/read", {"includeLayers": True, "cwd": str(cwd or home)}, explicit, timeout=20)
        return {"checked_at": timestamp, "status": "effective", "source": "Codex config/read", "entries": sanitize_config(response), "warning": None}
    except Exception:
        # Never forward parser/RPC errors: they can contain full secret values.
        path = Path(home)/".codex/config.toml"
        try:
            config = tomllib.loads(path.read_text("utf-8-sig")) if path.exists() else {}
            response = {"config": config, "layers": [{"config": config, "name": {"type": "user", "file": str(path)}}]}
            return {"checked_at": timestamp, "status": "file_only", "source": "Пользовательский config.toml", "entries": sanitize_config(response), "warning": "Codex не вернул действующую конфигурацию. Показан только пользовательский файл; проектные и управляемые настройки не проверены."}
        except Exception:
            return {"checked_at": timestamp, "status": "unavailable", "source": "Недоступно", "entries": [], "warning": "Не удалось прочитать настройки Codex. Секретные значения и текст ошибки скрыты."}


def view(directory, home, project=None, request_fn=discovery.request):
    directory = Path(directory)
    choices = project_choices(directory)
    selected = next((p for p in choices if p["id"] == project), None)
    if project and not selected:
        raise ValueError("Проект не найден. Обновите список.")
    settings = read_json(directory/"settings.json", {})
    observed = inspect(home, selected["path"] if selected else None, settings.get("codex_executable"), request_fn)
    with locked(directory):
        transactions.recover_locked(directory)
        saved = registry(read_json(directory/"user.json", {}))
    cards = {item["id"]: item for item in observed["entries"]}
    apps_status = "unavailable"
    try:
        installed, _ = request_fn("app/installed", {}, settings.get("codex_executable"), timeout=5, process_cwd=str(selected["path"] if selected else home))
        if not isinstance(installed.get("apps"), list):
            raise ValueError("Unexpected installed app response")
        apps_status = "reported"
        for app in installed["apps"]:
            if not isinstance(app, dict) or not isinstance(app.get("id"), str):
                continue
            key = "app:"+app["id"]
            old_sources = cards.get(key, {}).get("sources", [])
            cards[key] = {"id": key, "name": app.get("runtimeName") or app["id"], "kind": "app", "configured": True, "enabled": app.get("enabled") if isinstance(app.get("enabled"), bool) else None, "callable": app.get("callable") if isinstance(app.get("callable"), bool) else None, "runtime": "app_reported", "authentication": "not_checked", "sources": old_sources+[{"scope": "account", "path": "Codex app/installed", "applied": True}]}
    except Exception:
        pass
    mesh_state = meshy_setup.status(home)
    mesh_id = "mcp:" + str(mesh_state.get("server_name", ""))
    actual = cards.pop(mesh_id, None) if mesh_state.get("server_name") else None
    if actual:
        cards[MESHY["id"]] = {**actual, **MESHY, "kind": "mcp", "server_name": actual["name"], "credential_state": mesh_state}
    else:
        cards.setdefault(MESHY["id"], {**MESHY, "configured": False, "enabled": False, "sources": [], "runtime": "not_checked", "authentication": "not_checked", "credential_state": mesh_state})
    for key, card in list(cards.items()):
        if card.get("provider_identity") == "cloudflare" and "service:cloudflare" not in cards:
            cards["service:cloudflare"] = {**cards.pop(key), "id": "service:cloudflare", "name": "Cloudflare", "server_name": card["name"]}
    for key, item in saved["services"].items():
        cards.setdefault(key, {"id": key, "name": item.get("name", key), "kind": item.get("kind", "manual"), "configured": False, "enabled": False, "sources": [], "runtime": "not_checked", "authentication": "not_checked"})
        # These are curated notes, never override facts reported by Codex.
        cards[key].update({field: item[field] for field in ("description", "documentation", "connection_method", "policy", "paid", "notes") if field in item})
    # Documented options are catalogue entries, never evidence of a connection.
    for key, profile in service_profiles.suggestions().items():
        if key not in cards:
            cards[key] = {"id": key, "name": profile["title"], "kind": "planned", "configured": False, "enabled": False, "sources": [], "runtime": "not_checked", "authentication": "not_checked"}
    observations = read_json(directory/"connection-checks.json", {}).get("checks", {})
    for key, card in cards.items():
        card.setdefault("policy", "inherit")
        card["profile"] = service_profiles.describe(card, saved["services"].get(key, {}).get("profile"))
        evidence = observations.get(key, {}) if not project else {}
        matched = bool(evidence and card.get("configured") and evidence.get("configuration_revision") == card.get("configuration_revision") and card.get("configuration_revision"))
        if matched:
            check = evidence.get("result", {})
            try:
                age = (datetime.now(timezone.utc)-datetime.fromisoformat(check["checked_at"])).total_seconds()
                fresh = 0 <= age <= 86400
            except (ValueError, KeyError, TypeError):
                fresh = False
            card["last_check"] = {**check, "fresh": fresh}
            card["connection"] = connection_state.evaluate(card, check if fresh else None)
            if not fresh and card["connection"]["state"] == "needs_check":
                card["connection"]["reason"] = "Последняя проверка старше суток. Проверьте подключение повторно."
        else:
            card["connection"] = connection_state.evaluate(card)
        card["bindings"] = [{"project_id": pid, "project_name": next((p["name"] for p in choices if p["id"] == pid), pid), **links[key]} for pid, links in saved["bindings"].items() if key in links]
        card["project_binding"] = next((b for b in card["bindings"] if b["project_id"] == project), None)
    warning = observed["warning"]
    if apps_status != "reported":
        warning = ((warning+" ") if warning else "")+"Состояние приложений аккаунта сейчас не получено; список подключений может быть неполным."
    return {"revision": transactions.checksum(saved), "checked_at": observed["checked_at"], "source": observed["source"]+(" + app/installed" if apps_status == "reported" else ""), "status": observed["status"], "apps_status": apps_status, "warning": warning, "project_id": project, "projects": choices, "services": sorted(cards.values(), key=lambda c: (c["id"] != MESHY["id"], c["name"].casefold())), "coverage": "Настройки компьютера и доступные сведения приложений аккаунта получены отдельным процессом Codex. Инструменты уже открытых чатов и других компьютеров здесь не проверяются. Запись расширения и его приложения могут показываться отдельно."}


def change(directory, home, request, request_fn=discovery.request):
    action = request.get("action")
    if action not in ("add", "annotate", "bind", "unbind", "profile"):
        raise ValueError("Неизвестное действие с сервисом.")
    rid = request.get("request_id", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", rid):
        raise ValueError("Неверный идентификатор запроса.")
    fingerprint = transactions.checksum({k: v for k, v in request.items() if k != "revision"})
    current = view(directory, home, request_fn=request_fn)
    directory = Path(directory)
    with locked(directory):
        transactions.recover_locked(directory)
        user = read_json(directory/"user.json", {"schema": 1, "skills": {}})
        saved = registry(user)
        previous = next((e for e in journal.read_events(directory) if e["data"].get("service_request_id") == rid), None)
        if previous:
            if previous["data"].get("service_request_sha256") != fingerprint:
                raise Conflict("Этот запрос уже сохранён с другим содержимым.")
            return {"saved": True, "replayed": True}
        if request.get("revision") != transactions.checksum(saved):
            raise Conflict("Сведения изменились в другом окне. Обновите список перед сохранением.")
        key = request.get("id")
        card = next((c for c in current["services"] if c["id"] == key), None)
        if action == "add":
            key = "service:" + uuid.uuid4().hex
            kind = request.get("kind")
            if kind not in ("api", "mcp", "plugin", "cli"):
                raise ValueError("Выберите способ будущего подключения.")
            card = {"id": key, "name": text(request.get("name"), "Название", 120), "kind": "manual", "description": text(request.get("description", ""), "Назначение", optional=True), "connection_method": kind}
            saved["services"][key] = card
        elif card is None:
            raise ValueError("Сервис не найден. Обновите список.")
        payload = {"service_id": key, "service_name": card["name"], "action": action, "service_request_id": rid, "service_request_sha256": fingerprint}
        if action == "profile":
            profile = service_profiles.validate(request.get("profile"), text)
            saved["services"].setdefault(key, {"name": card["name"], "kind": card["kind"]})["profile"] = profile
            payload.update(profile=profile)
        if action in ("add", "annotate"):
            policy = request.get("policy", "explicit")
            if policy not in POLICIES:
                raise ValueError("Выберите правило использования.")
            saved["services"].setdefault(key, {"name": card["name"], "kind": card["kind"]}).update(policy=policy, notes=text(request.get("notes", ""), "Заметка", optional=True))
            payload.update(policy=policy, notes=saved["services"][key]["notes"])
        if action in ("bind", "unbind"):
            pid = request.get("project_id")
            project = next((p for p in project_choices(directory) if p["id"] == pid), None)
            if not project:
                raise ValueError("Выберите существующий проект каталога.")
            links = saved["bindings"].setdefault(pid, {})
            if action == "unbind":
                links.pop(key, None)
            else:
                policy = request.get("policy", "explicit")
                if policy not in POLICIES:
                    raise ValueError("Выберите правило использования.")
                links[key] = {"purpose": text(request.get("purpose"), "Назначение в проекте"), "policy": policy, "updated_at": now()}
                # Preserve the identity even if the connection is removed externally.
                saved["services"].setdefault(key, {"name": card["name"], "kind": card["kind"]})
            payload.update(project_id=pid, project_name=project["name"])
        updated = deepcopy(user)
        updated[KEY] = saved
        transactions.commit_locked(directory, user, updated, "service_catalog_changed", payload)
    return {"saved": True, "service_id": key}


def probe(directory, home, identifier, request_fn=discovery.request):
    """Explicit global discovery only; no tool call, model turn or credential write."""
    current = view(directory, home, request_fn=request_fn)
    card = next((c for c in current["services"] if c["id"] == identifier and c["kind"] == "mcp" and c["configured"] and c["enabled"]), None)
    if not card or current["status"] != "effective":
        raise ValueError("Проверка доступна для включённого MCP из действующей общей конфигурации.")
    settings = read_json(Path(directory)/"settings.json", {})
    result = {"checked_at": now(), "basis": "Отдельный процесс Codex; состояние открытого чата не проверялось", "status": "unavailable", "tool_count": None, "authentication": "unknown"}
    try:
        server_name = card.get("server_name", card["name"])
        response, _ = request_fn("mcpServerStatus/list", {"serverName": server_name, "detail": "toolsAndAuthOnly", "limit": 100}, settings.get("codex_executable"), timeout=35, process_cwd=str(home))
        entry = next((item for item in response.get("data", []) if item.get("name") == server_name), None)
        if entry:
            result.update(status="error" if entry.get("toolsError") else "discovered", tool_count=len(entry.get("tools") or {}), authentication=entry.get("authStatus") if entry.get("authStatus") in ("unknown", "unsupported", "notLoggedIn", "bearerToken", "oAuth") else "unknown")
    except Exception:
        pass
    result["connection"] = connection_state.evaluate(card, result)
    if card.get("configuration_revision"):
        with locked(directory):
            observed = read_json(Path(directory)/"connection-checks.json", {"schema": 1, "checks": {}})
            observed.setdefault("checks", {})[identifier] = {"configuration_revision": card["configuration_revision"], "result": result}
            atomic_json(Path(directory)/"connection-checks.json", observed)
    return result


def meshy_plan(home=None):
    state = meshy_setup.status(home)
    if state.get("configured"):
        return {"status": "configured", "credential_input_available": state["credential_input_available"], "scope": "Codex на этом компьютере", "notice": "Meshy установлен. Платные операции доступны только по явной команде пользователя; подтверждения включены в Codex.", "connection": state}
    return {"status": "awaiting_confirmation", "documentation": "https://www.meshy.ai/ru/developers/mcp", "package": "@meshy-ai/meshy-mcp-server@0.6.6", "version_checked_at": "2026-10-27", "scope": "Codex на этом компьютере", "allowed_tools": ["meshy_check_balance", "meshy_get_task_status", "meshy_list_tasks"], "steps": ["Установить официальный MCP-пакет версии 0.6.6 в отдельную локальную папку.", "Добавить только секцию mcp_servers.meshy в пользовательскую конфигурацию Codex, сохранив резерв и остальные настройки.", "Ввести API-ключ локально в отдельной форме; в чат и заметки его не отправлять.", "Сохранить ключ в диспетчере учётных данных Windows и передавать его процессу Meshy через локальный запускатель.", "Разрешить сначала только чтение баланса, списка и состояния задач; генерацию оставить недоступной. Для доступных инструментов включить запрос подтверждения.", "Проверить обнаружение инструментов и авторизацию без платной генерации."], "requirements": ["API-ключ Meshy с действующим доступом к API.", "Подтверждение области подключения и плана изменения конфигурации.", "Отдельная явная команда и бюджет для первого платного запуска."], "credential_input_available": False, "notice": "Это подготовленный план. Установка, сохранение ключа и изменение Codex ещё не выполняются. В этой версии каталога поля для секретов нет."}
