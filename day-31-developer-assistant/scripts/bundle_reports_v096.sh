#!/bin/bash
# Package explicit existing /tmp reports; no inference, repair or overwrite.
set -euo pipefail
python - "$@" <<'DAY31_BUNDLE'
import hashlib,json,sys
from pathlib import Path
if len(sys.argv)<3:
    raise SystemExit('Usage: bundle_reports_v096.sh /tmp/day31-...-bundle.json report...')
out=Path(sys.argv[1]);reports=[Path(x) for x in sys.argv[2:]]
for p in [out,*reports]:
    if p.parent.resolve()!=Path('/tmp').resolve() or not p.name.startswith('day31-') or p.suffix!='.json' or p.is_symlink():
        raise SystemExit('Only explicit nonsymlink day31 JSON reports in /tmp are allowed.')
if out in reports or len({p.name for p in reports})!=len(reports):
    raise SystemExit('Duplicate or self-referencing report paths.')
if out.exists():
    raise SystemExit(f'Bundle already exists: {out}; no overwrite.')
files={};missing=[]
for p in reports:
    if not p.exists():
        missing.append(p.name);continue
    raw=p.read_bytes()
    files[p.name]={'sha256':hashlib.sha256(raw).hexdigest(),'data':json.loads(raw)}
if not files:
    raise SystemExit('No report exists to bundle.')
payload={'schema':'day31-evidence-bundle-v1','files':files}
if missing:
    payload['missing_files']=missing
with out.open('x',encoding='utf-8') as stream:
    json.dump(payload,stream,ensure_ascii=False,indent=2)
    stream.write('\n')
print(json.dumps({'bundle':str(out),'reports':len(files),'missing_files':missing,'generation_calls':0,'embedding_calls':0}))
DAY31_BUNDLE
