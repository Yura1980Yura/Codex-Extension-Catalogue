"""Local user-skill switches through Codex's documented skills/config/write API.

The config is authoritative. A durable receipt recovers history after interruption;
recovery never retries a configuration write or rewrites an old configuration.
"""
from platform_paths import codex_dir
import hashlib
import os
from pathlib import Path
import tomllib
import uuid

import discovery
import journal
from storage import atomic_json, locked, now, read_json

PENDING = "activation-pending.json"


class Conflict(ValueError):
    pass


def normalized(path):
    return os.path.normcase(str(Path(path).resolve()))


def configuration(home):
    path = codex_dir(home)/"config.toml"
    raw = path.read_bytes() if path.exists() else b""
    return tomllib.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def personal_target(card, home):
    roots = [Path(home)/".agents/skills", codex_dir(home)/"skills"]
    candidates = set()
    for location in card.get("locations", []):
        path = Path(location["path"])
        if location.get("kind") == "cache" or path.name != "SKILL.md" or not path.is_file():
            continue
        # Only ordinary, direct personal installations; no plugins, junctions,
        # system skills, project paths or indirection to unrelated directories.
        if any(normalized(path.parent.parent) == normalized(root) for root in roots):
            if not any(p.is_symlink() or p.is_junction() for p in (path, path.parent, path.parent.parent)):
                candidates.add(path.resolve())
    return next(iter(candidates)) if len(candidates) == 1 else None


def target(card, home):
    if not card["id"].startswith("local:"):
        return None
    return personal_target(card, home)


def unavailable_message(card, home):
    key = card["id"]
    if key.startswith("vendor:") and personal_target(card, home):
        return "Известная ошибка каталога: этот личный навык установлен, но выключатель скрыт из-за отметки о стороннем авторе. Codex допускает его отключение; исправление каталога ещё не внесено."
    if key.startswith("system:"):
        return "Это встроенный навык Codex. Его отдельное включение и отключение в каталоге пока не реализовано."
    if key.startswith("plugin:"):
        return "Навык входит в плагин. Используйте выключатель плагина, если он доступен; отдельного выключателя этого навыка в каталоге пока нет."
    if any(location.get("scope") in ("project", "repo") or location.get("project") for location in card.get("locations", [])):
        return "Это навык проекта. Управление такими установками в каталоге пока не реализовано. Отсутствие выключателя не означает запрет отключения в Codex."
    return "Каталог не определил единственную обычную личную установку в стандартных папках навыков. Управление этим расположением пока не поддерживается."


def state(card, home, config=None):
    path = target(card, home)
    if path is None:
        return {"supported": False, "enabled": None, "message": unavailable_message(card, home)}
    try:
        parsed, fingerprint = config or configuration(home)
        entries = parsed.get("skills", {}).get("config", [])
        matches = [row for row in entries if isinstance(row, dict) and isinstance(row.get("path"), str) and normalized(row["path"]) == normalized(path)]
        if len(matches) > 1 or any(type(row.get("enabled")) is not bool for row in matches):
            raise ValueError("Неоднозначная настройка навыка.")
        enabled = matches[0]["enabled"] if matches else True
        revision = hashlib.sha256(journal.encoded({"config": fingerprint, "path": normalized(path)})).hexdigest()
        return {"supported": True, "enabled": enabled, "configured": bool(matches), "revision": revision,
                "message": "Изменение действует в Codex на этом компьютере. После переключения требуется перезапуск Codex; каталог и заметки сохраняются."}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"supported": False, "enabled": None, "message": "Настройки Codex пока не удалось прочитать. Переключение недоступно; прежние данные сохранены."}


def finish_locked(directory, home, pending, verification="not_checked", recovered=False):
    previous = next((e for e in journal.read_events(directory) if e["data"].get("activation_id") == pending["activation_id"]), None)
    if previous is None:
        card = read_json(Path(directory)/"inventory.json")["skills"].get(pending["skill_id"])
        actual = state(card, home) if card else {"enabled": None}
        changed = actual.get("supported") and actual["enabled"] == pending["enabled"]
        kind = "skill_activation_changed" if changed else "skill_activation_unconfirmed"
        observations = pending.get("observations", [])
        if changed and observations:
            inventory = read_json(Path(directory)/"inventory.json")
            record = inventory["skills"][pending["skill_id"]]
            # Merge only fresh observations of this skill, never an old whole index.
            for observation in observations:
                matches = [o for o in record["observations"] if o["kind"] == "discovery" and normalized(o["cwd"]) == normalized(observation["cwd"]) and normalized(o["path"]) == normalized(observation["path"])]
                if not matches or all(o["at"] <= observation["at"] for o in matches):
                    record["observations"] = [o for o in record["observations"] if o not in matches]+[observation]
            atomic_json(Path(directory)/"inventory.json", inventory)
        public = {k: v for k, v in pending.items() if k != "observations"}
        previous = journal.record_locked(directory, kind, {**public, "actual_enabled": actual["enabled"], "verification": pending.get("verification", verification), "recovered": recovered, "restart_required": bool(changed)})
    (Path(directory)/PENDING).unlink(missing_ok=True)
    return previous


def recover_locked(directory, home):
    pending = read_json(Path(directory)/PENDING)
    return finish_locked(directory, home, pending, recovered=True) if pending else None


def change(directory, home, project, key, enabled, revision, request_fn=None):
    if not isinstance(key, str) or type(enabled) is not bool or not isinstance(revision, str):
        raise ValueError("Неверные параметры переключателя.")
    request_fn = request_fn or discovery.request
    with locked(directory):
        journal.read_events(directory)
        recover_locked(directory, home)
        card = read_json(Path(directory)/"inventory.json")["skills"].get(key)
        if card is None:
            raise ValueError("Навык не найден.")
        before = state(card, home)
        if not before["supported"]:
            raise ValueError(before["message"])
        if revision != before["revision"]:
            raise Conflict("Настройки Codex уже изменились. Переключатель обновлён; проверьте состояние и повторите действие.")
        if enabled == before["enabled"]:
            return {"saved": True, "unchanged": True, "activation": before}
        path = target(card, home)
        pending = {"activation_id": uuid.uuid4().hex, "skill_id": key, "skill_name": card["name"], "before_enabled": before["enabled"], "enabled": enabled}
        atomic_json(Path(directory)/PENDING, pending)
        explicit = read_json(Path(directory)/"settings.json", {}).get("codex_executable")
        write_error = False
        try:
            request_fn("skills/config/write", {"path": str(path), "enabled": enabled}, explicit=explicit, codex_home=codex_dir(home))
        except (OSError, RuntimeError, ValueError):
            # A timeout may follow a committed write. Read back before reporting.
            write_error = True
        actual = state(card, home)
        verification = "not_checked"
        if actual["supported"] and actual["enabled"] == enabled:
            try:
                cwds = list(dict.fromkeys([str(project), *[o["cwd"] for o in card.get("observations", []) if o["kind"] == "discovery" and Path(o["cwd"]).is_dir()]]))
                result, _ = request_fn("skills/list", {"cwds": cwds, "forceReload": True}, explicit=explicit, codex_home=codex_dir(home))
                observations = [s for row in result.get("data", []) for s in row.get("skills", []) if normalized(s.get("path", "")) == normalized(path)]
                verification = "confirmed" if observations and all(s.get("enabled") is enabled for s in observations) else "not_confirmed"
                pending["observations"] = [{"kind": "discovery", "cwd": row["cwd"], "path": s["path"], "enabled": s["enabled"], "at": now()} for row in result.get("data", []) for s in row.get("skills", []) if normalized(s.get("path", "")) == normalized(path)]
            except (OSError, RuntimeError, ValueError):
                verification = "unavailable"
        pending["verification"] = verification
        atomic_json(Path(directory)/PENDING, pending)
        event = finish_locked(directory, home, pending, verification)
        if event["kind"] != "skill_activation_changed":
            raise ValueError("Codex не подтвердил изменение настройки. Текущее состояние перечитано; результат записан в историю. Повторите действие после проверки Codex.")
        result = {"saved": True, "activation": actual, "event_id": event["id"], "event": event, "restart_required": True, "verification": verification}
        if verification != "confirmed":
            result["warning"] = "Настройка сохранена. Подтвердить её новым процессом Codex пока не удалось. Требуется перезапуск Codex."
        elif write_error:
            result["warning"] = "Ответ Codex прервался, но сохранение и новое обнаружение проверены. Требуется перезапуск Codex."
        return result
