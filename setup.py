"""Install the verified Asemic bundle without changing account connections."""
from pathlib import Path
import argparse
import json
from deployment import manifest as verify, install, plan


def configure(bundle, home, offline=False, codex=None):
    return install(bundle, home, offline, codex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--codex-executable")
    parser.add_argument("--desktop-dir", type=Path)
    parser.add_argument("--docs-dir", type=Path)
    parser.add_argument("--port",type=int)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    try:
        if args.verify_only:
            info = verify(bundle)
            result = {"verified": True, "files": len(info["files"]), "bundle_id": info["bundle_id"]}
        elif args.plan:
            result = plan(bundle, desktop=args.desktop_dir, docs=args.docs_dir,port=args.port)
        else:
            result = install(bundle, codex=args.codex_executable, desktop=args.desktop_dir, docs=args.docs_dir,port=args.port)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
