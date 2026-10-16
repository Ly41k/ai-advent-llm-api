#!/bin/bash
# One selected paired packet on already tested v0.7.18. No rebuild or full suite replay.
set -euo pipefail
set -C

day31_packet="${1:-receipt}"
day31_repo_root="${2:-$PWD}"
case "$day31_packet" in
    receipt)
        day31_ru=receipt-ru
        day31_en=receipt-en
        day31_cap=4 ;;
    assistant)
        day31_ru=assistant-facts-ru
        day31_en=assistant-facts-en
        day31_cap=4 ;;
    dense)
        day31_ru=dense-private-branch-ru
        day31_en=dense-private-branch-en
        day31_cap=6 ;;
    language)
        day31_ru=quote-language-ru
        day31_en=quote-language-en
        day31_cap=4 ;;
    paths)
        day31_ru=path-limit-branch-ru
        day31_en=path-limit-branch-en
        day31_cap=6 ;;
    main)
        day31_ru=main-authority-branch-ru
        day31_en=main-authority-branch-en
        day31_cap=6 ;;
    paraphrase)
        day31_ru=paraphrase-ru
        day31_en=paraphrase-en
        day31_cap=4 ;;
    uncertain)
        day31_ru=uncertain-branch-ru
        day31_en=uncertain-branch-en
        day31_cap=6 ;;
    *) echo "Packet must be receipt, assistant, dense, language, paths, main, paraphrase, or uncertain." >&2; exit 2 ;;
esac
cd "$day31_repo_root"
day31_app=day-31-developer-assistant
day31_cases="$day31_app/evaluation/research_quality_regression_v077.json"
day31_version=$(python "$day31_app/main.py" --version)
if [ "$day31_version" != "0.7.18" ]; then
    echo "This continuation requires the tested complete v0.7.18 source." >&2
    exit 2
fi
day31_prefix="/tmp/day31-paired-${day31_packet}-mac-v088"
for day31_suffix in index-verify plan freeze result; do
    day31_target="${day31_prefix}-${day31_suffix}.json"
    if [ -e "$day31_target" ] || [ -L "$day31_target" ]; then
        echo "Existing output: $day31_target. Stop before model operations; do not replay." >&2
        exit 2
    fi
done

# Reuse the independently matching native preflight; fail before models if code differs.
python - "$day31_app" <<'DAY31_SOURCE_CHECK'
import hashlib,json,sys
from pathlib import Path
app=Path(sys.argv[1])
pre=json.loads(Path('/tmp/day31-stage7-preflight-mac-v088.json').read_text())
expected=pre['source_sha256']
actual={p.relative_to(app).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
if (pre.get('version')!='0.7.18' or pre.get('status')!='passed' or pre.get('tests_run')!=259
        or len(expected)!=59 or actual!=expected):
    raise SystemExit('Source differs from matching native v088 preflight. No model dispatch.')
cases=app/'evaluation/research_quality_regression_v077.json'
if hashlib.sha256(cases.read_bytes()).hexdigest()!='3cd0381ef7ef624b3fa81689ddd20277151389bb5820e12ba32d1a034b7f4010':
    raise SystemExit('Known case catalog differs. No model dispatch.')
print(json.dumps({'source_digests_verified':len(actual),'native_tests_already_passed':259,
                  'inference_performed':False}))
DAY31_SOURCE_CHECK

python "$day31_app/main.py" index verify > "${day31_prefix}-index-verify.json"
python "$day31_app/scripts/compare_single_multi.py" plan --cases "$day31_cases" \
    --case-id "$day31_ru" --case-id "$day31_en" --repeats 1 \
    > "${day31_prefix}-plan.json"
# Validate the zero-model plan before admitting the selected generation cap.
python - "${day31_prefix}-plan.json" "$day31_cap" "$day31_ru" "$day31_en" <<'DAY31_PLAN_CHECK'
import json,sys
from pathlib import Path
p=json.loads(Path(sys.argv[1]).read_text())
if (p.get('case_ids')!=sys.argv[3:] or p.get('pairs')!=2 or p.get('request_observations')!=4
        or p.get('generation_upper_bound')!=int(sys.argv[2])
        or p.get('embedding_calls')!=0 or p.get('inference_performed') is not False
        or p.get('cases_sha256')!='3cd0381ef7ef624b3fa81689ddd20277151389bb5820e12ba32d1a034b7f4010'):
    raise SystemExit('Unexpected plan; stopped before model dispatch.')
DAY31_PLAN_CHECK

python "$day31_app/scripts/compare_single_multi.py" freeze --cases "$day31_cases" \
    --output "${day31_prefix}-freeze.json"
python "$day31_app/scripts/compare_single_multi.py" run --cases "$day31_cases" \
    --freeze "${day31_prefix}-freeze.json" \
    --case-id "$day31_ru" --case-id "$day31_en" --repeats 1 \
    --max-generation-calls "$day31_cap" --output "${day31_prefix}-result.json"
