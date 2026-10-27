"""Verified Russian reading copies; never replaces or activates a skill."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parents[1]/"assets/ru"
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MESSAGES = {
    "missing": "Русская инструкция пока не подготовлена.",
    "manifest_error": "Запись русского перевода повреждена. Требуется проверка каталога переводов.",
    "source_unavailable": "Не удалось подтвердить текущий исходник инструкции. Прежняя копия не подставляется.",
    "stale_source": "Исходная инструкция изменилась. Русский перевод нужно сверить с новой версией.",
    "damaged_translation": "Файл русского перевода отсутствует или изменился. Требуется проверка перевода.",
}


def checksum(raw):
    """Both manifest checksums refer to exact bytes, including line endings."""
    return hashlib.sha256(raw).hexdigest()


def load_manifest():
    """Keep a broken localization registry from hiding the rest of the catalogue."""
    path = ROOT/"manifest.json"
    if not path.exists():
        return {"schema": 1, "skills": {}}
    try:
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError("Oversized manifest")
        value = json.loads(path.read_text("utf-8-sig"))
        if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("skills"), dict):
            raise ValueError("Invalid manifest")
        return value
    except (OSError, ValueError, UnicodeError):
        return {"schema": 1, "skills": {}, "_error": "manifest_error"}


def translation_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("Invalid translation path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".md":
        raise ValueError("Invalid translation path")
    root = ROOT.resolve()
    path = (root/relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Translation path escapes its directory")
    return path


def entry_for(card, manifest):
    if manifest.get("_error"):
        raise ValueError("Invalid manifest")
    entry = manifest["skills"].get(card["id"])
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ValueError("Invalid entry")
    for key in ("source_sha256", "translation_sha256"):
        if not isinstance(entry.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", entry[key]):
            raise ValueError("Invalid checksum")
    for key in ("title_ru", "description_ru"):
        if not isinstance(entry.get(key), str) or not entry[key].strip() or "\x00" in entry[key]:
            raise ValueError("Invalid translated metadata")
    if entry.get("original_language") not in ("en", "ru", "mixed"):
        raise ValueError("Invalid language")
    if not isinstance(entry.get("reviewed_at"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["reviewed_at"]):
        raise ValueError("Invalid review date")
    if "source_path" in entry and (not isinstance(entry["source_path"], str) or not Path(entry["source_path"]).is_absolute()):
        raise ValueError("Invalid source binding")
    translation_path(entry.get("file"))
    return entry


def normalized(path):
    return str(Path(path).resolve()).casefold()


def source_location(card, cwd, entry):
    """Prefer ordinary selection even if it makes the saved translation stale.

    A cache binding is only for reading: it must be an indexed location and match
    the latest observed path, or the unique highest indexed numeric version.
    It never updates discovery, application_allowed, or the working skill.
    """
    import catalog
    selected = catalog.select_location(card, cwd)
    if selected:
        return selected, "selected"
    bound = entry.get("source_path")
    if not bound or not card["id"].startswith("plugin:"):
        return None, None
    locations = card.get("locations", [])
    candidates = [location for location in locations if normalized(location["path"]) == normalized(bound)]
    if len(candidates) != 1 or not Path(candidates[0]["path"]).is_file():
        return None, None
    candidate = candidates[0]
    observations = [item for item in card.get("observations", []) if item.get("path")]
    discoveries = [item for item in observations if item.get("kind") == "discovery"]
    authoritative = [item for item in discoveries if item.get("cwd") and normalized(item["cwd"]) == normalized(cwd)]
    if not authoritative:
        authoritative = discoveries
    sessions = [item for item in observations if item.get("kind") == "session" and item.get("at")]
    if authoritative:
        # Preserve ordinary selection's discovery and enabled-path precedence.
        # A missing current file must not revive an older readable binding.
        enabled = [item for item in authoritative if item.get("enabled") is True]
        current_paths = {normalized(item["path"]) for item in (enabled or authoritative)}
        if current_paths != {normalized(bound)}:
            return None, None
    elif sessions:
        latest = max(item["at"] for item in sessions)
        latest_paths = {normalized(item["path"]) for item in sessions if item["at"] == latest}
        if latest_paths != {normalized(bound)}:
            return None, None
    elif len({normalized(location["path"]) for location in locations}) > 1:
        versions = [(location.get("package_version"), normalized(location["path"])) for location in locations]
        if any(not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+)*", version) for version, _ in versions):
            return None, None
        ranked = [(tuple(int(part) for part in version.split(".")), path) for version, path in versions]
        highest = max(version for version, _ in ranked)
        newest = {path for version, path in ranked if version == highest}
        if newest != {normalized(bound)}:
            return None, None
    return candidate, "bound_file"


def outcome(status, entry=None):
    ready = status == "ready"
    result = {"status": status, "readable": ready, "language": "ru",
              "message": "Русская инструкция сверена с исходным файлом." if ready else MESSAGES[status]}
    if entry:
        result["reviewed_at"] = entry["reviewed_at"]
        result["original_language"] = entry["original_language"]
    return result


def inspect(card, cwd=None, manifest=None, include_text=False):
    manifest = load_manifest() if manifest is None else manifest
    try:
        entry = entry_for(card, manifest)
    except (OSError, ValueError, TypeError, KeyError):
        return outcome("manifest_error"), None, None
    if entry is None:
        return outcome("missing"), None, None
    try:
        location, verification = source_location(card, cwd or Path.cwd(), entry)
        if location is None:
            return outcome("source_unavailable", entry), entry, None
        source = Path(location["path"])
        if source.stat().st_size > MAX_DOCUMENT_BYTES:
            return outcome("source_unavailable", entry), entry, None
        raw_source = source.read_bytes()
    except (OSError, ValueError, TypeError, KeyError):
        return outcome("source_unavailable", entry), entry, None
    if checksum(raw_source) != entry["source_sha256"]:
        return outcome("stale_source", entry), entry, None
    try:
        path = translation_path(entry["file"])
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            return outcome("damaged_translation", entry), entry, None
        raw = path.read_bytes()
        if checksum(raw) != entry["translation_sha256"]:
            return outcome("damaged_translation", entry), entry, None
        text = raw.decode("utf-8-sig")
        if not text.strip():
            return outcome("damaged_translation", entry), entry, None
    except (OSError, ValueError, UnicodeError):
        return outcome("damaged_translation", entry), entry, None
    result = outcome("ready", entry)
    result["source_verification"] = verification
    return result, entry, text if include_text else None


def heading_slugs(text):
    """The same conservative heading/slug rules used by the reader JavaScript."""
    import unicodedata
    text = re.sub(r"^\ufeff?---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)", "", text)
    headings, counts, fence = [], {}, None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if not heading:
            continue
        value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading[2])
        value = re.sub(r"<[^>]*>", "", value)
        value = re.sub(r"[`*_~]", "", value).lower()
        value = "".join(char for char in value if unicodedata.category(char)[0] in "LN" or char.isspace() or char in "_-")
        base = re.sub(r"\s", "-", value.strip())
        count = counts.get(base, 0)
        counts[base] = count + 1
        headings.append((len(heading[1]), base + (f"-{count}" if count else "")))
    return headings


def heading_aliases(source, translation):
    original, translated = heading_slugs(source), heading_slugs(translation)
    if [level for level, _ in original] != [level for level, _ in translated]:
        return {}
    return {left: right for (_, left), (_, right) in zip(original, translated) if left and right}


def read(card, cwd=None, manifest=None):
    result, entry, text = inspect(card, cwd, manifest, include_text=True)
    if not result["readable"]:
        raise ValueError(result["message"])
    notice = "Русский текст для чтения. Команды, имена инструментов и адреса сохранены в исходном виде."
    if card.get("portability") == "project_only":
        notice += " Этот навык применяется только в своём проекте."
    elif not card.get("application_allowed"):
        notice += " Наличие текста не подтверждает подключение навыка в текущем чате."
    # Bind navigation to the same verified source version, even if files changed
    # after inspect(). Never invent an alias for unmatched document structure.
    try:
        location, _ = source_location(card, cwd or Path.cwd(), entry)
        if location is None:
            raise OSError("Source disappeared")
        source = Path(location["path"])
        if source.stat().st_size > MAX_DOCUMENT_BYTES:
            raise OSError("Source too large")
        raw_source = source.read_bytes()
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise ValueError(MESSAGES["source_unavailable"]) from error
    if checksum(raw_source) != entry["source_sha256"]:
        raise ValueError(MESSAGES["stale_source"])
    try:
        aliases = heading_aliases(raw_source.decode("utf-8-sig"), text)
    except UnicodeError:
        aliases = {}
    return {"title": card.get("title_ru") or entry["title_ru"], "description": entry["description_ru"], "markdown": text,
            "language": "ru", "notice": notice, "instruction_localization": result,
            "source_sha256": entry["source_sha256"], "translation_sha256": entry["translation_sha256"], "heading_aliases": aliases}
