#!/usr/bin/env python3
"""Read-only delivery integrity check. No application/model execution."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = ('day31-source-anchor-v103-r1', 'day31-anchor-persistence-v104-r1', 'day31-course-minimum-r3')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def safe(root, name):
    rel = Path(name)
    require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe path: ' + name)
    p = root
    for part in rel.parts:
        p = p / part
        require(not p.is_symlink(), 'Symlink: ' + name)
    require(p.is_file(), 'Missing file: ' + name)
    return p


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def verify(root):
    require(HERE == root / 'day-31-course-minimum', 'Run the installed verifier at the selected repository root.')
    delivery = read(HERE / 'delivery-manifest.json')
    for name, digest in delivery['files_sha256'].items():
        require(sha(safe(root, name)) == digest, 'Delivery file differs: ' + name)
    for package in PACKAGES:
        folder = HERE / package
        for name, digest in read(folder / 'manifest.json')['files_sha256'].items():
            require(sha(safe(folder, name)) == digest, 'Original package differs: ' + package + '/' + name)
    app = root / 'day-31-developer-assistant'
    binding = read(HERE / PACKAGES[0] / 'source-binding.json')
    actual = {p.relative_to(app).as_posix(): sha(safe(app, p.relative_to(app).as_posix()))
              for p in sorted(app.rglob('*.py')) if not {'.venv', '__pycache__'}.intersection(p.parts)}
    require(len(actual) == 60 and actual == binding['source_sha256'], 'Base app must retain exactly the reviewed 60 Python files.')
    require(sha(safe(app, 'requirements.lock')) == binding['requirements_sha256'], 'Base requirements differ.')
    evidence = HERE / 'evidence'
    bundle = read(evidence / 'mac-course-minimum-bundle.json')
    require(len(bundle['files']) == 79, 'Expected the original 79-report Mac publication bundle.')
    for name, row in bundle['files'].items():
        require(hashlib.sha256((canonical(row['data']) + '\n').encode()).hexdigest() == row['sha256'], 'Report digest differs: ' + name)
    public = read(evidence / 'accepted-public-result.json')
    review = read(evidence / 'human-review.json')
    check = read(evidence / 'mac-publication-check.json')
    require(sha(evidence / 'mac-course-minimum-bundle.json') == check['source_bundle_sha256'], 'Mac bundle bytes differ.')
    review_sha = hashlib.sha256(canonical(review).encode()).hexdigest()
    require(review_sha == check['review_sha256'] == public['semantic_acceptance']['review_sha256'], 'Human review digest differs.')
    require(public['answer_accepted'] is True and public['semantic_acceptance']['answer_accepted'] is True, 'Historical publication was not accepted.')
    result_binding = public['publication']['result_binding_sha256']
    require(result_binding == review['result_binding_sha256'] == check['result_binding_sha256'], 'Result binding differs.')
    require(review['reviewer'] == {'id': 'yuriy', 'kind': 'human'}, 'Historical reviewer differs.')
    claims = {c['id']: c for c in public['claims']}
    anchors = {a['claim_id']: a for a in public['source_anchors']}
    decisions = {d['claim_id']: d for d in review['decisions']}
    require(set(claims) == set(anchors) == set(decisions) == {'c1', 'c2'}, 'Historical claim set differs.')
    for cid, claim in claims.items():
        anchor, decision = anchors[cid], decisions[cid]
        require(claim['text'] == anchor['text'], 'Claim text differs from its bound anchor: ' + cid)
        require(anchor['binding_sha256'] == decision['binding_sha256'], 'Claim review binding differs: ' + cid)
        require(decision['status'] == 'supported' and all(c['status'] == 'supported' for c in decision['clauses']), 'Historical human decision differs: ' + cid)
    require(any(row['data'] == public for name, row in bundle['files'].items() if name.endswith('-public.json') and '-reviews-' in name), 'Public result is absent from the original Mac bundle.')
    require(any(row['data'] == review for name, row in bundle['files'].items() if name.endswith('-decision.json') and '-reviews-' in name), 'Review is absent from the original Mac bundle.')
    required = list(delivery['files_sha256']) + ['day-31-course-minimum/delivery-manifest.json']
    required += ['day-31-developer-assistant/' + name for name in actual]
    required += [p.relative_to(root).as_posix() for p in (app / 'evaluation').glob('*.json')]
    visibility = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', '-z', '--stdin'],
                                input=('\0'.join(required) + '\0').encode(), capture_output=True, timeout=15)
    require(visibility.returncode in (0, 1), 'Cannot inspect Git ignore rules: ' + visibility.stderr.decode(errors='replace'))
    ignored = [p for p in visibility.stdout.decode().split('\0') if p]
    require(not ignored, 'Required delivery inputs are hidden by Git ignore rules: ' + ', '.join(ignored))
    return {'status': 'passed', 'scope': 'delivery_integrity_and_retained_human_review_only',
            'delivery_files_verified': len(delivery['files_sha256']), 'original_packages_verified': 3,
            'original_app_python_files_verified': 60, 'mac_reports_verified': 79,
            'required_inputs_hidden_by_gitignore': 0,
            'historical_answer_accepted': True, 'new_runtime_or_semantic_acceptance': False,
            'qwen_calls': 0, 'network_calls': 0, 'index_builds': 0, 'git_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.root.resolve())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'stopped', 'error': str(exc), 'qwen_calls': 0}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
