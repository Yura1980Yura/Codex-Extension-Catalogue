"""User-owned themes with stable IDs, optimistic editing and recoverable writes."""
from copy import deepcopy
import hashlib
from pathlib import Path
import uuid

import journal as j
from storage import atomic_json, locked, read_json

DEFAULTS = [
    ("literature", "Литература и редактура"),
    ("development", "Разработка программ"),
    ("reverse", "Разбор готовых программ"),
    ("design", "Дизайн и изображения"),
    ("documents", "Документы и таблицы"),
    ("research", "Данные и исследования"),
    ("organization", "Организация работы"),
]
PENDING = "directions-pending.json"


class Conflict(ValueError):
    pass


def checksum(value):
    return hashlib.sha256(j.encoded(value)).hexdigest()


def initial_ids(card):
    tasks = set(card.get("tasks", []))
    name = card["name"].casefold()
    selected = set()
    if tasks & {"литература", "редактура"}: selected.add("literature")
    if tasks & {"разработка", "разработка игры", "проверка кода", "тестирование", "проектирование", "сайты"}: selected.add("development")
    if name == "reverse-engineer-anything": selected.add("reverse")
    if tasks & {"изображения", "иллюстрации", "визуализация"} or name in {"sites", "sites-remix", "pets", "update-pet"}: selected.add("design")
    if tasks & {"документы", "таблицы", "презентации", "слайды"}: selected.add("documents")
    if tasks & {"таблицы", "расчёты"} or name == "visualize": selected.add("research")
    if tasks & {"настройки Codex", "навыки", "управление приложениями", "организация", "расписания", "страницы", "знания"} or name in {"google-drive", "google-drive-comments", "pets", "update-pet"}: selected.add("organization")
    return [key for key, _ in DEFAULTS if key in selected]


def state(user, inventory):
    value = user.get("directions")
    if value is None:
        value = {"schema": 1, "items": [{"id": key, "title": title} for key, title in DEFAULTS], "assignments": {key: initial_ids(card) for key, card in inventory["skills"].items()}}
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("items"), list) or not isinstance(value.get("assignments"), dict):
        raise ValueError("Повреждены направления каталога. Прежние данные не изменены.")
    seen, titles = set(), set()
    for item in value["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not isinstance(item.get("title"), str) or not item["title"].strip() or item["id"] in seen or item["title"].casefold() in titles:
            raise ValueError("Повреждён список направлений.")
        seen.add(item["id"]); titles.add(item["title"].casefold())
    for ids in value["assignments"].values():
        if not isinstance(ids, list) or any(not isinstance(key, str) or key not in seen for key in ids) or len(ids) != len(set(ids)):
            raise ValueError("Повреждены назначения направлений.")
    return {**deepcopy(value), "revision": checksum(value), "initialized": "directions" in user}


def recover_locked(directory):
    directory = Path(directory)
    pending = read_json(directory/PENDING)
    if pending is None: return False
    events = j.read_events(directory)
    body = {key: value for key, value in pending.items() if key != "checksum"}
    if pending.get("checksum") != checksum(body):
        raise Conflict("План сохранения настроек каталога изменён. Данные оставлены для сверки.")
    user = read_json(directory/"user.json", {"schema": 1, "skills": {}})
    current, target = checksum(user), checksum(pending["user"])
    previous = next((e for e in events if e["data"].get("directions_operation") == pending["data"]["directions_operation"]), None)
    if previous and (previous["kind"] != pending["kind"] or previous["data"] != pending["data"]):
        raise Conflict("Квитанция настроек каталога не совпадает с историей.")
    if current != target:
        if current != pending["before"] or previous:
            raise Conflict("Данные изменились после прерывания. План сохранён для сверки; чужая правка не заменена.")
        atomic_json(directory/"user.json", pending["user"])
    if not previous:
        j.record_locked(directory, pending["kind"], pending["data"])
    (directory/PENDING).unlink()
    return True


def commit_locked(directory, user, updated, kind, data):
    directory = Path(directory)
    j.read_events(directory)
    pending = {"before": checksum(user), "user": updated, "kind": kind, "data": {**data, "directions_operation": uuid.uuid4().hex}}
    atomic_json(directory/PENDING, {**pending, "checksum": checksum(pending)})
    recover_locked(directory)


def seed_locked(directory, inventory, initialize=False):
    recover_locked(directory)
    user = read_json(Path(directory)/"user.json", {"schema": 1, "skills": {}})
    if "directions" not in user and not initialize: return False
    view = state(user, inventory)
    value = {key: view[key] for key in ("schema", "items", "assignments")}
    allowed = {item["id"] for item in value["items"]}
    new = [key for key in inventory["skills"] if key not in value["assignments"]]
    for key in new:
        value["assignments"][key] = [x for x in initial_ids(inventory["skills"][key]) if x in allowed]
    if not view["initialized"] or new:
        updated = {**user, "directions": value}
        commit_locked(directory, user, updated, "directions_initialized" if not view["initialized"] else "directions_seeded", {"direction_count": len(value["items"]), "skill_count": len(new) if view["initialized"] else len(value["assignments"])})
        return True
    return False


def initialize(directory):
    with locked(directory):
        seed_locked(directory, read_json(Path(directory)/"inventory.json"), initialize=True)
        return state(read_json(Path(directory)/"user.json"), read_json(Path(directory)/"inventory.json"))


def change(directory, action, revision, title=None, direction_id=None, skill_id=None, ids=None):
    with locked(directory):
        recover_locked(directory)
        j.read_events(directory)
        user = read_json(Path(directory)/"user.json", {"schema": 1, "skills": {}})
        inventory = read_json(Path(directory)/"inventory.json")
        view = state(user, inventory)
        if revision != view["revision"]:
            raise Conflict("Направления уже изменены в другом окне. Откройте свежий список; ваш ввод сохранён в форме.")
        value = {key: view[key] for key in ("schema", "items", "assignments")}
        if action in ("create", "rename"):
            if not isinstance(title, str) or not title.strip() or len(title) > 80 or "\x00" in title:
                raise ValueError("Введите название направления от 1 до 80 символов.")
            title = " ".join(title.split())
            if any(item["title"].casefold() == title.casefold() and (action == "create" or item["id"] != direction_id) for item in value["items"]):
                raise ValueError("Такое направление уже есть. Выберите другое название.")
            if action == "create":
                direction_id = "custom-"+uuid.uuid4().hex
                value["items"].append({"id": direction_id, "title": title})
                detail = {"direction_id": direction_id, "title": title}
            else:
                item = next((x for x in value["items"] if x["id"] == direction_id), None)
                if not item: raise ValueError("Направление не найдено.")
                detail = {"direction_id": direction_id, "before_title": item["title"], "title": title}
                item["title"] = title
        elif action == "assign":
            if skill_id not in inventory["skills"]: raise ValueError("Навык не найден.")
            allowed = {item["id"] for item in value["items"]}
            if not isinstance(ids, list) or any(not isinstance(key, str) or key not in allowed for key in ids) or len(ids) != len(set(ids)):
                raise ValueError("Выберите направления из текущего списка.")
            detail = {"skill_id": skill_id, "skill_name": inventory["skills"][skill_id]["name"], "before_ids": value["assignments"].get(skill_id, []), "direction_ids": ids, "direction_titles": [item["title"] for item in value["items"] if item["id"] in ids]}
            value["assignments"][skill_id] = ids
        else: raise ValueError("Неизвестное действие с направлениями.")
        if user.get("directions") != value:
            updated = {**user, "directions": value}
            commit_locked(directory, user, updated, {"create":"direction_created", "rename":"direction_renamed", "assign":"skill_directions_changed"}[action], detail)
        return {"saved": True, "direction_id": direction_id, "revision": checksum(value)}
