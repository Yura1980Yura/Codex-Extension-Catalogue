"""On-demand search of published skill manifests; never installs or executes them."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from journal import read_events, record
from storage import atomic_json, locked, now, read_json

SOURCES = [
    {"repo": "openai/skills", "path": "skills/.curated", "ref": "main"},
    {"repo": "anthropics/skills", "path": "skills", "ref": "main"},
    {"repo": "remotion-dev/skills", "path": "skills", "ref": "main"},
]
FAMILIES = [
    (r"дизайн|интерфейс|\bui\b|\bux\b|design|frontend", ["frontend-design", "figma", "design", "web"]),
    (r"анимац|animation|motion|видео|video", ["remotion", "animation", "motion", "video"]),
    (r"аналит|анализ.*данн|data|исследован|research", ["jupyter", "spreadsheet", "data", "research", "analysis"]),
]


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "personal-codex-skill-catalog", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def source_index(source, fetch=fetch_json):
    repo, path, ref = source["repo"], source["path"].strip("/"), source.get("ref", "main")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not path or ".." in Path(path).parts:
        raise ValueError("Invalid published repository source")
    commit = fetch(f"https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}")
    revision = commit["sha"]
    tree = fetch(f"https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1")
    if tree.get("truncated"):
        raise ValueError("Repository tree truncated; completeness not established")
    manifests = [x for x in tree["tree"] if x.get("type") == "blob" and x["path"].startswith(path+"/") and x["path"].endswith("/SKILL.md")]
    return {"repo": repo, "revision": revision, "observed_at": now(), "manifests": manifests}


def match_score(query, path):
    lower = path.casefold()
    words = re.findall(r"[\w-]+", query.casefold())
    points = sum(2 for word in words if len(word) > 3 and word in lower)
    for pattern, tokens in FAMILIES:
        if re.search(pattern, query, re.I):
            points += sum(4 if token in lower else 0 for token in tokens)
    return points


def start_search(directory, query):
    if not query.strip():
        raise ValueError("Search query must not be empty")
    return record(directory, "search_requested", {"query": query, "mode": "on_demand"})


def finish_search(directory, search_id, candidates, warnings=(), sources=()):
    # Validate imported web/plugin suggestions without promoting them to installations.
    if not isinstance(candidates, list):
        raise ValueError("Candidates must be a list")
    unique = {}
    for candidate in candidates:
        if not all(isinstance(candidate.get(k), str) and candidate[k].strip() for k in ("name", "url", "summary")):
            raise ValueError("Candidate needs name, url and summary")
        url = urllib.parse.urlsplit(candidate["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Candidate URL must be a public HTTPS source without credentials")
        unique[candidate["url"]] = {**candidate, "state": "proposed", "functional_tested": False}
    events = read_events(directory)
    requested = next((x for x in events if x["id"] == search_id and x["kind"] == "search_requested"), None)
    if not requested:
        raise ValueError("Unknown search ID")
    return record(directory, "search_completed", {"search_id": search_id, "query": requested["data"]["query"], "candidates": list(unique.values()), "warnings": list(warnings), "sources": list(sources), "coverage": "Named sources and inspected manifests; not an exhaustive Internet search"})


def search(directory, query, limit=5, refresh_sources=False, fetch=fetch_json):
    if not 1 <= limit <= 12:
        raise ValueError("limit must be between 1 and 12")
    request = start_search(directory, query)
    indices, warnings = [], []
    try:
        settings = read_json(Path(directory)/"settings.json", {})
        cache = read_json(Path(directory)/"search-cache.json", {})
        if not isinstance(settings, dict) or not isinstance(cache, dict):
            raise ValueError("Search settings and cache must be objects")
        sources = settings.get("search_sources", SOURCES)
        if not isinstance(sources, list) or not sources or not all(isinstance(x, dict) for x in sources):
            raise ValueError("search_sources must be a nonempty list of repository descriptions")
        def load(source):
            key = json.dumps(source, sort_keys=True)
            saved = cache.get(key)
            if saved and not refresh_sources:
                age = datetime.now(timezone.utc)-datetime.fromisoformat(saved["observed_at"])
                if age.total_seconds() < 1800:
                    return key, saved
            return key, source_index(source, fetch)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for source, future in zip(sources, [pool.submit(load, s) for s in sources]):
                try:
                    key, index = future.result()
                    cache[key] = index
                    indices.append(index)
                except Exception as error:
                    warnings.append(f"{source.get('repo', 'source')}: {type(error).__name__}: {error}")
        with locked(directory):
            atomic_json(Path(directory)/"search-cache.json", cache)
        if not indices:
            raise RuntimeError("No search source could be read: " + "; ".join(warnings))
        ranked = []
        for index in indices:
            matches = sorted(index["manifests"], key=lambda item: (-match_score(query, item["path"]), item["path"]))
            # Diversity prevents one large source from crowding out all alternatives.
            ranked.extend((index, item) for item in matches[:max(2, limit//len(indices))] if match_score(query, item["path"]) > 0)
        ranked.sort(key=lambda pair: -match_score(query, pair[1]["path"]))
        inventory = read_json(Path(directory)/"inventory.json", {"skills": {}})
        installed = {x["name"].casefold() for x in inventory["skills"].values() if x["state"] == "present"}
        candidates = []
        for index, item in ranked[:limit]:
            try:
                import base64
                blob = fetch(f"https://api.github.com/repos/{index['repo']}/git/blobs/{item['sha']}")
                text = base64.b64decode(blob["content"]).decode("utf-8-sig")
                name_match = re.search(r"^name:\s*([^\n]+)", text, re.M)
                description = re.search(r"^description:\s*(.*?)(?=\n\S|\n---)", text, re.M|re.S)
                if not name_match or not description:
                    raise ValueError("Incomplete skill manifest")
                name = name_match.group(1).strip().strip("\"'")
                summary = " ".join(description.group(1).strip().lstrip(">|- ").strip("\"'").split())
                path = item["path"].removesuffix("/SKILL.md")
                candidates.append({"name": name, "url": f"https://github.com/{index['repo']}/blob/{index['revision']}/{item['path']}", "summary": summary, "repo": index["repo"], "path": path, "revision": index["revision"], "instruction_sha256": hashlib.sha256(text.encode('utf-8')).hexdigest(), "already_installed_by_name": name.casefold() in installed, "compatibility": "Needs instruction/dependency review for the current project before installation", "source_type": "skill"})
            except Exception as error:
                warnings.append(f"{index['repo']}/{item['path']}: {type(error).__name__}: {error}")
        return finish_search(directory, request["id"], candidates, warnings, [{"repo": x["repo"], "revision": x["revision"], "observed_at": x["observed_at"]} for x in indices])
    except Exception as error:
        record(directory, "search_failed", {"search_id": request["id"], "query": query, "error": f"{type(error).__name__}: {error}"})
        raise
