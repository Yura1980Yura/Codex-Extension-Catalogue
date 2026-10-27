"""Personal skill inventory, separate user annotations, compact task navigation."""
from __future__ import annotations

import argparse
import directions as themes
import origins as ownership
import authors
import activation
import localization
import organization
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from discovery import discover
from storage import atomic_json, locked, now, read_json
from journal import read_events, record_locked

SKILL_ROOT = Path(__file__).resolve().parents[1]
ORIGINS = ownership.ORIGINS


def normalized(path):
    return os.path.normcase(str(Path(path).resolve()))


def bundle_fingerprint(folder, package_version=None):
    files = {}
    for path in sorted(Path(folder).rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "installation.json":
            files[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps({"files": files, "package_version": package_version}, sort_keys=True).encode("utf-8")).hexdigest()


def frontmatter(path):
    """Read discovery fields only; never execute or interpret skill body as commands."""
    text = Path(path).read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.S)
    if not match:
        raise ValueError(f"No frontmatter: {path}")
    raw = match.group(1)
    fields = {}
    # These fields are strings in the skill specification. Handle block descriptions.
    for key in ("name", "description"):
        m = re.search(rf"^{key}:\s*(.*)$", raw, re.M)
        if not m:
            raise ValueError(f"Missing {key}: {path}")
        value = m.group(1).strip()
        if value in (">", ">-", "|", "|-"):
            lines = raw[m.end():].splitlines()
            block = []
            for line in lines:
                if line and not line[0].isspace():
                    break
                if line.strip():
                    block.append(line.strip())
            value = " ".join(block)
        elif value.startswith('"') and value.endswith('"'):
            value = json.loads(value)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("''", "'")
        fields[key] = value
    version = re.search(r'^\s+version:\s*[\"\x27]?([^\n\"\x27]+)', raw, re.M)
    fields["declared_version"] = version.group(1).strip() if version else None
    return fields


def repo_identity(root):
    try:
        value = subprocess.check_output(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, stderr=subprocess.DEVNULL, text=True, encoding="utf-8").strip()
        return normalized(value)
    except (OSError, subprocess.SubprocessError):
        return normalized(root)


def vendor_index(projects):
    result = {}
    for root in projects:
        lock = Path(root) / ".agents/skills/writing-tools.lock.json"
        if not lock.exists():
            continue
        data = read_json(lock)
        for source in data["sources"]:
            groups = {}
            for file in source["files"]:
                relative = Path(file["installed"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Unsafe vendor path in {lock}")
                if len(relative.parts) < 4 or relative.parts[:2] != (".agents", "skills"):
                    raise ValueError(f"Unexpected vendor path in {lock}")
                groups.setdefault(relative.parts[2], []).append(file)
            for name, files in groups.items():
                changed, missing = [], []
                for file in files:
                    path = Path(root) / file["installed"]
                    if not path.exists():
                        missing.append(file["installed"])
                    else:
                        raw = path.read_bytes().replace(b"\r\n", b"\n")
                        if hashlib.sha256(raw).hexdigest() != file["sha256"]:
                            changed.append(file["installed"])
                result[normalized(Path(root)/".agents/skills"/name/"SKILL.md")] = {
                    "repository": source["repository"], "commit": source["commit"],
                    "lock_path": str(lock), "user_modified": bool(changed),
                    "modified_files": changed, "missing_files": missing,
                }
    return result


def plugin_parts(path, home):
    try:
        parts = Path(path).resolve().relative_to(home / ".codex/plugins/cache").parts
        if len(parts) >= 6 and parts[3] == "skills":
            return {"plugin_id": f"{parts[1]}@{parts[0]}", "version": parts[2], "market": parts[0]}
    except ValueError:
        pass
    return None


def refresh(directory, home, cwd, project_roots=(), session=None, discovery_fn=discover):
    with locked(directory):
        themes.recover_locked(directory)
        read_events(directory)  # Reject damaged history before changing the inventory.
        settings = read_json(directory / "settings.json", {})
        previous = read_json(directory / "inventory.json", {"skills": {}})
        themes.state(read_json(directory / "user.json", {"schema": 1, "skills": {}}), previous)  # Validate before changing the inventory.
        projects = list(dict.fromkeys(str(Path(p).resolve()) for p in [*settings.get("project_roots", []), *project_roots, cwd]))
        present_projects = [p for p in projects if Path(p).is_dir()]
        stamp, warnings = now(), []
        vendors = vendor_index([home, *present_projects])
        identities = {normalized(p): repo_identity(p) for p in present_projects}
        records, bundle_hashes = {}, {}
        curation = read_json(SKILL_ROOT / "assets/curation.json", {})

        def add(path, location_kind, scope=None, project=None, observation=None, observed_name=None):
            path = Path(path)
            try:
                meta = frontmatter(path)
                raw = path.read_bytes()
            except (OSError, ValueError) as error:
                warnings.append(f"Cannot inspect {path}: {error}")
                return
            name = meta["name"]
            plugin = plugin_parts(path, home)
            vendor = vendors.get(normalized(path))
            if plugin:
                key = f"plugin:{plugin['plugin_id']}:{name.casefold()}"
            elif vendor:
                key = f"vendor:{vendor['repository']}:{name}"
            elif scope == "system" or path.parent.parent.name == ".system":
                key = f"system:{name}"
            else:
                identity = identities.get(normalized(project), normalized(path.parent)) if project else normalized(path.parent)
                key = f"local:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:12]}:{name}"
            # A session snapshot has no project scope. Attach it to an already
            # inspected identical instruction rather than creating another card.
            same_file = next((k for k, r in records.items() if r["name"] == name and any(normalized(x["path"]) == normalized(path) for x in r["locations"])), None)
            if same_file:
                key = same_file
            item = records.setdefault(key, {
                "id": key, "name": name, "aliases": [], "description": meta["description"],
                "declared_version": meta["declared_version"], "locations": [], "observations": [],
                "origin": "unknown", "origin_evidence": None, "source": None,
                "user_modified": None, "portability": "unknown", "last_seen": stamp,
            })
            curated = curation.get(name, {})
            for field in ("title_ru", "tasks", "helps", "output", "choose_when", "prepare", "dependencies", "portability", "origin", "origin_evidence", "source", "capability_groups", "capability_limits"):
                if field in curated:
                    item[field] = curated[field]
            if vendor:
                item.update(origin="third_party", origin_evidence="Проверенный writing-tools.lock.json", source=vendor, user_modified=vendor["user_modified"], portability="portable")
            elif plugin and plugin["market"] in ("openai-bundled", "openai-primary-runtime", "openai-curated-remote"):
                item.update(origin="builtin", origin_evidence="Пакет поставки OpenAI; авторство конкретного навыка отдельно не подтверждено", source={"plugin_id": plugin["plugin_id"], "author": None})
            elif key.startswith("system:"):
                item.update(origin="builtin", origin_evidence="Системный навык Codex (scope=system)", source={"author": "OpenAI"})
            if name.startswith(("aria-", "midnight-cafe-")):
                item["portability"] = "project_only"
            if observed_name and observed_name not in item["aliases"]:
                item["aliases"].append(observed_name)
            location = {"path": str(path), "resolved_path": str(path.resolve()), "kind": location_kind, "scope": scope, "project": project, "sha256": hashlib.sha256(raw).hexdigest(), "package_version": plugin["version"] if plugin else None}
            if location_kind != "cache":
                bundle_key = (normalized(path.parent), location["package_version"])
                if bundle_key not in bundle_hashes:
                    bundle_hashes[bundle_key] = bundle_fingerprint(path.parent, location["package_version"])
                location["skill_sha256"] = bundle_hashes[bundle_key]
            existing = next((x for x in item["locations"] if normalized(x["path"]) == normalized(path)), None)
            if existing is None:
                item["locations"].append(location)
            elif existing["kind"] == "cache" and location_kind != "cache":
                existing.update(location)
            if observation and observation not in item["observations"]:
                observed = {**observation, "path": str(path)}
                if observed not in item["observations"]:
                    item["observations"].append(observed)

        # All caches are evidence of files only, never evidence of an enabled plugin.
        cache = home / ".codex/plugins/cache"
        if cache.exists():
            for path in cache.glob("*/*/*/skills/*/SKILL.md"):
                add(path, "cache")
        for parent in (home/".agents/skills", home/".codex/skills", home/".codex/skills/.system"):
            if parent.exists():
                for path in parent.glob("*/SKILL.md"):
                    add(path, "installation", scope="system" if parent.name == ".system" else "user")
        for root in present_projects:
            for path in (Path(root)/".agents/skills").glob("*/SKILL.md"):
                add(path, "installation", scope="repo", project=root)
        try:
            discovered = discovery_fn(present_projects, settings.get("codex_executable"))
            discovery_status = "ok"
            for row in discovered["data"]:
                warnings.extend(f"Discovery {row['cwd']}: {error}" for error in row.get("errors", []))
                for skill in row["skills"]:
                    observation = {"kind": "discovery", "cwd": row["cwd"], "at": stamp, "enabled": skill.get("enabled"), "client": discovered.get("client")}
                    add(skill["path"], "discovered", scope=skill.get("scope"), project=row["cwd"] if skill.get("scope") == "repo" else None, observation=observation, observed_name=skill["name"])
        except Exception as error:
            # A failed probe must not promote cache files or reuse old enablement.
            discovery_status = "unavailable"
            warnings.append(f"Codex discovery unavailable: {type(error).__name__}: {error}")
        if session:
            snapshot = read_json(session)
            for skill in snapshot["skills"]:
                add(skill["path"], "session", observation={"kind": "session", "label": snapshot["label"], "at": snapshot["observed_at"]}, observed_name=skill["name"])
        for key, item in records.items():
            item["state"] = "present" if any(x["kind"] != "cache" for x in item["locations"]) else "cache_only"
            old = previous["skills"].get(key, {})
            if item["state"] == "cache_only" and old.get("state") in ("present", "unconfirmed", "missing"):
                item["state"] = "unconfirmed"
            item["first_seen"] = old.get("first_seen", stamp)
            # Historical observations carry no current enablement claim.
            item["history"] = old.get("history", [])[-20:] + ([{"at": previous.get("updated_at"), "observations": old["observations"]}] if old.get("observations") else [])
        for key, old in previous["skills"].items():
            if key not in records:
                records[key] = {**old, "state": "missing", "locations": [], "observations": [], "history": old.get("history", [])[-20:]}
        result = {"schema": 1, "updated_at": stamp, "discovery_status": discovery_status, "projects": projects, "warnings": warnings, "skills": dict(sorted(records.items()))}
        atomic_json(directory / "inventory.json", result)
        settings["project_roots"] = list(dict.fromkeys([*settings.get("project_roots", []), *map(str, project_roots)]))
        atomic_json(directory / "settings.json", settings)
        def installed_hashes(item):
            return sorted({x.get("skill_sha256", x["sha256"]) for x in item.get("locations", []) if x["kind"] != "cache"})
        before = previous["skills"]
        delta = {
            "added": [k for k, v in records.items() if v["state"] == "present" and before.get(k, {}).get("state") != "present"],
            "changed": [k for k, v in records.items() if v["state"] == "present" and before.get(k, {}).get("state") == "present" and installed_hashes(v) != installed_hashes(before[k])],
            "not_confirmed": [k for k, v in records.items() if v["state"] in ("missing", "unconfirmed") and before.get(k, {}).get("state") == "present"],
        }
        themes.seed_locked(directory, result)
        record_locked(directory, "inventory_refreshed", {"cwd": str(cwd), "discovery_status": discovery_status, "counts": dict(Counter(x["state"] for x in records.values())), "observed_changes": delta, "note": "Observed differences; installer, author and exact operation time cannot be inferred"})
        return result


def load_cards(directory, cwd=None, only_id=None):
    inventory = read_json(directory / "inventory.json")
    if inventory is None:
        raise ValueError("Индекс ещё не создан. Выполни refresh --cwd '<текущий проект>'.")
    user = read_json(directory / "user.json", {"skills": {}})
    if (directory/themes.PENDING).exists():
        raise ValueError("Сохранение настроек каталога прервалось. Выполните directions --initialize или откройте менеджер для восстановления.")
    directions = themes.state(user, inventory)
    titles = {item["id"]: item["title"] for item in directions["items"]}
    curation = read_json(SKILL_ROOT / "assets/curation.json", {})
    author_defaults = authors.load_defaults()
    russian = localization.load_manifest()
    home = directory.parent.parent if directory.parent.name == ".codex" else Path.home()
    try:
        activation_config = activation.configuration(home)
    except (OSError, ValueError):
        activation_config = None
    cards = []
    items = [(only_id, inventory["skills"][only_id])] if only_id in inventory["skills"] else inventory["skills"].items()
    for key, item in items:
        card = dict(item)
        card["activation"] = activation.state(card, home, activation_config)
        card["direction_ids"] = directions["assignments"].get(key, [])
        card["directions"] = [titles[x] for x in card["direction_ids"]]
        for field in ("capability_groups", "capability_limits"):
            if field in curation.get(card["name"], {}):
                card[field] = curation[card["name"]][field]
        overlay = user["skills"].get(key, {})
        metadata = organization.skill_metadata(card, user)
        card.update(catalog_tags=metadata['tags'], resource_ids=metadata['resource_ids'], organization_revision=metadata['revision'])
        card["has_user_annotations"] = bool(overlay)
        for field in ("title_ru", "tasks", "helps", "output", "choose_when", "prepare", "notes", "experience"):
            if field in overlay:
                card[field] = overlay[field]
        origin_state = ownership.state(user, inventory, key)
        card.update(origin=origin_state["origin"], origin_evidence=origin_state["origin_evidence"], origin_revision=origin_state["revision"])
        author_state = authors.state(user, inventory, key, author_defaults)
        card.update(author_profile=author_state["profile"], author_revision=author_state["revision"], author_evidence=author_state["evidence"])
        translation, translated, _ = localization.inspect(card, cwd, russian)
        card["instruction_localization"] = translation
        card["description_original"] = card["description"]
        if translation["readable"]:
            card["description_ru"] = translated["description_ru"]
            card["description"] = translated["description_ru"]
            if "title_ru" not in overlay:
                card["title_ru"] = translated["title_ru"]
        else:
            card["description"] = translation["message"]
        cards.append(card)
    return inventory, cards


def select_location(card, cwd):
    def rank(location):
        discoveries = [o for o in card["observations"] if o["kind"] == "discovery" and normalized(o["cwd"]) == normalized(cwd) and o.get("enabled") is True and normalized(o["path"]) == normalized(location["path"])]
        local = location.get("project") and Path(cwd).resolve().is_relative_to(Path(location["project"]).resolve())
        return (bool(discoveries), bool(local), location["scope"] == "user", location["kind"] != "cache")
    usable = [x for x in card["locations"] if x["kind"] != "cache" and Path(x["path"]).is_file()]
    authoritative = [o for o in card["observations"] if o["kind"] == "discovery" and normalized(o["cwd"]) == normalized(cwd)]
    if not authoritative and card["id"].startswith("plugin:"):
        authoritative = [o for o in card["observations"] if o["kind"] == "discovery"]
    if authoritative:
        enabled = [o for o in authoritative if o.get("enabled") is True]
        paths = {normalized(o["path"]) for o in (enabled or authoritative)}
        usable = [x for x in usable if normalized(x["path"]) in paths]
    elif card["id"].startswith("plugin:"):
        sessions = [o for o in card["observations"] if o["kind"] == "session"]
        if sessions:
            latest = max(o["at"] for o in sessions)
            paths = {normalized(o["path"]) for o in sessions if o["at"] == latest}
            usable = [x for x in usable if normalized(x["path"]) in paths]
    return max(usable, key=rank) if usable else None


def availability(card, cwd):
    control = card.get("activation", {})
    if control.get("supported") and control.get("configured"):
        return "configured_enabled" if control["enabled"] else "configured_disabled"
    observations = [x for x in card["observations"] if x["kind"] == "discovery" and normalized(x["cwd"]) == normalized(cwd)]
    if observations:
        if not any(x.get("enabled") is True for x in observations):
            return "discovered_disabled"
        return "discovered_enabled" if select_location(card, cwd) else "source_unavailable"
    location = select_location(card, cwd)
    if location and card["portability"] == "portable":
        return "read_via_catalog"
    if location and card["portability"] == "project_only":
        return "project_only"
    return "unknown"


TASK_GROUPS = [
    ("редактур", "редактор", "редакт", "edit", "коррект", "вычит"),
    ("литератур", "писат", "роман", "рассказ", "fiction", "сюжет"),
    ("rea", "разбор", "реверс", "декомп", "reverse", "бинар"),
    ("документ", "word", "docx", "pdf"),
    ("изображ", "картин", "image", "иллюстрац"),
    ("игр", "game", "midnight"),
    ("читател", "скуч", "непониман", "перестаёт понимать", "beta-reader"),
]


def score(card, task):
    query = task.casefold()
    words = re.findall(r"[\w-]+", query)
    # Ignore conversational filler; expanded task families supply Russian/English routing.
    filler = {"меня", "есть", "этой", "задачи", "какие", "подойдут", "покажи", "навыки", "моём", "каталоге", "поможет", "помогут"}
    meaningful = [w for w in words if w not in filler and (len(w) > 3 or w in ("rea", "pdf"))]
    fields = " ".join(str(card.get(k, "")) for k in ("name", "aliases", "title_ru", "tasks", "helps", "output", "description", "description_original", "author_profile")).casefold()
    if re.search(r"\brea\b|программ|бинар|декомп|реверс|reverse.engineer", query):
        return 100 if "разбор программ" in card.get("tasks", []) else 0
    def occurs(word):
        return bool(re.search(r"\brea\b", fields)) if word == "rea" else word in fields
    points = sum(2 for w in meaningful if occurs(w))
    for family in TASK_GROUPS:
        if any(w in query for w in family):
            points += sum(1 for w in family if occurs(w))
    return points


def list_cards(directory, task=None, origin=None, cwd=None, include_cache=False, direction=None):
    inventory, cards = load_cards(directory, cwd)
    cards = [c for c in cards if (include_cache or c["state"] != "cache_only" or c["has_user_annotations"]) and (not origin or c["origin"] == origin)]
    if direction:
        cards = [c for c in cards if direction in c["direction_ids"] or direction in c["directions"] or (direction == "unassigned" and not c["direction_ids"])]
    if task:
        cards = [c for c in cards if score(c, task) > 0]
        cards.sort(key=lambda c: (-score(c, task), c["name"]))
    else:
        cards.sort(key=lambda c: (c["origin"], c.get("title_ru", c["name"])))
    return {"updated_at": inventory["updated_at"], "counts": dict(Counter(c["origin"] for c in cards)), "warnings": inventory["warnings"], "skills": [{"id": c["id"], "title_ru": c.get("title_ru", c["name"]), "name": c["name"], "origin": c["origin"], "author_profile": c["author_profile"], "instruction_localization": c["instruction_localization"], "tasks": c.get("tasks", []), "direction_ids": c["direction_ids"], "directions": c["directions"], "helps": c.get("helps", c["description"]), "state": c["state"], "availability": availability(c, cwd or Path.cwd()), "session_observations": [o for o in c["observations"] if o["kind"] == "session"], "historical_session_observations": [o for h in c.get("history", []) for o in h.get("observations", []) if o["kind"] == "session"][-5:], "experience_count": len(c.get("experience", []))} for c in cards]}


def show_card(directory, key, cwd):
    inventory, cards = load_cards(directory, cwd, only_id=key)
    exact = [c for c in cards if c["id"] == key]
    matches = exact or [c for c in cards if c["name"] == key or key in c["aliases"]]
    if len(matches) != 1:
        raise ValueError(f"Нужен однозначный id; найдено: {[c['id'] for c in matches]}")
    card = matches[0]
    location = select_location(card, cwd)
    project_matches = any(x.get("project") and Path(cwd).resolve().is_relative_to(Path(x["project"]).resolve()) for x in card["locations"])
    allowed = bool(location) and availability(card, cwd) not in ("discovered_disabled", "configured_disabled") and (card["portability"] != "project_only" or project_matches)
    current_hash = hashlib.sha256(Path(location["path"]).read_bytes()).hexdigest() if location else None
    current_bundle = bundle_fingerprint(Path(location["path"]).parent, location["package_version"]) if location else None
    card.update(availability=availability(card, cwd), application_allowed=allowed, instruction_path=location["path"] if allowed else None, instruction_sha256=current_hash, skill_sha256=current_bundle, inventory_stale=bool(location and (current_hash != location["sha256"] or current_bundle != location.get("skill_sha256"))))
    card["verified_experience"] = [x for x in card.get("experience", []) if current_bundle and x.get("skill_sha256") == current_bundle]
    card["historical_experience"] = [x for x in card.get("experience", []) if x not in card["verified_experience"]]
    card["availability_note"] = "Обнаружение отдельным процессом и датированные наблюдения; проверь список доступных навыков текущего чата."
    for field in ("output", "choose_when", "prepare", "dependencies"):
        card.setdefault(field, "Не описано отдельно; прочитай выбранную инструкцию.")
    return card


def add_note(directory, key, text):
    with locked(directory):
        themes.recover_locked(directory)
        read_events(directory)
        keys = read_json(directory / "inventory.json", {"skills": {}})["skills"]
        if key not in keys:
            raise ValueError(f"Unknown ID: {key}")
        user = read_json(directory / "user.json", {"schema": 1, "skills": {}})
        user["skills"].setdefault(key, {}).setdefault("notes", []).append(text)
        atomic_json(directory / "user.json", user)
        event = record_locked(directory, "user_note_added", {"skill_id": key, "note_number": len(user["skills"][key]["notes"])})
    return {"id": key, "note_added": True, "event_id": event["id"]}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path.home()/".codex/skill-catalog")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    services = sub.add_parser("services", help="Прочитать подключения Codex и связи сервисов; секреты не выводятся")
    services.add_argument("--project", help="ID проекта из ответа services")
    services.add_argument("--meshy-plan", action="store_true")
    update = sub.add_parser("refresh")
    update.add_argument("--cwd", default=str(Path.cwd()))
    update.add_argument("--project-root", action="append", default=[])
    update.add_argument("--session", type=Path)
    listing = sub.add_parser("list")
    listing.add_argument("--task")
    listing.add_argument("--direction", help="Stable direction ID, exact title, or unassigned")
    listing.add_argument("--origin", choices=ORIGINS)
    listing.add_argument("--cwd", default=str(Path.cwd()))
    listing.add_argument("--include-cache", action="store_true")
    showing = sub.add_parser("show")
    showing.add_argument("id")
    showing.add_argument("--cwd", default=str(Path.cwd()))
    reading = sub.add_parser("instruction", help="Прочитать полную русскую инструкцию, сверенную с оригиналом")
    reading.add_argument("id")
    reading.add_argument("--cwd", default=str(Path.cwd()))
    noting = sub.add_parser("note")
    noting.add_argument("id")
    noting.add_argument("--text", required=True)
    exporting = sub.add_parser("export", help="Update owned Markdown views from working data")
    direction_parser = sub.add_parser("directions", help="Read personal directions; initialize them once")
    direction_parser.add_argument("--initialize", action="store_true")
    exporting.add_argument("--docs-root", type=Path)
    exporting.add_argument("--save", action="store_true", help="Remember this documentation root after a successful export")
    finding = sub.add_parser("search", help="Find published skills on demand; records request and proposals")
    finding.add_argument("--query", required=True)
    finding.add_argument("--limit", type=int, default=5)
    finding.add_argument("--refresh-sources", action="store_true")
    begin_search = sub.add_parser("search-start", help="Record a request before browser/plugin research")
    begin_search.add_argument("--query", required=True)
    end_search = sub.add_parser("search-finish", help="Save inspected web/plugin proposals")
    end_search.add_argument("id")
    end_search.add_argument("--results-file", type=Path, required=True)
    history_parser = sub.add_parser("history")
    history_parser.add_argument("--limit", type=int, default=10)
    history_parser.add_argument("--kind")
    start_operation = sub.add_parser("operation-start")
    start_operation.add_argument("--action", choices=["install", "replace", "update", "remove"], required=True)
    start_operation.add_argument("--target", type=Path, required=True)
    start_operation.add_argument("--source", required=True)
    start_operation.add_argument("--reason", required=True)
    finish_operation = sub.add_parser("operation-finish")
    finish_operation.add_argument("id")
    finish_operation.add_argument("--outcome", choices=["success", "failure", "interrupted"], required=True)
    finish_operation.add_argument("--detail", required=True)
    args = parser.parse_args()
    try:
        if args.command == "services":
            import connections
            result = connections.meshy_plan() if args.meshy_plan else connections.view(args.data_dir, args.home, args.project)
        elif args.command == "refresh":
            inventory = refresh(args.data_dir, args.home, args.cwd, args.project_root, args.session)
            result = {"updated_at": inventory["updated_at"], "discovery_status": inventory["discovery_status"], "counts": dict(Counter(x["state"] for x in inventory["skills"].values())), "warnings": inventory["warnings"]}
        elif args.command == "list":
            result = list_cards(args.data_dir, args.task, args.origin, args.cwd, args.include_cache, args.direction)
        elif args.command == "directions":
            if args.initialize:
                result = themes.initialize(args.data_dir)
            else:
                with locked(args.data_dir):
                    themes.recover_locked(args.data_dir)
                    result = themes.state(read_json(args.data_dir/"user.json", {"skills": {}}), read_json(args.data_dir/"inventory.json"))
        elif args.command == "show":
            result = show_card(args.data_dir, args.id, args.cwd)
        elif args.command == "instruction":
            with locked(args.data_dir):
                result = localization.read(show_card(args.data_dir, args.id, args.cwd), args.cwd)
        elif args.command == "note":
            result = add_note(args.data_dir, args.id, args.text)
        elif args.command == "export":
            from exporter import export
            result = export(args.data_dir, args.docs_root, args.save)
        elif args.command == "search":
            from market import search
            result = search(args.data_dir, args.query, args.limit, args.refresh_sources)
        elif args.command == "search-start":
            from market import start_search
            result = start_search(args.data_dir, args.query)
        elif args.command == "search-finish":
            from market import finish_search
            results = read_json(args.results_file)
            result = finish_search(args.data_dir, args.id, results["candidates"], results.get("warnings", []), results.get("sources", []))
        elif args.command == "history":
            from journal import read_events, render
            if not 1 <= args.limit <= 1000:
                raise ValueError("History limit must be between 1 and 1000")
            with locked(args.data_dir):
                events = read_events(args.data_dir)
                render(args.data_dir, events)
            result = {"history_file": str(args.data_dir/"HISTORY.md"), "events": [x for x in events if not args.kind or x["kind"] == args.kind][-args.limit:]}
        elif args.command == "operation-start":
            from journal import operation_start
            result = operation_start(args.data_dir, args.action, args.target, args.source, args.reason)
        else:
            from journal import operation_finish
            result = operation_finish(args.data_dir, args.id, args.outcome, args.detail)
        if args.command not in ("list", "show", "instruction", "export"):
            from exporter import automatic_export
            result["documentation_export"] = automatic_export(args.data_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        from exporter import automatic_export
        result = {"error": str(error)}
        if args.command != "instruction":
            result["documentation_export"] = automatic_export(args.data_dir)
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
