#!/bin/bash
# Explicit source/refusal/comparison prompts; same paired order protocol; existing 44/405 index remains current.
set -euo pipefail
set -C

day31_repo_root="${1:-$PWD}"
cd "$day31_repo_root"
day31_app="day-31-developer-assistant"
day31_cases="$day31_app/evaluation/research_quality_regression_v075.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.5" ]; then
    echo "Install the complete v0.7.5 directory first." >&2
    exit 2
fi
for day31_name in stage7-preflight index-verify quality-admission quality-plan quality-freeze \
    quality-serialized quality-untracked quality-unknown; do
    day31_target="/tmp/day31-${day31_name}-mac-v075.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before model operations; do not replay completed calls." >&2
        exit 2
    fi
done

python -W error::ResourceWarning "$day31_app/scripts/check_stage7.py" \
    --output /tmp/day31-stage7-preflight-mac-v075.json
python "$day31_app/main.py" index verify > /tmp/day31-index-verify-mac-v075.json
python "$day31_app/scripts/check_bilingual_retrieval.py" \
    --output /tmp/day31-quality-admission-mac-v075.json

python "$day31_app/scripts/compare_single_multi.py" plan --cases "$day31_cases" \
    --case-id serialized-model-branch-ru --case-id serialized-model-branch-en \
    --case-id allowed-untracked-ru --case-id allowed-untracked-en \
    --case-id unsupported-knobs-ru --case-id unsupported-knobs-en \
    --repeats 1 > /tmp/day31-quality-plan-mac-v075.json
python "$day31_app/scripts/compare_single_multi.py" freeze \
    --cases "$day31_cases" --output /tmp/day31-quality-freeze-mac-v075.json

run_day31_quality() {
    local day31_name="$1"
    local day31_cap="$2"
    local day31_ru="$3"
    local day31_en="$4"
    python "$day31_app/scripts/compare_single_multi.py" run \
        --cases "$day31_cases" --freeze /tmp/day31-quality-freeze-mac-v075.json \
        --case-id "$day31_ru" --case-id "$day31_en" \
        --repeats 1 --max-generation-calls "$day31_cap" \
        --output "/tmp/day31-quality-${day31_name}-mac-v075.json"
}

run_day31_quality serialized 6 serialized-model-branch-ru serialized-model-branch-en
run_day31_quality untracked 4 allowed-untracked-ru allowed-untracked-en
run_day31_quality unknown 4 unsupported-knobs-ru unsupported-knobs-en
