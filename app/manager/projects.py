"""Project recommendations and explicitly confirmed results in the existing user layer."""
from copy import deepcopy
from datetime import date
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlencode, urlsplit
import uuid

import catalog as c
import directions as themes
import installation
import journal as j
import resources
from storage import locked, read_json

KEY = "project_catalog"
KINDS = {"project_added", "project_recommendation_changed", "project_application_recorded"}


class Conflict(ValueError):
    pass


def text(value, label, maximum=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(x) < 32 and x not in "\n\r\t" for x in value):
        raise ValueError(f"Заполните поле «{label}» в допустимых пределах.")
    return value.strip()


def registry(user):
    value = user.get(KEY, {"schema": 1, "projects": {}})
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("projects"), dict):
        raise ValueError("Повреждены сведения проектов. Прежние данные сохранены.")
    for key, item in value["projects"].items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not Path(item["path"]).is_absolute() or installation.project_id(item["path"]) != key:
            raise ValueError("Повреждён адрес проекта. Прежние данные сохранены.")
        if not isinstance(item.get("name"), str) or not item["name"].strip() or not isinstance(item.get("recommendations", []), list) or not isinstance(item.get("applications", []), list):
            raise ValueError("Повреждена карточка проекта. Прежние данные сохранены.")
        for recommendation in item.get("recommendations", []):
            if not isinstance(recommendation, dict) or not isinstance(recommendation.get("skill_id"), str) or not isinstance(recommendation.get("reason"), str):
                raise ValueError("Повреждена рекомендация проекта. Прежние данные сохранены.")
        for application in item.get("applications", []):
            if not isinstance(application, dict) or any(not isinstance(application.get(field), str) for field in ("id", "skill_id", "date", "task", "result", "evidence_url", "evidence_label")):
                raise ValueError("Повреждена запись применения. Прежние данные сохранены.")
    return deepcopy(value)


def state(user, inventory, cards, docs):
    value = registry(user)
    visible = [card for card in cards if card.get("state") != "cache_only" or card.get("has_user_annotations")]
    facets = installation.facets(visible)
    found = {item["id"]: deepcopy(item) for item in facets["projects"]}
    for raw in inventory.get("projects", []):
        if isinstance(raw, str) and Path(raw).is_absolute():
            key = installation.project_id(raw)
            path = str(Path(raw).absolute())
            found.setdefault(key, {"id": key, "name": Path(path).name or path, "path": path})
    for key, item in value["projects"].items():
        found[key] = {"id": key, "name": item["name"], "path": item["path"]}
    projects = []
    for key, project in found.items():
        item = value["projects"].get(key, {})
        installed = sorted(card["id"] for card in visible if any(entry["kind"] == "project" and entry["present"] and entry["project_path"] and installation.project_id(entry["project_path"]) == key for entry in installation.describe(card)["entries"]))
        service_catalog = user.get("service_catalog", {})
        service_bindings = [{"id": sid, "name": service_catalog.get("services", {}).get(sid, {}).get("name", sid), **binding} for sid, binding in service_catalog.get("bindings", {}).get(key, {}).items()]
        projects.append({**project, "installed_skill_ids": installed, "recommendations": deepcopy(item.get("recommendations", [])), "applications": deepcopy(item.get("applications", [])), "services": service_bindings, "resources": resources.project_bindings(user, key)})
    projects.sort(key=lambda item: (item["name"].casefold(), installation.normalize_project_path(item["path"])))
    skills = [{key: card.get(key, "") for key in ("id", "name", "title_ru", "state")} for card in visible]
    skills.sort(key=lambda item: (item["title_ru"] or item["name"]).casefold())
    revision = themes.checksum({"registry": value, "projects": [{key: item[key] for key in ("id", "name", "path", "installed_skill_ids")} for item in projects], "skills": [item["id"] for item in skills]})
    return {"revision": revision, "projects": projects, "skills": skills, "obsidian_vault": Path(docs).resolve().parents[1].name}


def evidence(value, docs):
    value = text(value, "Ссылка на результат", 2048)
    if value.startswith("[[") and value.endswith("]]"):
        raw = value[2:-2]
        target, _, label = raw.partition("|")
        path, separator, heading = target.partition("#")
        normalized = PurePosixPath(path.replace("\\", "/"))
        if not path or normalized.is_absolute() or any(part in ("..", ".") or ":" in part for part in normalized.parts) or any(x in raw for x in ("[", "]", "\n", "\r", "\x00")):
            raise ValueError("Ссылка Obsidian должна указывать на заметку внутри вашего хранилища.")
        vault = Path(docs).resolve().parents[1]
        relative = normalized.as_posix()
        relative = relative[:-3] if relative.lower().endswith(".md") else relative
        destination = (vault/(relative+".md")).resolve()
        if not destination.is_relative_to(vault) or not destination.is_file():
            raise ValueError("Заметка по ссылке Obsidian не найдена в хранилище.")
        if separator and (not heading or heading not in re.findall(r"^#{1,6} (.+?)\s*$", destination.read_text("utf-8-sig"), re.M)):
            raise ValueError("Точный заголовок по ссылке Obsidian не найден.")
        return {"evidence_url": "obsidian://open?"+urlencode({"vault": vault.name, "file": relative+("#"+heading if separator else "")}), "evidence_label": label.strip() or target, "evidence_source": value}
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise ValueError("Укажите корректный адрес HTTP/HTTPS или ссылку Obsidian.")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme.lower() in ("http", "https") and parsed.hostname and parsed.username is None and parsed.password is None and not any(x in parsed.netloc for x in ("\\", "%"))
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Разрешены ссылки HTTP/HTTPS без пароля или ссылка Obsidian вида [[путь к заметке#заголовок]].")
    return {"evidence_url": value, "evidence_label": value, "evidence_source": value}


def change(directory, docs, cwd, request):
    directory = Path(directory)
    if not isinstance(request, dict):
        raise ValueError("Неверный запрос проекта.")
    action = request.get("action")
    if action not in ("add", "recommend", "unrecommend", "application"):
        raise ValueError("Неизвестное действие с проектом.")
    request_id = text(request.get("request_id"), "Идентификатор запроса", 128)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", request_id):
        raise ValueError("Неверный идентификатор запроса проекта.")
    fingerprint = themes.checksum({key: val for key, val in request.items() if key != "revision"})
    with locked(directory):
        themes.recover_locked(directory)
        events = j.read_events(directory)
        inventory, cards = c.load_cards(directory, cwd)
        user = read_json(directory/"user.json", {"schema": 1, "skills": {}})
        view = state(user, inventory, cards, docs)
        previous = next((item for item in events if item["kind"] in KINDS and item["data"].get("project_request_id") == request_id), None)
        if previous:
            if previous["data"].get("project_request_sha256") != fingerprint:
                raise Conflict("Этот запрос уже сохранён с другим содержимым. Обновите сведения и повторите действие.")
            return {"saved": True, "replayed": True, **view}
        if request.get("revision") != view["revision"]:
            raise Conflict("Сведения проекта изменились в другом окне. Обновите сведения, сохранив свой ввод, и повторите действие.")
        value = registry(user)
        if action == "add":
            name = text(request.get("name"), "Название проекта", 160)
            raw_path = text(request.get("path"), "Папка проекта", 2048)
            path = Path(raw_path)
            if not path.is_absolute() or not path.is_dir():
                raise ValueError("Укажите полный путь к существующей папке проекта.")
            path = str(path.absolute())
            key = installation.project_id(path)
            project = next((item for item in view["projects"] if item["id"] == key), {"name": name, "path": path})
        else:
            key = request.get("project_id")
            project = next((item for item in view["projects"] if item["id"] == key), None)
            if project is None:
                raise ValueError("Проект не найден. Обновите список проектов.")
        item = value["projects"].setdefault(key, {"name": project["name"], "path": project["path"], "recommendations": [], "applications": []})
        item.setdefault("recommendations", []); item.setdefault("applications", [])
        payload = {"project_id": key, "project_name": item["name"], "project_request_id": request_id, "project_request_sha256": fingerprint}
        if action == "add":
            item.update(name=name, path=path)
            kind = "project_added"
            payload["project_name"] = name
        else:
            skill_id = request.get("skill_id")
            skill = next((card for card in cards if card["id"] == skill_id), None)
            if action == "unrecommend" and skill is None and any(entry["skill_id"] == skill_id for entry in item["recommendations"]):
                skill = {"id": skill_id, "name": skill_id}
            if skill is None or (action != "unrecommend" and (skill.get("state") in ("missing", "cache_only"))):
                raise ValueError("Навык не найден в текущем каталоге. Обновите сведения или выберите другой.")
            payload.update(skill_id=skill_id, skill_name=skill.get("title_ru") or skill["name"])
            if action in ("recommend", "unrecommend"):
                item["recommendations"] = [entry for entry in item["recommendations"] if entry["skill_id"] != skill_id]
                if action == "recommend":
                    reason = text(request.get("reason"), "Зачем рекомендован навык", 4000)
                    item["recommendations"].append({"skill_id": skill_id, "reason": reason})
                    payload["reason"] = reason
                payload["action"] = action
                kind = "project_recommendation_changed"
            else:
                if request.get("confirmed") is not True:
                    raise ValueError("Подтвердите, что результат применения действительно проверен.")
                supplied_date = text(request.get("date"), "Дата применения", 10)
                try:
                    valid_date = date.fromisoformat(supplied_date)
                except ValueError:
                    raise ValueError("Введите дату применения в формате ГГГГ-ММ-ДД.") from None
                if valid_date.isoformat() != supplied_date:
                    raise ValueError("Введите дату применения в формате ГГГГ-ММ-ДД.")
                record = {"id": uuid.uuid4().hex, "skill_id": skill_id, "date": supplied_date, "task": text(request.get("task"), "Задача", 4000), "result": text(request.get("result"), "Проверенный результат"), **evidence(request.get("evidence"), docs), "verification_basis": "user_confirmation", "skill_sha256": None}
                item["applications"].append(record)
                payload["application"] = record
                kind = "project_application_recorded"
        if value == registry(user):
            return {"saved": True, "unchanged": True, **view}
        updated = deepcopy(user)
        updated[KEY] = value
        themes.commit_locked(directory, user, updated, kind, payload)
        fresh = read_json(directory/"user.json")
        return {"saved": True, **state(fresh, inventory, cards, docs)}
