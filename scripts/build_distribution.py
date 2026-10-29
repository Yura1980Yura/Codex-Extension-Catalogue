"""Build a clean release from the verified manifest, never from a user's profile."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from deployment import manifest


def build(output):
    info=manifest(ROOT);output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    target=output/'Asemic-Catalogue.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in sorted([*info['files'],'MANIFEST.json']):
            entry=zipfile.ZipInfo('Asemic-Catalogue/'+name,date_time=(2026,10,29,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o100644<<16
            archive.writestr(entry,(ROOT/name).read_bytes())
    with tempfile.TemporaryDirectory(prefix='asemic-verify-') as directory:
        with zipfile.ZipFile(target) as archive:
            assert all(not n.startswith('/') and '..' not in Path(n).parts for n in archive.namelist())
            archive.extractall(directory)
        manifest(Path(directory)/'Asemic-Catalogue')
    prompt=output/'START-CODEX.txt';prompt.write_bytes((ROOT/'START-CODEX.txt').read_bytes())
    sums=output/'SHA256SUMS.txt'
    sums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (target,prompt)),encoding='utf-8',newline='\n')
    return {'version':json.loads((ROOT/'release.json').read_text('utf-8'))['version'],'files':len(info['files']),
            'zip':str(target),'prompt':str(prompt),'checksums':str(sums),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.local/dist')
    print(json.dumps(build(parser.parse_args().output),ensure_ascii=False,indent=2))
