"""Create a NEW isolated application copy, never replace the installed app."""
from hashlib import sha256
from pathlib import Path
import json,shutil

HERE=Path(__file__).resolve().parent


def prepare(app,destination,v103):
    app=app.resolve();destination=destination.resolve()
    pins=json.loads((v103/'source-binding.json').read_text())['source_sha256']
    actual={p.relative_to(app).as_posix():sha256(p.read_bytes()).hexdigest()
            for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
    if actual!=pins:raise ValueError('original_app_source_changed')
    if destination.exists():raise FileExistsError('isolated_application_destination_exists')
    if app==destination or app in destination.parents:raise ValueError('overlay_must_be_outside_original_app')
    shutil.copytree(app,destination,ignore=shutil.ignore_patterns('.venv','__pycache__','reports'))
    for p in (HERE/'overlay').rglob('*.py'):
        target=destination/p.relative_to(HERE/'overlay');target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
    if (app/'main.py').read_bytes()!=(destination/'main.py').read_bytes():raise ValueError('main_changed')
    return destination
