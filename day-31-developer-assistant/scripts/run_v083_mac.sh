#!/bin/bash
# New shared source/coverage instructions; first paired serialized packet, cap 6.
set -euo pipefail
set -C
day31_repo_root="${1:-$PWD}"
cd "$day31_repo_root"
day31_app=day-31-developer-assistant
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.13" ]; then
    echo "Install the complete v0.7.13 directory first." >&2
    exit 2
fi
for day31_name in stage7-preflight quality-admission ollama-version; do
    day31_target="/tmp/day31-${day31_name}-mac-v083.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before models; do not replay." >&2
        exit 2
    fi
done
for day31_suffix in index-verify plan freeze result; do
    day31_target="/tmp/day31-paired-serialized-mac-v083-${day31_suffix}.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before models; do not replay." >&2
        exit 2
    fi
done
python -W error::ResourceWarning "$day31_app/scripts/check_stage7.py" \
    --output /tmp/day31-stage7-preflight-mac-v083.json
python "$day31_app/scripts/check_bilingual_retrieval.py" \
    --output /tmp/day31-quality-admission-mac-v083.json
python - /tmp/day31-ollama-version-mac-v083.json <<'DAY31_VERSION_PY'
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path('day-31-developer-assistant').resolve()))
from bublik_developer.rag.embeddings import LocalEmbeddings
from bublik_developer.research import write_new
value=LocalEmbeddings(None).request('/api/version')
version=value.get('version')
if not isinstance(version,str) or len(version)>80 or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?',version):
    raise SystemExit('Invalid bounded Ollama server version; no generation performed.')
write_new(Path(sys.argv[1]),{'format':'ollama-server-version-v1','server_version':version,
                           'endpoint':'/api/version','http_method':'GET','generation_calls':0,'embedding_calls':0})
print(json.dumps({'server_version':version,'generation_calls':0}))
DAY31_VERSION_PY
bash "$day31_app/scripts/continue_v083_mac.sh" serialized "$PWD"
