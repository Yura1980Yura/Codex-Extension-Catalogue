"""Report credential-shaped findings without displaying credential values."""
from pathlib import Path
import argparse
import json
import re
import string
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from deployment import manifest

PATTERNS={
    'private-key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'github-token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'openai-token':rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}',
    'meshy-token':rb'msy_[A-Za-z0-9_-]{24,}',
    'bearer-secret':rb'Bearer [A-Za-z0-9._-]{35,}',
    'aws-key':rb'AKIA[0-9A-Z]{16}',
}
SENSITIVE=re.compile(r'(^|/)(auth\.json|config\.toml|\.env[^/]*|inventory\.json|history\.jsonl|user\.json|snapshot\.json|annotations\.json)$')


def inspect(raw,path,revision):
    findings=[]
    if SENSITIVE.search(path):findings.append({'path':path,'revision':revision,'type':'private-filename'})
    for kind,pattern in PATTERNS.items():
        for hit in re.finditer(pattern,raw):
            # Existing regression tests deliberately reject this exact alphabet.
            if path=='tests/test_connections.py' and hit[0]==('msy_'+string.ascii_lowercase).encode():continue
            findings.append({'path':path,'revision':revision,'type':kind,'line':raw[:hit.start()].count(b'\n')+1})
    return findings


def audit(history=False):
    info=manifest(ROOT);findings=[];count=0
    for name in info['files']:findings+=inspect((ROOT/name).read_bytes(),name,'working-tree')
    if history:
        rows=subprocess.check_output(['git','rev-list','--objects','--all'],cwd=ROOT).splitlines()
        for row in rows:
            fields=row.split(b' ',1)
            if len(fields)!=2:continue
            revision,name=fields
            if subprocess.check_output(['git','cat-file','-t',revision],cwd=ROOT).strip()!=b'blob':continue
            count+=1
            findings+=inspect(subprocess.check_output(['git','cat-file','blob',revision],cwd=ROOT),name.decode('utf-8','replace'),revision.decode())
    return {'files':len(info['files']),'history_blobs':count,'findings':findings,'passed':not findings,
            'limits':'Pattern scan and filename check; review documents and repository metadata separately.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--history',action='store_true')
    result=audit(parser.parse_args().history)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
