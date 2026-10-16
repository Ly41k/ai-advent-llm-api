"""Load unchanged pinned dependencies and a separate publication-overlay copy."""
import json,sys
from hashlib import sha256
from pathlib import Path

HERE=Path(__file__).resolve().parent


def load(v103,v104,app,folder):
    sys.path[:0]=[str(v104),str(v103),str(app)]
    import runner as core
    pins=core.read_json(HERE/'dependency-pins.json')
    for root,key in [(v103,'v103_manifest_sha256'),(v104,'v104_manifest_sha256')]:
        manifest=core.read_json(root/'manifest.json')
        if sha256(core.no_symlinks(root/'manifest.json').read_bytes()).hexdigest()!=pins[key]:
            raise core.Stop('Dependency manifest differs: '+key)
        for name,h in manifest['files_sha256'].items():
            if sha256(core.no_symlinks(root/name).read_bytes()).hexdigest()!=h:raise core.Stop('Dependency differs: '+name)
    manifest=core.read_json(HERE/'manifest.json')
    for name,h in manifest['files_sha256'].items():
        if sha256(core.no_symlinks(HERE/name).read_bytes()).hexdigest()!=h:raise core.Stop('Course package differs: '+name)
    binding=core.read_json(v103/'source-binding.json')
    actual={p.relative_to(app).as_posix():sha256(core.no_symlinks(p).read_bytes()).hexdigest()
            for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
    if actual!=binding['source_sha256'] or len(actual)!=60:raise core.Stop('Original app0.7.29 source differs.')
    if sha256((app/'requirements.lock').read_bytes()).hexdigest()!=binding['requirements_sha256']:
        raise core.Stop('Original requirements differ.')
    saved=core.no_symlinks(HERE/'inputs/reviewed-mac83.json')
    if sha256(saved.read_bytes()).hexdigest()!=pins['reviewed_mac83_sha256']:raise core.Stop('Mac83 input differs.')
    bundle=core.read_json(saved)
    for value in bundle['files'].values():
        if sha256((core.canonical(value['data'])+'\n').encode()).hexdigest()!=value['sha256']:raise core.Stop('Mac83 report digest differs.')
    tests=bundle['files']['day31-publication-v104-r2-tests.json']['data']
    if sum(r['tests_run'] for r in tests.values())!=83 or any(r['status']!='passed' or r['qwen_calls']!=0 for r in tests.values()):
        raise core.Stop('Passed native Mac83 required.')
    sys.path.insert(0,str(HERE/'publication_v104r2'))
    from prepare_overlay import prepare
    overlay=folder/'isolated-app'
    if not overlay.exists():prepare(app,overlay,v103)
    expected=dict(actual)
    for name in ['pipeline.py','publication.py']:
        rel='bublik_developer/'+name
        expected[rel]=sha256((HERE/'publication_v104r2/overlay'/rel).read_bytes()).hexdigest()
    observed={p.relative_to(overlay).as_posix():sha256(core.no_symlinks(p).read_bytes()).hexdigest()
              for p in sorted(overlay.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
    if observed!=expected:raise core.Stop('Isolated application differs from the reviewed overlay.')
    sys.path.insert(0,str(overlay))
    import bublik_developer.pipeline as pipeline
    if not Path(pipeline.__file__).resolve().is_relative_to(overlay):raise core.Stop('Wrong pipeline imported.')
    return core,{'package_sha256':core.digest(manifest),'original_python_sha256':actual,
                 'isolated_python_sha256':observed,'original_main_sha256':actual['main.py'],
                 'overlay':str(overlay),'prior_reports':61,'qwen_calls':0}
