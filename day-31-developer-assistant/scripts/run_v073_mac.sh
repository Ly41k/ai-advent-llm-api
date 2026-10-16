#!/bin/bash
# Native validation -> hybrid rebuild -> zero-model FTS gate -> bounded paired Qwen.
set -euo pipefail
set -C

day31_repo_root="${1:-$PWD}"
cd "$day31_repo_root"
day31_app="day-31-developer-assistant"
day31_cases="$day31_app/evaluation/research_bilingual_regression_v073.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.3" ]; then
    echo "Install the complete v0.7.3 directory before running this helper." >&2
    exit 2
fi

for day31_report_name in \
    stage7-preflight models-status index-build index-verify bilingual-retrieval \
    bilingual-freeze bilingual-main bilingual-path bilingual-dense bilingual-unknown; do
    day31_target="/tmp/day31-${day31_report_name}-mac-v073.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing report: $day31_target. No calls started; use the README to continue from a stopped step." >&2
        exit 2
    fi
done

python -W error::ResourceWarning "$day31_app/scripts/check_stage7.py" \
    --output /tmp/day31-stage7-preflight-mac-v073.json

python "$day31_app/main.py" models status > /tmp/day31-models-status-mac-v073.json
python - <<'DAY31_GATE'
import json
from pathlib import Path
value=json.loads(Path('/tmp/day31-models-status-mac-v073.json').read_text())
if value.get('gate_open') is not True:
    raise SystemExit('Model gate is closed. Stop before rebuild/inference; follow the existing prepare/operator-restart/confirm procedure.')
DAY31_GATE

python "$day31_app/main.py" index build --mode hybrid > /tmp/day31-index-build-mac-v073.json
python "$day31_app/main.py" index verify > /tmp/day31-index-verify-mac-v073.json
python "$day31_app/scripts/check_bilingual_retrieval.py" \
    --output /tmp/day31-bilingual-retrieval-mac-v073.json
python "$day31_app/scripts/compare_single_multi.py" freeze \
    --cases "$day31_cases" --output /tmp/day31-bilingual-freeze-mac-v073.json

run_day31_pair() {
    local day31_topic="$1"
    local day31_ru="$2"
    local day31_en="$3"
    python "$day31_app/scripts/compare_single_multi.py" run \
        --cases "$day31_cases" --freeze /tmp/day31-bilingual-freeze-mac-v073.json \
        --case-id "$day31_ru" --case-id "$day31_en" \
        --repeats 1 --max-generation-calls 6 \
        --output "/tmp/day31-bilingual-${day31_topic}-mac-v073.json"
}

run_day31_pair main main-authority-branch-ru main-authority-branch-en
run_day31_pair path path-limit-branch-ru path-limit-branch-en
run_day31_pair dense dense-private-branch-ru dense-private-branch-en

# Corpus changed: ensure unsupported parameter questions still abstain.
python "$day31_app/scripts/compare_single_multi.py" run \
    --cases "$day31_cases" --freeze /tmp/day31-bilingual-freeze-mac-v073.json \
    --case-id unsupported-knobs-ru --case-id unsupported-knobs-en \
    --repeats 1 --max-generation-calls 4 \
    --output /tmp/day31-bilingual-unknown-mac-v073.json
