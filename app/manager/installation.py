"""Read-only, user-facing installation scope from the current inventory locations."""
from pathlib import Path
import hashlib
import os


def normalize_project_path(path):
    """Absolute lexical identity, with Windows path casing/separators normalized."""
    return os.path.normcase(os.path.abspath(path))


def project_id(path):
    return "project:" + hashlib.sha256(normalize_project_path(path).encode("utf-8")).hexdigest()[:24]


def _project_root(path, location):
    # Discovery may report a nested working directory; the skill folder identifies
    # the actual project boundary more precisely than that observation does.
    for parent in path.parents:
        if parent.name.casefold() == "skills" and parent.parent.name.casefold() in (".agents", ".codex"):
            return str(parent.parent.parent)
    value = location.get("project")
    return str(Path(value)) if isinstance(value, str) and value else ""


def describe(card):
    """Return only scope and the paths related to this skill, never raw observations."""
    entries, seen = [], set()
    locations = card.get("locations", [])
    is_plugin = str(card.get("id", "")).startswith("plugin:")
    # Prefer a real installation/discovery record when the same path is also cached.
    for location in sorted(locations, key=lambda item: (item.get("kind") == "cache", item.get("scope") not in ("user", "repo", "system"))):
        raw = location.get("path")
        if not isinstance(raw, str) or not raw or location.get("kind") == "cache":
            continue
        path = Path(raw)
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        scope = location.get("scope")
        kind = "plugin" if is_plugin else {"user": "user", "repo": "project", "system": "system"}.get(scope, "unknown")
        project = _project_root(path, location) if kind == "project" else ""
        try:
            present = path.is_file() and card.get("state") != "missing"
        except OSError:
            present = False
        title, description = {
            "user": ("Глобальная установка", "Для разных локальных проектов этого пользователя на этом компьютере."),
            "project": ("Установка в проекте", "Для работы в указанном проекте и его папках." if project else "Навык относится к проекту, но его папка пока не определена."),
            "system": ("Встроенный навык Codex", "Поставляется вместе с Codex. Наличие в конкретном чате зависит от его среды."),
            "plugin": ("Через расширение", "Поставляется расширением. Его доступность зависит от подключения расширения в Codex."),
            "unknown": ("Область установки не уточнена", "Файл найден, но данных для глобальной или проектной области недостаточно."),
        }[kind]
        if kind == "user" and card.get("portability") == "project_only":
            description = "Файл находится в личной папке, но инструкция привязана к своему проекту. Переносимость в другие проекты не подтверждена."
        if not present:
            title += " — наличие не подтверждено"
            description = "По этому адресу установка сейчас не подтверждена. Обновите каталог, чтобы сверить наличие файла."
        entries.append({
            "kind": kind, "title": title, "description": description,
            "project_name": Path(project).name if project else "",
            "project_path": project, "installation_path": str(path.parent), "present": present,
        })
    note = "Доступность в текущем чате проверяется отдельно: она зависит от включения навыка и среды Codex. Локальная установка сама не переносится на другое устройство или в облако."
    if not entries:
        if any(location.get("kind") == "cache" for location in locations):
            note = "Найдены только сохранённые файлы расширения. Они не подтверждают его подключение или область действия. Проверьте расширение в Codex и обновите каталог."
        else:
            note = "Текущее место установки не подтверждено. Обновите каталог или проверьте наличие навыка в нужном проекте."
    return {"entries": entries, "note": note}


def facets(cards):
    """Classify visible cards for filtering, without asserting enablement or use."""
    skills, projects = {}, {}
    scope_order = ("user", "project", "system", "plugin", "unknown")
    for card in cards:
        entries = describe(card)["entries"]
        scopes = {entry["kind"] for entry in entries}
        # A plugin known only from cached files is still supplied by a plugin.
        # Its existing state and detail note continue to report uncertainty.
        if str(card.get("id", "")).startswith("plugin:"):
            scopes = {"plugin"}
        if not scopes:
            scopes = {"unknown"}
        project_ids = set()
        for entry in entries:
            if entry["kind"] != "project" or not entry["project_path"]:
                continue
            path = os.path.abspath(entry["project_path"])
            identifier = project_id(path)
            project_ids.add(identifier)
            projects.setdefault(identifier, {"id": identifier, "name": Path(path).name or path, "path": path})
        skills[card["id"]] = {"scopes": [scope for scope in scope_order if scope in scopes], "project_ids": sorted(project_ids)}
    ordered_projects = sorted(projects.values(), key=lambda project: (project["name"].casefold(), os.path.normcase(project["path"])))
    return {"skills": skills, "projects": ordered_projects}
