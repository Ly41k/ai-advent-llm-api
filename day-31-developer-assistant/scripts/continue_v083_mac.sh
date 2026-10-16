#!/bin/bash
# One selected paired packet on already tested v0.7.13. No rebuild or full suite replay.
set -euo pipefail
set -C

day31_packet="${1:-unknown}"
day31_repo_root="${2:-$PWD}"
case "$day31_packet" in
    unknown)
        day31_ru=unsupported-knobs-ru
        day31_en=unsupported-knobs-en
        day31_cap=4 ;;
    serialized)
        day31_ru=serialized-model-branch-ru
        day31_en=serialized-model-branch-en
        day31_cap=6 ;;
    untracked)
        day31_ru=allowed-untracked-ru
        day31_en=allowed-untracked-en
        day31_cap=4 ;;
    *) echo "Packet must be unknown, serialized, or untracked." >&2; exit 2 ;;
esac
cd "$day31_repo_root"
day31_app=day-31-developer-assistant
day31_cases="$day31_app/evaluation/research_quality_regression_v077.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.13" ]; then
    echo "This continuation requires the tested complete v0.7.13 source." >&2
    exit 2
fi
day31_prefix="/tmp/day31-paired-${day31_packet}-mac-v083"
for day31_suffix in index-verify plan freeze result; do
    day31_target="${day31_prefix}-${day31_suffix}.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before model operations; do not replay." >&2
        exit 2
    fi
done

# Reuse the independently reviewed native preflight; fail before models if code differs.
python - "$day31_app" <<'DAY31_SOURCE_CHECK'
import hashlib,json,sys
from pathlib import Path
app=Path(sys.argv[1])
pre=json.loads(Path('/tmp/day31-stage7-preflight-mac-v083.json').read_text())
expected=pre['source_sha256']
actual={p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
if (pre.get('version')!='0.7.13' or pre.get('status')!='passed' or pre.get('tests_run')!=252
        or len(expected)!=59 or actual!=expected):
    raise SystemExit('Source differs from reviewed native v083 preflight. No model dispatch.')
print(json.dumps({'source_digests_verified':len(actual),'native_tests_already_passed':252,
                  'inference_performed':False}))
DAY31_SOURCE_CHECK

python "$day31_app/main.py" index verify > "${day31_prefix}-index-verify.json"
python "$day31_app/scripts/compare_single_multi.py" plan --cases "$day31_cases" \
    --case-id "$day31_ru" --case-id "$day31_en" --repeats 1 \
    > "${day31_prefix}-plan.json"
python "$day31_app/scripts/compare_single_multi.py" freeze --cases "$day31_cases" \
    --output "${day31_prefix}-freeze.json"
python "$day31_app/scripts/compare_single_multi.py" run --cases "$day31_cases" \
    --freeze "${day31_prefix}-freeze.json" \
    --case-id "$day31_ru" --case-id "$day31_en" --repeats 1 \
    --max-generation-calls "$day31_cap" --output "${day31_prefix}-result.json"
