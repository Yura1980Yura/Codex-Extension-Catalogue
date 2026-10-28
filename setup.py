"""Configure a clean personal Windows trial from the verified local distribution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BUNDLE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(bundle):
    manifest = json.loads((bundle/"MANIFEST.json").read_text("utf-8"))
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file() and p != bundle/"MANIFEST.json" and not any(x in p.relative_to(bundle).parts for x in ("__pycache__", ".git", ".pytest_cache", ".venv", ".local", "node_modules"))}
    if actual != set(manifest["files"]):
        raise ValueError("Состав комплекта изменён. Используйте исходный распакованный архив.")
    for name, expected in manifest["files"].items():
        path = bundle/name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()) or sha(path.read_bytes()) != expected:
            raise ValueError("Повреждён файл комплекта: "+name)
    return manifest


def configure(bundle, home, offline=False, codex=None):
    bundle, home = Path(bundle).resolve(), Path(home).resolve()
    manifest = verify(bundle)
    runtime = home/"Applications/Naviki"
    data = home/".codex/skill-catalog"
    skill = home/".agents/skills/skill-catalog"
    docs = home/"Documents/Naviki/Projects/Catalog"
    marker = runtime/"trial-installation.json"
    if runtime.exists():
        previous = json.loads(marker.read_text("utf-8")) if marker.is_file() else {}
        if previous.get("bundle_id") != manifest["bundle_id"] or previous.get("home") != str(home):
            raise ValueError("Папка установки уже занята другим комплектом. Прежние файлы сохранены; поручите Codex проверить обновление.")
        for name, expected in previous.get("files", {}).items():
            path = runtime/name
            if not path.resolve().is_relative_to(runtime) or not path.is_file() or sha(path.read_bytes()) != expected:
                raise ValueError("Программа изменена после установки: "+name+". Изменения сохранены; поручите Codex проверить их.")
        if not previous.get("files"):
            raise ValueError("Нет контрольного списка установленной программы. Нужна проверка Codex.")
    elif data.exists() or skill.exists():
        raise ValueError("Личный каталог уже существует. Этот первый пробный установщик не заменяет существующий каталог; поручите Codex проверить перенос или обновление.")
    else:
        runtime.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".naviki-", dir=runtime.parent))
        try:
            shutil.copytree(bundle/"app", stage, dirs_exist_ok=True)
            if (bundle/"preview").is_dir():
                shutil.copytree(bundle/"preview", stage/"overview", ignore=shutil.ignore_patterns('node_modules', 'tests', '__pycache__'))
            own_skill = stage/"skill-catalog"
            raw = (own_skill/"SKILL.md").read_bytes()
            identity = os.path.normcase(str(skill.resolve()))
            key = "local:"+sha(identity.encode("utf-8"))[:12]+":skill-catalog"
            russian = own_skill/"assets/ru"
            (russian/"instructions").mkdir(parents=True, exist_ok=True)
            (russian/"instructions/catalog.md").write_bytes(raw)
            entry = {"file":"instructions/catalog.md", "source_sha256":sha(raw), "translation_sha256":sha(raw), "original_language":"ru", "reviewed_at":manifest["date"], "title_ru":"Каталог навыков", "description_ru":"Личный каталог, поиск новых навыков, заметки и история работы.", "source_path":str(skill/"SKILL.md")}
            (russian/"manifest.json").write_text(json.dumps({"schema":1,"skills":{key:entry}}, ensure_ascii=False, indent=2), encoding="utf-8")
            fingerprints = {p.relative_to(stage).as_posix():sha(p.read_bytes()) for p in stage.rglob("*") if p.is_file()}
            (stage/"trial-installation.json").write_text(json.dumps({"bundle_id":manifest["bundle_id"], "home":str(home), "source_revision":manifest["source_revision"], "files":fingerprints}, ensure_ascii=False, indent=2), encoding="utf-8")
            stage.rename(runtime)
        finally:
            if stage.exists():
                assert stage.resolve().parent == runtime.parent.resolve() and stage.name.startswith(".naviki-")
                shutil.rmtree(stage)
    sys.path[:0] = [str(runtime/"skill-catalog/scripts"), str(runtime/"manager")]
    import catalog
    import discovery
    import exporter
    from install import install
    from storage import atomic_json, atomic_text, read_json
    docs.mkdir(parents=True, exist_ok=True)
    for source in (bundle/"notes-template").rglob("*.md"):
        dest = docs/source.relative_to(bundle/"notes-template")
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    atomic_text(runtime/"docs-root.txt", str(docs)+"\n")
    settings = read_json(data/"settings.json", {})
    settings.setdefault("documentation_root", str(docs))
    if codex:
        settings["codex_executable"] = discovery.executable(codex)
    elif not settings.get("codex_executable"):
        try: settings["codex_executable"] = discovery.executable()
        except FileNotFoundError:
            if not offline:
                raise ValueError("Команда Codex не найдена. Запустите установку из Codex или передайте --codex-executable с найденным приложением Codex.")
    atomic_json(data/"settings.json", settings)
    installed = install(source=runtime/"skill-catalog", home=home, update_instructions=True)
    probe = (lambda *_: {"data":[]}) if offline else discovery.discover
    inventory = catalog.refresh(data, home, runtime, discovery_fn=probe)
    import organization
    organization.migrate(data)
    exported = exporter.export(data)
    # The launcher only starts this installation; it never installs software.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.is_file() else Path(sys.executable)
    def batch_path(path):
        value = str(path)
        if any(char in value for char in '\r\n"'):
            raise ValueError("Неподдерживаемые символы в пути программы.")
        return value.replace('%', '%%')
    command = '@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\nstart "" "'+batch_path(interpreter)+'" -X utf8 -B "'+batch_path(runtime/"manager/launch.py")+'"\r\n'
    launcher = home/"Documents/Naviki/Открыть каталог.cmd"
    (launcher.parent/"Открыть прежний каталог.cmd").write_bytes(command.encode("utf-8"))
    if (runtime/"overview/server.py").is_file():
        command = '@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\nstart "" "'+batch_path(interpreter)+'" -X utf8 -B "'+batch_path(runtime/"overview/server.py")+'" --open\r\n'
        atomic_json(runtime/".local/catalog-current/settings.json", {"runtime":str(runtime), "source_data":str(data), "home":str(home)})
    launcher.write_bytes(command.encode("utf-8"))
    result = {"installed":str(runtime), "skill":str(skill), "data":str(data), "notes":str(docs), "launcher":str(launcher), "files_verified":installed["files_verified"], "discovery": "skipped_for_isolated_test" if offline else inventory["discovery_status"], "warnings":inventory.get("warnings",[]), "exported":exported["files_verified"]}
    atomic_json(runtime/"setup-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--codex-executable")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3,12): raise SystemExit("Нужен Python 3.12 или новее.")
    if not args.verify_only and not args.offline and os.environ.get("CODEX_HOME") and Path(os.environ["CODEX_HOME"]).resolve() != args.home.resolve()/".codex":
        raise SystemExit("У вас задана нестандартная папка CODEX_HOME. Этот пробный комплект рассчитан на обычный профиль; поручите Codex адаптировать установку, сохранив ваши данные.")
    if args.verify_only:
        result = {"verified":True,"files":len(verify(BUNDLE)["files"])}
    else:
        result = configure(BUNDLE, args.home, args.offline, args.codex_executable)
        if not args.no_launch and not args.offline:
            entry = Path(result["installed"])/"overview/server.py"
            if entry.is_file():
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                subprocess.Popen([sys.executable,"-X","utf8","-B",str(entry),"--open"], creationflags=flags)
            else:
                subprocess.run([sys.executable,"-X","utf8","-B",str(Path(result["installed"])/"manager/launch.py")],check=True)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    try: main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("Установка не завершена: "+str(error),file=sys.stderr)
        raise SystemExit(1)
