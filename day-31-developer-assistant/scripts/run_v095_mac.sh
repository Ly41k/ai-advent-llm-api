#!/bin/bash
# Clause-to-ID support and whole-answer nonrepetition; one positive EN Doc control, cap1.
set -euo pipefail
set -C

day31_repo_root="${1:-$PWD}"
cd "$day31_repo_root"
day31_app="day-31-developer-assistant"
day31_cases="$day31_app/evaluation/diagnostic_serialized_en_v095.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.25" ]; then
    echo "Install the complete v0.7.25 directory first." >&2
    exit 2
fi
for day31_name in stage7-preflight index-verify quality-admission \
    ollama-version diagnostics-plan diagnostics-freeze diagnostics-serialized-en; do
    day31_target="/tmp/day31-${day31_name}-mac-v095.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before model operations; do not replay completed calls." >&2
        exit 2
    fi
done

# A bundle-only existing output also stops before any dispatch.
day31_bundle="/tmp/day31-stage7-mac-v095-bundle.json"
if [ -e "$day31_bundle" ] || [ -L "$day31_bundle" ]; then
    echo "Existing bundle: $day31_bundle. No model dispatch." >&2
    exit 2
fi
# Preserve partial failure reports without retrying; propagate original exit code.
day31_bundle_on_exit() {
    day31_original_exit=$?
    trap - EXIT
    set +e
    bash "$day31_app/scripts/bundle_reports_v095.sh" "$day31_bundle" /tmp/day31-stage7-preflight-mac-v095.json /tmp/day31-index-verify-mac-v095.json /tmp/day31-quality-admission-mac-v095.json /tmp/day31-ollama-version-mac-v095.json /tmp/day31-diagnostics-plan-mac-v095.json /tmp/day31-diagnostics-freeze-mac-v095.json /tmp/day31-diagnostics-serialized-en-mac-v095.json
    day31_bundle_exit=$?
    if [ "$day31_original_exit" -ne 0 ]; then exit "$day31_original_exit"; fi
    exit "$day31_bundle_exit"
}
trap day31_bundle_on_exit EXIT

python -W error::ResourceWarning "$day31_app/scripts/check_stage7.py" \
    --output /tmp/day31-stage7-preflight-mac-v095.json
python "$day31_app/main.py" index verify > /tmp/day31-index-verify-mac-v095.json
python "$day31_app/scripts/check_bilingual_retrieval.py" \
    --output /tmp/day31-quality-admission-mac-v095.json

python - /tmp/day31-ollama-version-mac-v095.json <<'DAY31_VERSION_PY'
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

python - "$day31_app" <<'DAY31_SOURCE_CHECK'
import hashlib,json,sys
from pathlib import Path
app=Path(sys.argv[1])
pre=json.loads(Path('/tmp/day31-stage7-preflight-mac-v095.json').read_text())
expected=pre['source_sha256']
actual={p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
if (pre.get('version')!='0.7.25' or pre.get('status')!='passed' or pre.get('tests_run')!=262
        or len(expected)!=59 or actual!=expected):
    raise SystemExit('Source differs from matching native v095 preflight. No model dispatch.')
cases=app/'evaluation/research_quality_regression_v077.json'
if hashlib.sha256(cases.read_bytes()).hexdigest()!='3cd0381ef7ef624b3fa81689ddd20277151389bb5820e12ba32d1a034b7f4010':
    raise SystemExit('Known case catalog differs. No model dispatch.')
print(json.dumps({'source_digests_verified':len(actual),'native_tests_already_passed':262,
                  'inference_performed':False}))
DAY31_SOURCE_CHECK

python "$day31_app/scripts/research_project.py" plan --cases "$day31_cases" \
    --case-id serialized-doc-en > /tmp/day31-diagnostics-plan-mac-v095.json
python - /tmp/day31-diagnostics-plan-mac-v095.json <<'DAY31_DIAGNOSTIC_PLAN'
import json,sys
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text())
if (p.get('case_ids')!=['serialized-doc-en'] or p.get('request_count')!=1
        or p.get('generation_upper_bound')!=1 or p.get('embedding_calls')!=0
        or p.get('inference_performed') is not False or p.get('pipeline_mode')!='fts'
        or p.get('cases_sha256')!='14b70f83bc93ca1c46b70cc819d7b58a8b8a1aa6e7f8cb5726d23fcbde71b4bc'):
    raise SystemExit('Unexpected diagnostic plan; no dispatch.')
DAY31_DIAGNOSTIC_PLAN

python "$day31_app/scripts/research_project.py" freeze --cases "$day31_cases" \
    --output /tmp/day31-diagnostics-freeze-mac-v095.json
python "$day31_app/scripts/research_project.py" run --cases "$day31_cases" \
    --freeze /tmp/day31-diagnostics-freeze-mac-v095.json \
    --case-id serialized-doc-en --max-generation-calls 1 \
    --output /tmp/day31-diagnostics-serialized-en-mac-v095.json
