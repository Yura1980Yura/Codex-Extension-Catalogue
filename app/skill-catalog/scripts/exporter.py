"""One-way, owned Markdown views. Never imports edits from the documentation tree."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlsplit, urlunsplit

from journal import read_events
from storage import atomic_json, atomic_text, locked, read_json

MARKER = "<!-- codex-skill-catalog:generated:v1 -->"
VIEW_DIR = "Представления"
MANIFEST = ".catalog-export.json"
PENDING = ".catalog-export.pending.json"
STATES = {"present": "найден установленный комплект", "unconfirmed": "известен, сейчас не подтверждён", "missing": "не найден", "cache_only": "только файлы кеша"}
KINDS = {"service_catalog_changed": "Изменены сведения сервиса", "search_requested": "Запрос поиска", "search_completed": "Предложены варианты", "search_failed": "Ошибка поиска", "operation_started": "Начата операция", "operation_completed": "Результат операции", "inventory_refreshed": "Сверка каталога", "catalog_installed": "Установка каталога", "organization_completed": "Изменено размещение проекта"}
KINDS.update(user_note_added="Заметка к навыку", favorite_changed="Избранное изменено", document_saved="Сохранена ручная заметка", wish_created="Записано пожелание", wish_updated="Обновлено пожелание", manager_verified="Проверен менеджер навыков")
KINDS.update(directions_initialized="Созданы исходные направления", directions_seeded="Классифицированы новые навыки", direction_created="Создано направление", direction_renamed="Направление переименовано", skill_directions_changed="Изменены направления навыка")
KINDS.update(resource_catalog_changed="Изменены сведения ресурса", skill_organization_changed="Изменены теги и связи навыка", catalog_organization_migrated="Обновлена организация каталога")
KINDS["skill_application_verified"] = "Проверено применение навыка"
KINDS["skill_origin_changed"] = "Изменено происхождение навыка"
KINDS["skill_author_changed"] = "Изменён профиль автора навыка"
KINDS["skill_activation_changed"] = "Изменено использование навыка в Codex"
KINDS["skill_activation_unconfirmed"] = "Переключение навыка не подтверждено"
KINDS.update(project_added="Проект добавлен в каталог", project_recommendation_changed="Изменена рекомендация проекта", project_application_recorded="Записано подтверждённое пользователем применение")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(value):
    # User strings remain plain text, not Obsidian links, embeds or HTML.
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("[", "&#91;").replace("]", "&#93;").replace("*", "&#42;").replace("`", "&#96;").replace("\n", " ").replace("\r", " ")


def safe_url(value):
    parts = urlsplit(str(value))
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    # A source link is useful without credentials, query parameters or fragment.
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def author_links(profile):
    from authors import validate
    profile = validate(profile)
    # Angle-delimited Markdown destinations keep parentheses safe; escaping URL
    # delimiters preserves the meaning of query/fragment instead of removing them.
    return ["["+text(link["label"])+"](<"+quote(link["url"], safe=":/?#[]@!$&'()*+,;=%~-._")+">)" for link in profile["links"]]


def header(title):
    return [MARKER, f"# {title}", "", "Создано из рабочих данных каталога. Эту страницу не редактировать: свои записи ведите в разделе «Заметки», изменения карточек — через каталог. Обратного переноса из Markdown нет.", ""]


def project_evidence(record):
    value = str(record.get("evidence_source") or record.get("evidence_url") or "")
    if re.fullmatch(r"\[\[[^\[\]\r\n]+\]\]", value):
        target = value[2:-2].split("|", 1)[0].split("#", 1)[0].replace("\\", "/")
        path = PurePosixPath(target)
        if target and not path.is_absolute() and all(part != ".." and ":" not in part for part in path.parts):
            return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and parsed.username is None and parsed.password is None and not any(c.isspace() for c in value):
            return "["+text(record.get("evidence_label") or "Результат")+"](<"+quote(value, safe=":/?#[]@!$&'()*+,;=%~-._")+">)"
    except ValueError:
        pass
    return text(value or "ссылка не указана")


def project_lines(user, cards):
    projects = user.get("project_catalog", {}).get("projects", {})
    if not projects:
        return []
    titles = {card["id"]: card.get("title_ru") or card["name"] for card in cards}
    lines = ["## Проекты: рекомендации и подтверждённые применения", "", "Рекомендации — сохранённый выбор для задачи. Применения ниже подтверждены пользователем со ссылкой на результат; каталог сам не испытал навык. Если версия не зафиксирована, запись не подтверждает работу текущей версии. Место установки и применение учитываются отдельно.", ""]
    for key, project in sorted(projects.items(), key=lambda pair: (str(pair[1].get("name", "")).casefold(), pair[0])):
        lines += ["### "+text(project.get("name", key)), "", "Папка проекта: "+text(project.get("path", "")), "", "#### Рекомендованные навыки", ""]
        recommendations = project.get("recommendations", [])
        lines += ["- "+text(titles.get(item["skill_id"], item["skill_id"]))+": "+text(item.get("reason", "")) for item in recommendations] or ["Рекомендации пока не сохранены."]
        lines += ["", "#### Подтверждённые пользователем применения", ""]
        if not project.get("applications"):
            lines += ["Применения пока не записаны.", ""]
        for item in project.get("applications", []):
            lines += ["- "+text(item.get("date", ""))+" — "+text(titles.get(item["skill_id"], item["skill_id"])), "  - Задача: "+text(item.get("task", "")), "  - Проверенный пользователем результат: "+text(item.get("result", "")), "  - Подтверждение: "+project_evidence(item), "  - Версия комплекта: "+text(item.get("skill_sha256") or "не зафиксирована"), ""]
    return lines


def build_views(directory, events):
    from catalog import ORIGINS, load_cards
    directory = Path(directory)
    if (directory/"inventory.json").exists():
        inventory, cards = load_cards(directory)
    else:
        inventory, cards = {"updated_at": None}, []
    cards = [c for c in cards if c["state"] != "cache_only" or c["has_user_annotations"]]
    lines = header("Каталог навыков")
    from directions import state as direction_state
    user = read_json(directory/"user.json", {"skills": {}})
    themes = direction_state(user, inventory)
    lines += ["## Направления", "", "Один навык может относиться к нескольким темам. Происхождение учитывается отдельно.", ""]
    lines += ["- "+text(item["title"]) for item in themes["items"]]
    lines += [""]
    lines += [f"Сверка данных: {text(inventory.get('updated_at') or 'ещё не выполнена')}. Карточек: {len(cards)}.", "", "Наличие файлов, обнаружение отдельным процессом, доступность в текущем чате и проверенное применение — разные факты. Здесь показаны сохранённые сведения; актуальный путь и опыт для этой версии проверяет команда show.", ""]
    for origin, label in ORIGINS.items():
        group = sorted((c for c in cards if c["origin"] == origin), key=lambda c: c.get("title_ru", c["name"]))
        if not group:
            continue
        lines += [f"## {label} — {len(group)}", ""]
        for card in group:
            lines += [f"### {text(card.get('title_ru', card['name']))} ({text(card['name'])})", "", f"ID: {text(card['id'])}", "", f"Состояние: {text(STATES.get(card['state'], card['state']))}.", ""]
            lines += ["Направления: "+("; ".join(text(v) for v in card["directions"]) or "без направления")+".", ""]
            lines += ["Теги: "+("; ".join(text(v) for v in card.get("catalog_tags", [])) or "не назначены"), "", "Связанные ресурсы: "+("; ".join(text(v) for v in card.get("resource_ids", [])) or "не назначены"), ""]
            profile = card["author_profile"]
            lines += ["Автор: "+text(profile["name"] or "не указан")+".", ""]
            if profile["links"]:
                lines += ["Ссылки автора: "+" · ".join(author_links(profile)), ""]
            lines += ["Основание: "+text(card["author_evidence"]), ""]
            for group in card.get("capability_groups", []):
                lines += ["#### "+text(group["title"]), "", text(group["text"]), ""]
            if card.get("capability_limits"):
                lines += [text(card["capability_limits"]), ""]
            for field, title in (("tasks", "Метки для поиска"), ("helps", "Чем поможет"), ("output", "Результат"), ("choose_when", "Когда выбирать"), ("prepare", "Что подготовить"), ("notes", "Ваши заметки")):
                value = card.get(field)
                if value:
                    values = value if isinstance(value, list) else [value]
                    lines += [f"{title}: {'; '.join(text(v) for v in values)}", ""]
            if card.get("experience"):
                lines += ["Записанный опыт (при изменении комплекта может стать историческим):", ""]
                for experience in card["experience"]:
                    lines += ["- " + "; ".join(f"{label}: {text(experience[k])}" for k, label in (("date", "дата"), ("task", "задача"), ("result", "результат"), ("limitations", "ограничения"), ("skill_sha256", "версия комплекта")) if experience.get(k))]
                lines += [""]
    lines += project_lines(user, cards)
    search_lines = header("История поиска навыков")
    change_lines = header("История изменений каталога")
    requests = {e["id"]: e["data"].get("query", "") for e in events if e["kind"] == "search_requested"}
    for event in events:
        kind, data = event["kind"], event["data"]
        target = search_lines if kind.startswith("search_") else change_lines
        target += [f"## {text(event['at'])} — {text(KINDS.get(kind, kind))}", "", f"ID события: {text(event['id'])}", ""]
        query = data.get("query") or requests.get(data.get("search_id"))
        if query:
            target += [f"Запрос: {text(query)}", ""]
        if kind in ("direction_created", "direction_renamed"):
            target += ["Направление: "+text(data.get("title", "")), ""]
            if data.get("before_title"): target += ["Прежнее название: "+text(data["before_title"]), ""]
        if kind == "skill_directions_changed":
            target += ["Навык: "+text(data.get("skill_name", data.get("skill_id", ""))), "", "Направления: "+("; ".join(text(v) for v in data.get("direction_titles", [])) or "без направления"), ""]
        if kind == "skill_origin_changed":
            target += ["Навык: "+text(data.get("skill_name", data.get("skill_id", ""))), "", "Прежняя группа: "+text(ORIGINS.get(data.get("before_origin"), "не указана")), "", "Новая группа: "+text(ORIGINS.get(data.get("origin"), "не указана")), ""]
        if kind == "skill_author_changed":
            profile = data["author_profile"]
            target += ["Навык: "+text(data.get("skill_name", data.get("skill_id", ""))), "", "Прежний автор: "+text(data["before_profile"]["name"] or "не указан"), "", "Новый автор: "+text(profile["name"] or "не указан"), "", "Ссылки автора: "+(" · ".join(author_links(profile)) or "не указаны"), ""]
        if kind.startswith("skill_activation_"):
            status = {True: "Включено", False: "Отключено", None: "Не удалось определить"}
            target += ["Навык: "+text(data.get("skill_name", "")), "", "Использовать в Codex: "+status[data.get("actual_enabled")], "", "Проверка новым процессом Codex: "+("подтверждена" if data.get("verification") == "confirmed" else "не подтверждена"), ""]
            if data.get("restart_required"): target += ["Для применения изменения требуется перезапуск Codex.", ""]
        if kind in ("directions_initialized", "directions_seeded"):
            target += ["Навыков с исходными назначениями: "+text(data.get("skill_count", 0)), ""]
        if kind == "skill_application_verified":
            for key, label in (("title", "Навык"), ("task", "Задача"), ("result", "Результат"), ("limitations", "Ограничения"), ("skill_sha256", "Версия комплекта")):
                target += [label + ": " + text(data.get(key, "")), ""]
        if kind == "resource_catalog_changed":
            target += ["Ресурс: "+text(data.get("resource_name", "")), "", "Действие: "+text(data.get("action", "")), "", "Проект: "+text(data.get("project_name", "не указан")), "", "Запись каталога; разрешения Codex не изменялись.", ""]
        if kind == "skill_organization_changed":
            target += ["Навык: "+text(data.get("skill_name", "")), "", "Теги: "+"; ".join(text(v) for v in data.get("tags", [])), "", "Ресурсы: "+"; ".join(text(v) for v in data.get("resource_ids", [])), ""]
        if kind == "catalog_organization_migrated":
            target += ["Навыков классифицировано: "+text(len(data.get("classified_skill_ids", []))), "", "Источников уточнено: "+text(len(data.get("origin_skill_ids", []))), "", "Рекомендаций ресурсов проектам: "+text(len(data.get("project_links", []))), ""]
        if kind == "service_catalog_changed":
            target += ["Сервис: "+text(data.get("service_name", "")), "", "Действие: "+text(data.get("action", "")), "", "Проект: "+text(data.get("project_name", "не указан")), "", "Это запись каталога; разрешения Codex не изменялись.", ""]
        if kind.startswith("project_"):
            target += ["Проект: "+text(data.get("project_name", data.get("project_id", ""))), ""]
            if kind == "project_application_recorded":
                application = data.get("application", {})
                target += ["Подтверждение: пользователь сообщил о проверенном результате; автоматическое испытание не выполнялось.", "", "Задача: "+text(application.get("task", "")), "", "Результат: "+text(application.get("result", "")), "", "Материал результата: "+project_evidence(application), "", "Версия комплекта: "+text(application.get("skill_sha256") or "не зафиксирована"), ""]
        for key, label in (("action", "Операция"), ("outcome", "Наблюдавшийся итог"), ("reported_outcome", "Заявленный итог"), ("reason", "Причина"), ("detail", "Результат"), ("error", "Ошибка"), ("source_revision", "Версия исходника"), ("skill_id", "Навык"), ("wish_id", "Пожелание"), ("document", "Заметка")):
            if data.get(key):
                target += [f"{label}: {text(data[key])}", ""]
        if data.get("source"):
            url = safe_url(data["source"])
            target += [f"Источник: {text(url) if url else 'см. локальный журнал операции'}", ""]
        if data.get("counts"):
            target += ["Количество по состояниям: " + "; ".join(f"{text(k)}: {text(v)}" for k, v in data["counts"].items()), ""]
        changes = data.get("observed_changes", {})
        for key, label in (("added", "Появились"), ("changed", "Изменились"), ("not_confirmed", "Перестали подтверждаться")):
            if changes.get(key):
                target += [f"{label}: " + "; ".join(text(v) for v in changes[key]), ""]
        for candidate in data.get("candidates", []):
            url = safe_url(candidate.get("url", ""))
            target += [f"### {text(candidate.get('name', 'Вариант'))}", "", text(candidate.get("summary", "")), "", f"Источник: {text(url) if url else 'ссылка скрыта'}", "", "Статус: предложен. Это событие не подтверждает установку и испытание.", ""]
        if data.get("warnings"):
            target += ["Ограничения: " + "; ".join(text(v) for v in data["warnings"]), ""]
        if kind in ("operation_completed", "catalog_installed"):
            target += ["Проверка файлов не доказывает качество применения навыка.", ""]
    sources = {name: sha((directory/name).read_bytes()) if (directory/name).is_file() else None for name in ("inventory.json", "user.json", "history.jsonl")}
    status = header("Состояние представлений") + ["Один источник: inventory.json, user.json и проверенная цепочка history.jsonl в рабочем хранилище. Настройки, кеш поиска, резервные копии, полные конфиги Codex и исходники навыков сюда не копируются.", "", f"Событий: {len(events)}. Последнее: {text(events[-1]['id'] if events else 'нет')}.", "", "Контрольные суммы исходных данных:", ""] + [f"- {name}: {digest or 'файл отсутствует'}" for name, digest in sources.items()]
    services = header("Сервисы и подключения")
    services += ["Это сохранённые назначения и правила каталога. Текущее подключение, вход в сервис и инструменты чата проверяются отдельно в браузере. Ключи и конфигурация Codex сюда не экспортируются.", ""]
    registry = read_json(directory/"user.json", {}).get("service_catalog", {})
    projects = read_json(directory/"user.json", {}).get("project_catalog", {}).get("projects", {})
    policies = {"inherit": "По правилам Codex", "explicit": "Только по явной команде", "ask": "С подтверждением операции", "blocked": "Не использовать"}
    for key, item in registry.get("services", {}).items():
        services += ["## "+text(item.get("name", key)), "", "Правило: "+policies.get(item.get("policy", "explicit"), "Не определено"), "", text(item.get("notes", "")), ""]
        profile = item.get("profile", {})
        if profile:
            services += ["Название карточки: "+text(profile.get("title", "")), "Поставщик: "+text(profile.get("provider", "")), "Происхождение: "+text(profile.get("origin", "unknown")), "", text(profile.get("description", "")), ""]
            services += ["- "+text(value) for value in profile.get("capabilities", [])]
            services += ["", "Сайт: "+text(profile.get("website", "")), "Документация: "+text(profile.get("documentation", "")), ""]
            if profile.get("connection_steps"):
                services += ["### Как подключить", ""]
                services += [str(index)+". "+text(step) for index, step in enumerate(profile["connection_steps"], 1)]
                services += ["", "Документация подключения: "+text(profile.get("connection_documentation", "")), ""]
        for pid, bindings in registry.get("bindings", {}).items():
            if key in bindings:
                binding = bindings[key]
                services += ["- Проект: "+text(projects.get(pid, {}).get("name", pid))+". "+text(binding.get("purpose", ""))+". Правило: "+policies.get(binding.get("policy"), "Не определено")]
        services += [""]
    if not registry.get("services"):
        services += ["Пользовательские назначения пока не сохранены. Действующие подключения и состояние Meshy смотрите в браузерном разделе «Сервисы и подключения».", ""]
    from resources import descriptors, registry as resource_registry, summaries
    from connections import project_choices
    from service_profiles import ASSET as profile_asset
    resource_data = resource_registry(user)
    profiles = read_json(profile_asset)["profiles"]
    names = {x["id"]: x["name"] for x in project_choices(directory)}
    roles = {"recommended":"Рекомендован", "codex_use":"Используется через Codex", "runtime":"Интегрирован в приложение"}
    services += ["## Ресурсы и связи с проектами", "", "Ресурс описывает возможность. Подключение — обнаруженная настройка MCP или приложение. Компонент расширения не означает подключённый аккаунт. Фактические статусы не экспортируются, чтобы устаревшая копия не выглядела текущей проверкой.", ""]
    for item in descriptors():
        rid = item["id"]
        bindings = [(pid, entries[rid]) for pid, entries in resource_data["bindings"].items() if rid in entries]
        if rid not in resource_data["profiles"] and not bindings: continue
        profile = {**profiles.get(item["profile_id"], {}), **resource_data["profiles"].get(rid, {})}
        services += ["### "+text(profile.get("title", rid)), "", "ID: "+text(rid), "", "Поставщик: "+text(profile.get("provider", "")), "", text(profile.get("description", "")), "", "Теги: "+"; ".join(text(v) for v in profile.get("tags", item["tags"])), "", "Сайт: "+text(profile.get("website", "")), "", "Документация: "+text(profile.get("connection_documentation") or profile.get("documentation", "")), ""]
        for pid, binding in bindings:
            services += ["- Проект: "+text(names.get(pid, pid))+". "+roles.get(binding.get("role"), "Рекомендован")+". "+text(binding.get("purpose", ""))+". Правило: "+policies.get(binding.get("policy"), "Не определено")]
            if binding.get("evidence"): services += ["  Основание: "+text(binding["evidence"])]
        if profile.get("notes"): services += ["", "Заметки: "+text(profile["notes"])]
        services += [""]
    return {"Каталог.md": "\n".join(lines), "Сервисы и подключения.md": "\n".join(services), "История поиска.md": "\n".join(search_lines), "История изменений.md": "\n".join(change_lines), "Состояние экспорта.md": "\n".join(status)+"\n"}, sources


def export_locked(directory, documentation_root):
    """Caller owns the data lock; preflight all output files before any write."""
    directory = Path(directory).resolve()
    root = Path(documentation_root)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Documentation root must be an existing absolute directory")
    root = root.resolve()
    if root.is_relative_to(directory) or directory.is_relative_to(root):
        raise ValueError("Documentation and working data must be separate")
    output = root/VIEW_DIR
    if output.is_symlink() or output.is_junction():
        raise ValueError("Generated view directory must not be a link")
    events = read_events(directory)
    views, sources = build_views(directory, events)
    manifest_path = output/MANIFEST
    if manifest_path.is_symlink():
        raise ValueError("Export manifest must not be a link")
    old = read_json(manifest_path, {})
    if not isinstance(old, dict) or (old and (old.get("schema") != 1 or old.get("owner") != "codex-skill-catalog")):
        raise ValueError("Unknown export manifest; preserve it and review")
    pending_path = output/PENDING
    if pending_path.is_symlink() or pending_path.is_junction():
        raise ValueError("Pending export receipt must not be a link")
    pending = read_json(pending_path, {})
    if pending:
        if not isinstance(pending, dict):
            raise ValueError("Invalid pending export receipt")
        payload = {k: v for k, v in pending.items() if k != "sha256"}
        if pending.get("schema") != 1 or pending.get("owner") != "codex-skill-catalog" or pending.get("sha256") != sha(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()):
            raise ValueError("Pending export receipt integrity check failed")
        if not isinstance(pending.get("files"), dict) or set(pending["files"]) != set(views):
            raise ValueError("Unexpected pending export files")
        for planned in pending["files"].values():
            if not isinstance(planned, dict) or any(v is not None and (not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v)) for v in (planned.get("before"), planned.get("after"))):
                raise ValueError("Invalid pending export hashes")
    elif not isinstance(pending, dict):
        raise ValueError("Invalid pending export receipt")
    before_hashes = {}
    for name, content in views.items():
        path = output/name
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Refusing linked view: {path}")
        if path.exists():
            raw = path.read_bytes()
            before_hashes[name] = sha(raw)
            expected = content.encode("utf-8")
            prior = pending.get("files", {}).get(name, {})
            known_hashes = {old.get("files", {}).get(name), prior.get("before"), prior.get("after")}
            if raw != expected and (not raw.startswith(MARKER.encode()) or sha(raw) not in known_hashes):
                raise ValueError(f"View has untracked/manual edits; preserve it before export: {path}")
        else:
            before_hashes[name] = None
    manifest = {"schema": 1, "owner": "codex-skill-catalog", "sources": sources, "files": {n: sha(v.encode("utf-8")) for n, v in views.items()}}
    changed = [name for name in views if before_hashes[name] != manifest["files"][name]]
    if changed or old != manifest:
        plan = {"schema": 1, "owner": "codex-skill-catalog", "files": {name: {"before": before_hashes[name], "after": manifest["files"][name]} for name in views}}
        plan["sha256"] = sha(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode())
        atomic_json(pending_path, plan)
    written = []
    for name, content in views.items():
        path = output/name
        if not path.exists() or path.read_bytes() != content.encode("utf-8"):
            atomic_text(path, content)
            written.append(name)
    if old != manifest:
        atomic_json(manifest_path, manifest)
    for name, digest in manifest["files"].items():
        if sha((output/name).read_bytes()) != digest:
            raise OSError(f"Export read-back failed: {name}")
    if read_json(manifest_path) != manifest:
        raise OSError("Manifest read-back failed")
    pending_path.unlink(missing_ok=True)
    return {"root": str(root), "files_verified": len(views), "changed": written, "source_hashes": sources, "direction": "working data -> Markdown only"}


def export(directory, documentation_root=None, save=False):
    with locked(directory):
        settings = read_json(Path(directory)/"settings.json", {})
        root = documentation_root or settings.get("documentation_root")
        if not root:
            return {"status": "not_configured"}
        result = export_locked(directory, root)
        if save:
            settings["documentation_root"] = str(Path(root).resolve())
            atomic_json(Path(directory)/"settings.json", settings)
        return result


def automatic_export(directory):
    # The primary operation has already completed. A disconnected G: must not
    # turn a saved request/installation into an apparent failure or duplicate it.
    try:
        return export(directory)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        return {"warning": f"Working data saved; Markdown update pending: {error}"}
