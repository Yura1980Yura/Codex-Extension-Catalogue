"""Install an ordinary personal skill copy; preserve data and global instructions."""
from __future__ import annotations
from platform_paths import codex_dir

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from catalog import SKILL_ROOT, atomic_json, locked
from journal import read_events, record_locked, snapshot

MARKER = "## Личный каталог навыков Codex"
BLOCK = """

## Личный каталог навыков Codex

Для вопросов о своих навыках и подбора к содержательной задаче используй личный навык
`skill-catalog` из `~/.agents/skills/skill-catalog/SKILL.md`. Сначала читай краткий индекс,
затем только выбранную инструкцию. Когда это заметно поможет новой задаче, кратко предложи
несколько подходящих навыков и объясни пользу. Не добавляй рекламную преамбулу к каждому
сообщению и не задерживай простые задачи. По запросу «Покажи мой каталог навыков»,
«Что есть для редактуры?» или «Обнови каталог навыков» применяй каталог прямо в чате.
Различай найденные файлы, доступность в текущем чате и проверенное применение.
Чужие проектные правила остаются в своём проекте; переносимые литературные инструкции
каталог читает по исходному пути, без второй копии и без переноса правил игры.
"""


def install(source=SKILL_ROOT, home=Path.home(), update_instructions=False):
    source, home = Path(source).resolve(), Path(home).resolve()
    data = codex_dir(home)/"skill-catalog"
    target = home / ".agents/skills/skill-catalog"
    if target.resolve() == source or target.is_symlink() or target.is_junction():
        raise ValueError("Expected an independent installation directory")
    with locked(data):
        read_events(data)  # Keep an unrecordable update from changing the installation.
        before = snapshot(target)
        original = (codex_dir(home)/"AGENTS.md").read_bytes() if (codex_dir(home)/"AGENTS.md").exists() else b""
        if update_instructions and MARKER in original.decode("utf-8-sig"):
            if BLOCK.strip() not in original.decode("utf-8-sig"):
                raise ValueError("Existing catalog instructions differ; review them instead of appending a duplicate")
        source_files = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "installation.json"}
        if "SKILL.md" not in source_files:
            raise ValueError("Missing source SKILL.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".catalog-install-", dir=target.parent.parent))
        backup = None
        try:
            for relative in source_files:
                dest = staging / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source/relative, dest)
            for relative, digest in source_files.items():
                if hashlib.sha256((staging/relative).read_bytes()).hexdigest() != digest:
                    raise OSError(f"Copy verification failed: {relative}")
            release = json.loads((source.parent/"release.json").read_text("utf-8"))
            revision = release["source_revision"]
            provenance = {"source_repository": release.get("source_repository"), "source_branch": release.get("source_branch"), "source_subdirectory": "app/skill-catalog", "source_directory": str(source), "source_revision": revision}
            metadata_path = target/"installation.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            current_files = {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "installation.json"} if target.is_dir() else {}
            if current_files == source_files and all(metadata.get(k) == v for k, v in provenance.items()) and (not update_instructions or BLOCK.strip() in original.decode("utf-8-sig")):
                return {"installed": str(target), "files_verified": len(source_files), "outcome": "unchanged", "source_revision": revision, "user_data": "preserved"}
            atomic_json(staging/"installation.json", {"schema": 1, **provenance, "installed_at": datetime.now(timezone.utc).isoformat(), "files": source_files})
            if target.exists():
                if (target/"SKILL.md").read_bytes() != (source/"SKILL.md").read_bytes() and not (target/"installation.json").exists():
                    raise ValueError("Existing unmanaged skill differs; preserve and review before replacing")
                backups = data/"backups"
                backups.mkdir(exist_ok=True)
                backup = backups / staging.name
                target.rename(backup)
            try:
                staging.rename(target)
            except OSError:
                if backup:
                    backup.rename(target)
                raise
            if update_instructions and MARKER not in original.decode("utf-8-sig"):
                agents = codex_dir(home)/"AGENTS.md"
                backups = data/"backups"
                backups.mkdir(exist_ok=True)
                saved = backups/f"AGENTS-{hashlib.sha256(original).hexdigest()[:16]}.md"
                if not saved.exists():
                    saved.write_bytes(original)
                expected = original + BLOCK.encode("utf-8")
                fd, temporary = tempfile.mkstemp(prefix=".agents-catalog-", dir=agents.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(expected)
                    if (agents.read_bytes() if agents.exists() else b"") != original:
                        raise ValueError("Global instructions changed concurrently; retry after review")
                    os.replace(temporary, agents)
                    if agents.read_bytes() != expected or not agents.read_bytes().startswith(original):
                        raise OSError("Global instructions read-back failed")
                finally:
                    Path(temporary).unlink(missing_ok=True)
            result = {"installed": str(target), "files_verified": len(source_files), "backup": str(backup) if backup else None, "global_instructions": "preserved and catalog block present" if update_instructions else "unchanged", "source_revision": revision}
            for relative, digest in source_files.items():
                if hashlib.sha256((target/relative).read_bytes()).hexdigest() != digest:
                    raise OSError(f"Installed read-back failed: {relative}")
            record_locked(data, "catalog_installed", {"source_revision": revision, "target": str(target), "before": before, "after": snapshot(target), "backup": str(backup) if backup else None, "outcome": "success", "functional_tested": False})
            return result
        finally:
            if staging.exists():
                # Only the exact directory created by mkdtemp; never a computed user root.
                shutil.rmtree(staging)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--update-instructions", action="store_true")
    args = parser.parse_args()
    result = install(home=args.home, update_instructions=args.update_instructions)
    from exporter import automatic_export
    result["documentation_export"] = automatic_export(codex_dir(args.home)/"skill-catalog")
    print(json.dumps(result, ensure_ascii=False, indent=2))
