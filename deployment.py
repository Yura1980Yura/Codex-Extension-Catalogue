"""Repeatable per-user installation of the verified Asemic catalogue."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"app/skill-catalog/scripts"))
from platform_paths import codex_dir, user_folder

NAME = "Asemic Catalogue"
APP = "codex-catalog-overview-preview"


def read(path, default=None):
    return json.loads(Path(path).read_text("utf-8-sig")) if Path(path).is_file() else default


def write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    os.replace(temp,path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shortcut_digest(path):
    path=Path(path)
    if path.is_file():return digest(path)
    hashes={p.relative_to(path).as_posix():digest(p) for p in sorted(path.rglob('*')) if p.is_file()}
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()


def manifest(bundle):
    bundle=Path(bundle).resolve();result=read(bundle/"MANIFEST.json")
    if not isinstance(result,dict) or not result.get("files"): raise ValueError("Нет контрольного списка комплекта.")
    allowed=set(result["files"])
    excluded={".git",".local","node_modules","__pycache__",".venv",".pytest_cache"}
    actual={p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()
            and p.name not in ("MANIFEST.json",".asemic-installation.json")
            and not excluded.intersection(p.relative_to(bundle).parts)}
    if actual!=allowed: raise ValueError("Состав комплекта изменён. Используйте полный ZIP из Releases.")
    for name,expected in result["files"].items():
        path=bundle/name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle) or digest(path)!=expected:
            raise ValueError("Повреждён файл комплекта: "+name)
    return result


def locations(home=None, desktop=None, docs=None):
    home=Path(home or Path.home()).resolve();profile=codex_dir(home)
    data=profile/"skill-catalog"
    previous=read(data/"settings.json",{})
    documents=Path(docs or previous.get("documentation_root") or user_folder("Documents",home)/"Asemic/Catalogue").resolve()
    return {"home":str(home),"profile":str(profile),"runtime":str(home/"Applications/Asemic-Catalogue"),
            "data":str(data),"work":str(profile/"asemic-catalogue-current"),"skill":str(home/".agents/skills/skill-catalog"),
            "notes":str(documents),"desktop":str(Path(desktop or user_folder("Desktop",home)).resolve())}


def plan(bundle=ROOT,home=None,desktop=None,docs=None,port=None):
    info=manifest(bundle);paths=locations(home,desktop,docs)
    runtime=Path(paths["runtime"]);marker=read(runtime/".asemic-installation.json")
    if runtime.exists():
        if runtime.is_symlink() or runtime.is_junction(): raise ValueError("Папка программы перенаправлена ссылкой.")
        if not marker or marker.get("application")!="asemic-catalogue" or marker.get("home")!=paths["home"]:
            raise ValueError("Папка программы уже занята. Автоматическая замена отменена: "+str(runtime))
        if not marker.get("files"): raise ValueError("Нет контрольного списка установленной программы.")
        manifest(runtime)
        for name,expected in marker["files"].items():
            path=runtime/name
            if not path.resolve().is_relative_to(runtime) or not path.is_file() or path.is_symlink() or digest(path)!=expected:
                raise ValueError("В установленной программе есть пользовательские изменения: "+name)
    skill=Path(paths["skill"])
    if skill.exists():
        if skill.is_symlink() or skill.is_junction(): raise ValueError("Навык установлен ссылкой; требуется отдельная проверка переноса.")
        old=read(skill/"installation.json",{})
        if not old.get("files"): raise ValueError("Найдена неуправляемая копия skill-catalog. Сначала сохраните и проверьте её.")
        actual={str(p.relative_to(skill)) for p in skill.rglob('*') if p.is_file() and p.name!='installation.json' and '__pycache__' not in p.parts}
        if actual!=set(old['files']): raise ValueError("Состав установленного навыка изменён; требуется проверка.")
        for name,expected in old["files"].items():
            if not (skill/name).resolve().is_relative_to(skill) or not (skill/name).is_file() or digest(skill/name)!=expected:
                raise ValueError("Личный навык skill-catalog изменён пользователем: "+name)
    link=installed_shortcut(paths)
    if link.exists() and (not marker or marker.get("shortcut")!=str(link)):
        raise ValueError("Одноимённый ярлык уже существует; требуется отдельная проверка.")
    if link.exists() and marker.get('shortcut_sha256')!=shortcut_digest(link):
        raise ValueError("Ярлык изменён пользователем; требуется проверка.")
    port=port if port is not None else (marker or {}).get('port',8772)
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('Порт должен быть от 1024 до 65535.')
    return {"application":"asemic-catalogue","version":read(Path(bundle)/"release.json")["version"],"port":port,
            "origin":"Asemic","action":"unchanged" if marker and marker.get("bundle_id")==info["bundle_id"] else "update" if marker else "install",
            "bundle_id":info["bundle_id"],"paths":paths}


def shortcut(runtime, desktop, platform=None):
    """Create an OS launcher with a fixed target, never a downloaded shell command."""
    runtime,desktop=Path(runtime).resolve(),Path(desktop).resolve()
    desktop.mkdir(parents=True,exist_ok=True)
    platform=platform or sys.platform
    interpreter=Path(sys.executable)
    if platform=="win32" and interpreter.with_name("pythonw.exe").is_file(): interpreter=interpreter.with_name("pythonw.exe")
    if platform=="win32":
        target=desktop/(NAME+".lnk")
        if target.exists(): raise ValueError("Ярлык уже существует: "+str(target))
        def ps(value):return "'"+str(value).replace("'","''")+"'"
        script="$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+ps(target)+");"
        script+="$s.TargetPath="+ps(interpreter)+";$s.Arguments="+ps('-X utf8 -B "'+str(runtime/"launch.py")+'"')+";"
        script+="$s.WorkingDirectory="+ps(runtime)+";$s.IconLocation="+ps(runtime/"assets/asemic.ico")+";$s.Save()"
        subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-Command",script],
                       check=True,capture_output=True,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    elif platform=="darwin":
        target=desktop/(NAME+".app")
        if target.exists(): raise ValueError("Ярлык уже существует: "+str(target))
        resources=target/"Contents/Resources";resources.mkdir(parents=True)
        executable=target/"Contents/MacOS/launch";executable.parent.mkdir()
        executable.write_text("#!/bin/sh\nexec "+__import__("shlex").quote(str(interpreter))+" -X utf8 -B "+__import__("shlex").quote(str(runtime/"launch.py"))+"\n",encoding="utf-8")
        executable.chmod(0o755)
        shutil.copy2(runtime/"assets/asemic.icns",resources/"asemic.icns")
        with (target/"Contents/Info.plist").open("wb") as file:
            plistlib.dump({"CFBundleName":NAME,"CFBundleIdentifier":"ai.asemic.catalogue","CFBundleExecutable":"launch","CFBundleIconFile":"asemic.icns"},file)
    else:
        target=desktop/(NAME+".desktop")
        if target.exists(): raise ValueError("Ярлык уже существует: "+str(target))
        def quoted(value):
            # Desktop Entry string escapes are decoded before Exec quoting.
            # https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html
            value=str(value).replace('%','%%')
            if any(ord(c)<32 for c in value):raise ValueError('Управляющие символы в пути ярлыка не поддерживаются.')
            return '"'+''.join('\\\\\\\\' if c=='\\' else '\\\\'+c if c in '"`$' else c for c in value)+'"'
        target.write_text("[Desktop Entry]\nType=Application\nName="+NAME+"\nExec="+quoted(interpreter)+" -X utf8 -B "+quoted(runtime/"launch.py")+"\nIcon="+str(runtime/"assets/asemic.png")+"\nTerminal=false\nCategories=Utility;\n",encoding="utf-8")
        target.chmod(0o755)
    if not target.exists(): raise ValueError("Создание ярлыка не подтверждено.")
    return str(target)


def installed_shortcut(paths):
    suffix=".lnk" if sys.platform=="win32" else ".app" if sys.platform=="darwin" else ".desktop"
    return Path(paths["desktop"])/(NAME+suffix)


def request_api(work, action="state", body=None):
    info=read(Path(work)/"server.json",{})
    url=info.get("url","")
    from urllib.parse import urlsplit
    parsed=urlsplit(url)
    if parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or parsed.username or parsed.password or parsed.query:
        raise ValueError("Нет подтверждённого локального адреса каталога.")
    health=json.load(urllib.request.urlopen(url+"/api/health",timeout=4))
    if health.get("app")!=APP or Path(health.get("data","")).resolve()!=Path(work).resolve():
        raise ValueError("По адресу работает другая установка каталога.")
    html=urllib.request.urlopen(url,timeout=4).read().decode()
    token=re.search('name="catalog-token" content="([^"]+)"',html)[1]
    raw=json.dumps(body).encode() if body is not None else None
    request=urllib.request.Request(url+"/api/"+action,data=raw,headers={"X-Catalog-Token":token,"Content-Type":"application/json","Origin":url})
    return json.load(urllib.request.urlopen(request,timeout=20))


def stop_managed(work):
    if not (Path(work)/"server.json").is_file(): return
    try: request_api(work,"shutdown",{})
    except (OSError,ValueError): return
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        try:request_api(work)
        except (OSError,ValueError):return
        time.sleep(.15)
    raise ValueError('Сервер ещё завершает работу. Повторите обновление после его остановки.')


def install(bundle=ROOT,home=None,offline=False,codex=None,desktop=None,docs=None,port=None):
    bundle=Path(bundle).resolve();prepared=plan(bundle,home,desktop,docs,port);paths=prepared["paths"]
    runtime=Path(paths["runtime"]);profile=Path(paths["profile"]);data=Path(paths["data"]);work=Path(paths["work"])
    info=manifest(bundle);program_backup=None
    previous=read(runtime/".asemic-installation.json",{})
    import discovery
    executable=discovery.executable(codex) if not offline else codex
    runtime.parent.mkdir(parents=True,exist_ok=True);profile.mkdir(parents=True,exist_ok=True)
    if prepared["action"]!="unchanged":
        if runtime.is_symlink() or runtime.is_junction(): raise ValueError("Папка программы перенаправлена ссылкой.")
        stage=Path(tempfile.mkdtemp(prefix=".asemic-",dir=runtime.parent))
        try:
            for name in [*info["files"],"MANIFEST.json"]:
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(bundle/name,target)
            manifest(stage)
            if runtime.exists():
                stop_managed(work)
                program_backup=runtime.parent/".asemic-backups"/uuid.uuid4().hex
                assert program_backup.resolve().is_relative_to(runtime.parent.resolve())
                program_backup.parent.mkdir(exist_ok=True)
                deadline=time.monotonic()+8
                while True:
                    try:runtime.rename(program_backup);break
                    except PermissionError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.2)
            try: stage.rename(runtime)
            except Exception:
                if program_backup:program_backup.rename(runtime)
                raise
        finally:
            if stage.exists():
                assert stage.parent.resolve()==runtime.parent.resolve() and stage.name.startswith(".asemic-")
                shutil.rmtree(stage)
    sys.path[:0]=[str(runtime/"app/skill-catalog/scripts"),str(runtime/"app/manager")]
    from storage import atomic_json, read_json
    from install import install as install_skill
    documents=Path(paths["notes"]);documents.mkdir(parents=True,exist_ok=True)
    for source in (runtime/"notes-template").rglob("*.md"):
        target=documents/source.relative_to(runtime/"notes-template")
        if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    settings=read_json(data/"settings.json",{})
    settings.setdefault("documentation_root",str(documents))
    if executable: settings["codex_executable"]=executable
    atomic_json(data/"settings.json",settings)
    skill_result=install_skill(runtime/"app/skill-catalog",Path(paths["home"]),update_instructions=False)
    meta=read(Path(paths["skill"])/"installation.json")
    meta["catalogue"]={"runtime":str(runtime),"work":str(work),"data":str(data),"profile":str(profile)}
    atomic_json(Path(paths["skill"])/"installation.json",meta)
    atomic_json(work/"settings.json",{"runtime":str(runtime/"app"),"source_data":str(data),"home":paths["home"]})
    marker={**prepared,**paths,"files":info["files"],"python":sys.executable,"shortcut":str(installed_shortcut(paths))}
    link=installed_shortcut(paths)
    if link.exists():
        if previous.get("shortcut")!=str(link): raise ValueError("На рабочем столе уже есть одноимённый ярлык. Он сохранён; проверьте его вручную.")
    else: marker["shortcut"]=shortcut(runtime,paths["desktop"])
    marker['shortcut_sha256']=shortcut_digest(link)
    atomic_json(runtime/".asemic-installation.json",marker)
    return {"installed":str(runtime),"skill":paths["skill"],"data":str(data),"work":str(work),"notes":str(documents),
            "launcher":marker["shortcut"],"files_verified":skill_result["files_verified"],"version":prepared["version"],
            "origin":"Asemic","outcome":prepared["action"],"program_backup":str(program_backup) if program_backup else None}


def launch(runtime=ROOT, open_browser=True, port=None):
    runtime=Path(runtime).resolve();marker=read(runtime/".asemic-installation.json")
    work=Path(marker["work"]) if marker else runtime/".local/catalog-current"
    port=port if port is not None else (marker or {}).get('port',8772)
    if marker:os.environ["CODEX_HOME"]=marker["profile"]
    command=[sys.executable,"-X","utf8","-B",str(runtime/"preview/server.py"),"--work",str(work),"--settings",str(work/"settings.json"),"--port",str(port)]
    if open_browser:command.append("--open")
    log=work/"launch.log";log.parent.mkdir(parents=True,exist_ok=True)
    with log.open("ab") as output:
        subprocess.Popen(command,cwd=runtime,stdout=output,stderr=output,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),start_new_session=os.name!="nt")
    return work


def check(runtime=ROOT, refresh=False, open_browser=False, port=None):
    work=launch(runtime,open_browser,port)
    deadline=time.monotonic()+20
    while True:
        try:
            state=request_api(work)
            break
        except (OSError,ValueError,KeyError):
            if time.monotonic()>deadline:raise ValueError("Каталог не запустился. Проверьте "+str(work/"launch.log"))
            time.sleep(.2)
    if refresh:
        request_api(work,"refresh",{})
        deadline=time.monotonic()+150
        while True:
            state=request_api(work)
            if state.get("job",{}).get("state")!="running":break
            if time.monotonic()>deadline:raise ValueError("Сверка ещё выполняется; повторите проверку состояния.")
            time.sleep(.4)
        if state.get("job",{}).get("state")=="error":raise ValueError("Сверка не завершена; прежний снимок сохранён.")
    own=[c for a in state.get("addons",[]) for c in a.get("components",[]) if c.get("name")=="skill-catalog"]
    return {"url":read(work/"server.json")["url"],"version":state.get("version"),"origin":"Asemic",
            "skill_confirmed":any(c.get("installed") for c in own),"skill_paths":[c.get("path") for c in own],
            "project_count":len(state.get("projects",[])),"last_checked":state.get("updated_at"),
            "source_coverage":state.get("coverage",{}).get("reconciliation",{})}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["plan","install","check","launch"])
    parser.add_argument("--home",type=Path,default=Path.home(),help=argparse.SUPPRESS)
    parser.add_argument("--desktop-dir",type=Path);parser.add_argument("--docs-dir",type=Path)
    parser.add_argument("--port",type=int)
    parser.add_argument("--offline",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--codex-executable");parser.add_argument("--refresh",action="store_true");parser.add_argument("--open",action="store_true")
    args=parser.parse_args()
    if args.action=="plan": result=plan(home=args.home,desktop=args.desktop_dir,docs=args.docs_dir,port=args.port)
    elif args.action=="install":result=install(home=args.home,offline=args.offline,codex=args.codex_executable,desktop=args.desktop_dir,docs=args.docs_dir,port=args.port)
    elif args.action=="check":result=check(refresh=args.refresh,open_browser=args.open,port=args.port)
    else:result={"work":str(launch(open_browser=True,port=args.port))}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
