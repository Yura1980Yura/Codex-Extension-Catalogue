"""Durable requests, proposals and observed skill lifecycle events."""
import hashlib
import json
import os
from pathlib import Path
import uuid

from storage import atomic_text, locked, now


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_events(directory):
    path = Path(directory)/"history.jsonl"
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("History has an incomplete final record; preserve and repair it explicitly")
    events, previous = [], None
    for line in raw.splitlines():
        event = json.loads(line)
        digest = event.get("sha256")
        payload = {k: v for k, v in event.items() if k != "sha256"}
        if event.get("previous_sha256") != previous or hashlib.sha256(encoded(payload)).hexdigest() != digest:
            raise ValueError("History integrity check failed; existing history was not modified")
        previous = digest
        events.append(event)
    return events


def render(directory, events):
    lines = ["# История каталога навыков", "", "Автоматическое представление history.jsonl. Поиск не означает установку; найдено не означает испытано.", ""]
    labels = {"search_requested": "Запрос поиска", "search_completed": "Предложены варианты", "search_failed": "Ошибка поиска", "operation_started": "Начата операция", "operation_completed": "Результат операции", "inventory_refreshed": "Сверка каталога", "catalog_installed": "Установка каталога"}
    labels.update(user_note_added="Заметка к навыку", favorite_changed="Избранное изменено", document_saved="Сохранена ручная заметка", wish_created="Записано пожелание", wish_updated="Обновлено пожелание", manager_verified="Проверен менеджер навыков")
    labels.update(directions_initialized='Созданы исходные направления', directions_seeded='Классифицированы новые навыки', direction_created='Создано направление', direction_renamed='Направление переименовано', skill_directions_changed='Изменены направления навыка')
    labels['skill_application_verified'] = 'Проверено применение навыка'
    labels['skill_origin_changed'] = 'Изменено происхождение навыка'
    labels['skill_author_changed'] = 'Изменён профиль автора навыка'
    labels['skill_activation_changed'] = 'Изменено использование навыка в Codex'
    labels['skill_activation_unconfirmed'] = 'Переключение навыка не подтверждено'
    labels.update(project_added='Проект добавлен в каталог', project_recommendation_changed='Изменена рекомендация проекта', project_application_recorded='Записано подтверждённое пользователем применение')
    for event in events:
        data = event["data"]
        lines.extend([f"## {event['at']} — {labels.get(event['kind'], event['kind'])}", "", f"ID: `{event['id']}`", "", json.dumps(data, ensure_ascii=False, indent=2), ""])
    atomic_text(Path(directory)/"HISTORY.md", "\n".join(lines))


def record_locked(directory, kind, data):
    """Caller holds the catalog write lock. Append is authoritative; view is derived."""
    events = read_events(directory)
    event = {"schema": 1, "id": uuid.uuid4().hex, "at": now(), "kind": kind, "data": data, "previous_sha256": events[-1]["sha256"] if events else None}
    event["sha256"] = hashlib.sha256(encoded(event)).hexdigest()
    line = encoded(event) + b"\n"
    with (Path(directory)/"history.jsonl").open("ab") as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    verified = read_events(directory)
    if verified[-1] != event:
        raise OSError("History append read-back failed")
    try:
        render(directory, verified)
    except OSError as error:
        # The event is already durable: do not imply that the operation was not recorded.
        event = {**event, "view_warning": f"Event saved; rebuild HISTORY.md with history command: {error}"}
    return event


def record(directory, kind, data):
    with locked(directory):
        return record_locked(directory, kind, data)


def snapshot(target):
    target = Path(target)
    if not (target/"SKILL.md").is_file():
        return {"present": False, "sha256": None}
    files = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.name != "installation.json"}
    return {"present": True, "sha256": hashlib.sha256(encoded(files)).hexdigest(), "file_count": len(files)}


def operation_start(directory, action, target, source, reason):
    if action not in ("install", "replace", "update", "remove"):
        raise ValueError("Unsupported lifecycle action")
    return record(directory, "operation_started", {"action": action, "target": str(Path(target).resolve()), "source": source, "reason": reason, "before": snapshot(target)})


def operation_finish(directory, operation_id, outcome, detail):
    with locked(directory):
        events = read_events(directory)
        started = next((x for x in events if x["id"] == operation_id and x["kind"] == "operation_started"), None)
        if not started:
            raise ValueError("Unknown operation ID")
        finished = next((x for x in events if x["kind"] == "operation_completed" and x["data"]["operation_id"] == operation_id), None)
        if finished:
            return finished
        data = started["data"]
        after = snapshot(data["target"])
        before = data["before"]
        actual = outcome
        if outcome == "success":
            if data["action"] == "remove":
                actual = "success" if before["present"] and not after["present"] else "unproven"
            elif not after["present"]:
                actual = "unproven"
            elif before == after:
                actual = "unchanged"
            elif data["action"] in ("update", "replace") and not before["present"]:
                actual = "unproven"
        return record_locked(directory, "operation_completed", {"operation_id": operation_id, "action": data["action"], "target": data["target"], "source": data["source"], "reported_outcome": outcome, "outcome": actual, "before": before, "after": after, "detail": detail, "functional_tested": False})
