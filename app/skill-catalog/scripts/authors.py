"""Editable author profiles, independent of ownership and installation source."""
from copy import deepcopy
import ipaddress
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

import directions as transactions
import journal as j
from storage import locked, now, read_json

PROFILES = Path(__file__).resolve().parents[1]/"assets/author-profiles.json"
Conflict = transactions.Conflict


def controls(value):
    return any(unicodedata.category(char) in ("Cc", "Cf") for char in value)


def valid_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048 or controls(value) or any(char.isspace() for char in value) or any(char in value for char in "\\<>"):
        raise ValueError("Ссылка должна содержать до 2048 символов без пробелов, управляющих знаков, угловых скобок и обратной косой черты.")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        if parts.scheme not in ("http", "https") or not hostname or parts.username is not None or parts.password is not None:
            raise ValueError()
        parts.port  # Validate the port, including its range.
        if parts.netloc.endswith(":"): raise ValueError()
        if ":" in hostname:
            if "%" in hostname or not re.fullmatch(r"\[[^\]]+\](?::\d+)?", parts.netloc): raise ValueError()
            ipaddress.IPv6Address(hostname)
        else:
            domain = (hostname[:-1] if hostname.endswith(".") else hostname).encode("idna").decode("ascii")
            if not domain or len(domain) > 253 or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label) for label in domain.split(".")):
                raise ValueError()
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", domain):
                ipaddress.IPv4Address(domain)
    except (ValueError, UnicodeError):
        raise ValueError("Укажите корректную ссылку http:// или https:// с именем сайта, без логина и пароля.") from None
    return value


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != {"name", "links"}:
        raise ValueError("Укажите имя автора и список ссылок.")
    name, links = profile["name"], profile["links"]
    if not isinstance(name, str) or len(name) > 160 or controls(name):
        raise ValueError("Имя автора должно содержать до 160 символов без управляющих знаков.")
    if not isinstance(links, list) or len(links) > 8:
        raise ValueError("Можно сохранить не больше 8 ссылок автора.")
    result = []
    for link in links:
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise ValueError("У каждой ссылки нужны название и адрес.")
        label = link["label"]
        if not isinstance(label, str) or not label.strip() or len(label) > 80 or controls(label):
            raise ValueError("Название ссылки должно содержать от 1 до 80 символов без управляющих знаков.")
        result.append({"label": label.strip(), "url": valid_url(link["url"])})
    return {"name": name.strip(), "links": result}


def load_defaults():
    return read_json(PROFILES, {"schema": 1, "repositories": {}, "skills": {}})


def initial(item, defaults):
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    repository = source.get("repository")
    match = defaults.get("skills", {}).get(item["id"])
    if match is None and isinstance(repository, str):
        match = next((entry for key, entry in defaults.get("repositories", {}).items() if key.casefold() == repository.casefold()), None)
    if match is not None:
        return validate(match["profile"]), match["evidence"]
    profile = {"name": "", "links": []}
    author = source.get("author")
    if isinstance(author, str) and len(author) <= 160 and not controls(author):
        profile["name"] = author.strip()
    candidates = []
    if isinstance(repository, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        candidates.append({"label": "GitHub", "url": "https://github.com/"+repository})
    if isinstance(source.get("url"), str):
        candidates.append({"label": "Источник навыка", "url": source["url"]})
    for link in candidates:
        try: valid_url(link["url"])
        except ValueError: continue
        if not any(existing["url"] == link["url"] for existing in profile["links"]):
            profile["links"].append(link)
    evidence = "Имя указано в исходных сведениях об авторе." if profile["name"] else "Автор пока не уточнён; ссылка на источник сама по себе не подтверждает авторство."
    return profile, evidence


def state(user, inventory, skill_id, defaults=None):
    item = inventory["skills"].get(skill_id)
    if item is None: raise ValueError("Навык не найден.")
    overlay = user.get("skills", {}).get(skill_id, {})
    overridden = "author_profile" in overlay
    if overridden:
        profile = validate(overlay["author_profile"])
        evidence = overlay.get("author_evidence") or "Профиль автора указан владельцем каталога."
    else:
        profile, evidence = initial(item, defaults if defaults is not None else load_defaults())
    return {"profile": profile, "evidence": evidence, "overridden": overridden,
            "revision": transactions.checksum({"skill_id": skill_id, "profile": profile, "overridden": overridden})}


def change(directory, skill_id, profile, revision):
    if not isinstance(skill_id, str) or not skill_id: raise ValueError("Выберите навык.")
    profile = validate(profile)
    directory = Path(directory)
    with locked(directory):
        transactions.recover_locked(directory)
        j.read_events(directory)
        user = read_json(directory/"user.json", {"schema": 1, "skills": {}})
        inventory = read_json(directory/"inventory.json")
        defaults = load_defaults()
        before = state(user, inventory, skill_id, defaults)
        if revision != before["revision"]:
            raise Conflict("Профиль автора уже изменился. Получите свежие сведения; ваш ввод сохранён в форме.")
        if before["overridden"] and before["profile"] == profile:
            return {"saved": True, "author_profile": profile, "revision": before["revision"], "unchanged": True}
        updated = deepcopy(user)
        overlay = updated.setdefault("skills", {}).setdefault(skill_id, {})
        overlay["author_profile"] = profile
        overlay["author_evidence"] = f"Профиль автора указан владельцем каталога {now()}."
        transactions.commit_locked(directory, user, updated, "skill_author_changed", {
            "skill_id": skill_id, "skill_name": inventory["skills"][skill_id]["name"],
            "before_profile": before["profile"], "author_profile": profile,
        })
        return {"saved": True, "author_profile": profile, "revision": state(updated, inventory, skill_id, defaults)["revision"]}
