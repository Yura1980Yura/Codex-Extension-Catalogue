"""Use the current local catalogue API from its installed skill."""
from pathlib import Path
import argparse
import json
import sys


def connection():
    meta=Path(__file__).resolve().parents[1]/"installation.json"
    installation=json.loads(meta.read_text("utf-8-sig")) if meta.is_file() else {}
    paths=installation.get("catalogue",{})
    if not paths:
        raise ValueError("Нет связи навыка с текущим каталогом. Запустите установщик Codex Extension Catalogue или найдите рабочую папку каталога; не создавайте второй экземпляр вслепую.")
    runtime=Path(paths["runtime"])
    sys.path.insert(0,str(runtime))
    import deployment
    try:deployment.request_api(paths["work"])
    except (OSError,ValueError):deployment.check(runtime)
    return deployment,paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["status","list","show","refresh","wishes","wish"])
    parser.add_argument("id",nargs="?")
    args=parser.parse_args()
    api,paths=connection()
    if args.action=="refresh":result=api.check(paths["runtime"],refresh=True)
    elif args.action in ("wishes","wish"):
        if args.action=="wish" and not args.id:parser.error("Укажите номер пожелания.")
        result=api.request_api(paths["work"],"backlog",{"action":"read","id":args.id} if args.action=="wish" else {"action":"load"})
    else:
        state=api.request_api(paths["work"])
        if args.action=="status":
            result={k:state.get(k) for k in ("product","developer","version","updated_at","coverage","job","projects")}
        elif args.action=="list":
            result=[{"id":a["id"],"title":a["title"],"origin":a.get("origin"),"components":[{k:c.get(k) for k in ("kind","scope","installed","enabled","path")} for c in a.get("components",[])]} for a in state.get("addons",[])]
        else:
            result=next((a for a in state.get("addons",[]) if a["id"]==args.id),None)
            if result is None:raise ValueError("Карточка не найдена. Прочитайте list.")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    try:main()
    except (ValueError,OSError) as error:raise SystemExit(str(error))
