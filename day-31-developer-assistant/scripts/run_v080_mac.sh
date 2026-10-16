#!/bin/bash
# Monolingual prose prompt; one production Documentation call; schema unchanged.
set -euo pipefail
set -C

day31_repo_root="${1:-$PWD}"
cd "$day31_repo_root"
day31_app="day-31-developer-assistant"
day31_cases="$day31_app/evaluation/research_quality_regression_v077.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.10" ]; then
    echo "Install the complete v0.7.10 directory first." >&2
    exit 2
fi
for day31_name in stage7-preflight index-verify quality-admission \
    ollama-version diagnostics-plan diagnostics-freeze diagnostics-untracked-ru; do
    day31_target="/tmp/day31-${day31_name}-mac-v080.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before model operations; do not replay completed calls." >&2
        exit 2
    fi
done

python -W error::ResourceWarning "$day31_app/scripts/check_stage7.py" \
    --output /tmp/day31-stage7-preflight-mac-v080.json
python "$day31_app/main.py" index verify > /tmp/day31-index-verify-mac-v080.json
python "$day31_app/scripts/check_bilingual_retrieval.py" \
    --output /tmp/day31-quality-admission-mac-v080.json

python - /tmp/day31-ollama-version-mac-v080.json <<'DAY31_VERSION_PY'
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

python "$day31_app/scripts/research_project.py" plan --cases "$day31_cases" \
    --case-id allowed-untracked-ru > /tmp/day31-diagnostics-plan-mac-v080.json
python "$day31_app/scripts/research_project.py" freeze --cases "$day31_cases" \
    --output /tmp/day31-diagnostics-freeze-mac-v080.json
python "$day31_app/scripts/research_project.py" run --cases "$day31_cases" \
    --freeze /tmp/day31-diagnostics-freeze-mac-v080.json \
    --case-id allowed-untracked-ru --max-generation-calls 1 \
    --output /tmp/day31-diagnostics-untracked-ru-mac-v080.json
