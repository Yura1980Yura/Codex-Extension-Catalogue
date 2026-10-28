"""Build the distributable file inventory, excluding machine-local data and caches."""
from pathlib import Path
import hashlib, json
root=Path(__file__).resolve().parents[1]
excluded={'.git','.local','node_modules','__pycache__','.venv','.pytest_cache'}
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(root.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'
       and not excluded.intersection(p.relative_to(root).parts)}
manifest={'bundle_id':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
          'date':'2026-10-28','source_revision':'v3.0.0','files':files}
(root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(f'{len(files)} files')
