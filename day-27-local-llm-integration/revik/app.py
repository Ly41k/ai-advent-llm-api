"""No cloud provider. Git index is authoritative; LLM output is advisory."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
import xml.etree.ElementTree as ET
from .i18n import reviewer_prompt, tr

DEFAULT = {
    'language': 'ru',
    'tone': 'professional',
    'detekt_config': 'detekt/detekt.yml',
    'detekt_command': ['detekt'],
    'detekt_plugins': [],
    'baseline': None,
    'build_upon_default_config': False,
    'detekt_timeout': 180,
    'ollama_url': 'http://127.0.0.1:11434',
    'model': 'qwen2.5:14b',
    'llm_timeout': 180,
    'num_ctx': 8192,
    'num_predict': 1500,
    'require_llm': True,
    'max_findings_for_llm': 12,
    'snippet_lines': 3,
}

class RevikError(RuntimeError):
    pass


def run(cmd, cwd, timeout=30):
    try:
        return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RevikError(f'Cannot run {cmd[0]}: {type(e).__name__}') from None


def git(root, *args):
    p = run(['git', *args], root)
    if p.returncode:
        raise RevikError('Git failed: ' + p.stderr.decode('utf-8', 'replace')[:1500])
    return p.stdout


def root_path():
    return Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').decode().strip()).resolve()


def safe_rel(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or '\\' in value:
        raise RevikError(f'Expected repository-relative path: {value!r}')
    return str(p)


def settings(root, overrides=None):
    cfg = dict(DEFAULT)
    path = root / '.revik.json'
    if path.exists():
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or set(value) - set(DEFAULT):
            raise RevikError('Unknown settings or non-object .revik.json')
        cfg.update(value)
    cfg.update({k: v for k, v in (overrides or {}).items() if v is not None})
    if cfg['language'] not in ('ru', 'en'):
        raise RevikError('language must be ru or en')
    if cfg['tone'] not in ('professional', 'light_troll', 'hard_troll'):
        raise RevikError('tone must be professional, light_troll or hard_troll')
    cfg['detekt_config'] = safe_rel(cfg['detekt_config'])
    if cfg['baseline'] is not None:
        cfg['baseline'] = safe_rel(cfg['baseline'])
    cmd = cfg['detekt_command']
    if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd):
        raise RevikError('detekt_command must be a nonempty JSON array of arguments')
    # Resolve local tool arguments before changing cwd to the immutable snapshot.
    cfg['detekt_command'] = [str((root / x).resolve()) if (root / x).is_file() else x for x in cmd]
    plugins = cfg['detekt_plugins']
    if not isinstance(plugins, list) or not all(isinstance(x, str) for x in plugins):
        raise RevikError('detekt_plugins must be a list of local jar paths')
    cfg['detekt_plugins'] = [str((root / x).resolve()) for x in plugins]
    for key in ('detekt_timeout', 'llm_timeout', 'num_ctx', 'num_predict', 'max_findings_for_llm', 'snippet_lines'):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise RevikError(f'{key} must be a positive integer')
    for key in ('require_llm', 'build_upon_default_config'):
        if type(cfg[key]) is not bool:
            raise RevikError(f'{key} must be boolean')
    u = urlsplit(cfg['ollama_url'])
    if u.scheme != 'http' or u.hostname not in ('127.0.0.1', 'localhost', '::1') or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment:
        raise RevikError('Ollama URL must be loopback HTTP, without credentials or URL path')
    if not isinstance(cfg['model'], str) or not cfg['model'].strip() or 'cloud' in cfg['model'].lower():
        raise RevikError('Choose a downloaded local model, without cloud tags')
    return cfg


def tree_files(root, tree):
    files = {}
    for record in git(root, 'ls-tree', '-r', '-z', tree).split(b'\0'):
        if not record:
            continue
        meta, name = record.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        files[name.decode('utf-8')] = (mode, kind, oid)
    return files


def selected_files(root, tree, files, cfg):
    head = run(['git', 'rev-parse', '--verify', 'HEAD^{tree}'], root)
    if head.returncode:
        changed = set(files)
    else:
        base = head.stdout.decode().strip()
        data = git(root, 'diff', '--no-renames', '--name-only', '-z', '--diff-filter=ACMRT', base, tree, '--')
        changed = {x.decode('utf-8') for x in data.split(b'\0') if x}
    # Any config or baseline change revalidates the complete staged Kotlin tree.
    deleted = set()
    if not head.returncode:
        deleted = {x.decode('utf-8') for x in git(root, 'diff', '--no-renames', '--name-only', '-z', base, tree, '--').split(b'\0') if x}
    controls = {cfg['detekt_config']} | ({cfg['baseline']} if cfg['baseline'] else set())
    all_sources = bool((changed | deleted) & controls)
    sources = sorted(x for x in files if x.endswith(('.kt', '.kts')) and (all_sources or x in changed))
    return sources, all_sources


def materialize(root, snapshot, files, paths):
    for name in sorted(set(paths)):
        safe_rel(name)
        if name not in files:
            raise RevikError(f'Not in Git index: {name}; run git add')
        mode, kind, oid = files[name]
        if mode not in ('100644', '100755') or kind != 'blob':
            raise RevikError(f'Symlink/submodule is not supported for analyzed input: {name}')
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(root, 'cat-file', 'blob', oid))


def parse_xml(path, snapshot, sources):
    if not path.is_file():
        raise RevikError('Detekt did not create a fresh XML report')
    doc = ET.parse(path)
    if doc.getroot().tag != 'checkstyle':
        raise RevikError('Unexpected Detekt XML schema')
    findings = []
    for node in doc.getroot().findall('file'):
        raw = Path(node.attrib['name'])
        candidate = raw if raw.is_absolute() else snapshot / raw
        try:
            relative = candidate.resolve().relative_to(snapshot.resolve()).as_posix()
        except ValueError:
            raise RevikError('Detekt returned a path outside the analyzed snapshot') from None
        if relative not in sources:
            raise RevikError('Detekt reported an unselected source')
        for error in node.findall('error'):
            findings.append({'path': relative, 'line': max(1, int(error.get('line', 1))),
                             'column': max(1, int(error.get('column', 1))),
                             'rule': error.get('source', 'Detekt'),
                             'severity': error.get('severity', 'warning'),
                             'message': error.get('message', '')})
    return findings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def explain(cfg, payload):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    base = cfg['ollama_url'].rstrip('/')
    def request(endpoint, body):
        req = Request(base + endpoint, data=json.dumps(body, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=cfg['llm_timeout']) as response:
            value = json.load(response)
        if not isinstance(value, dict) or value.get('error'):
            raise RevikError('Ollama returned an error or invalid object')
        return value
    model = cfg['model']
    info = request('/api/show', {'model': model})
    if info.get('remote_host') or info.get('remote_model'):
        raise RevikError('Ollama model uses a remote backend')
    messages = [
        {'role': 'system', 'content': reviewer_prompt(cfg['language'], cfg['tone'])},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
    started = time.monotonic()
    data = request('/api/chat', {'model': model, 'messages': messages, 'stream': False,
                 'keep_alive': '5m', 'options': {'temperature': 0, 'num_ctx': cfg['num_ctx'], 'num_predict': cfg['num_predict']}})
    text = data.get('message', {}).get('content')
    actual = data.get('model')
    if actual not in (model, model + ':latest') or data.get('done') is not True or data.get('done_reason') != 'stop' or not isinstance(text, str) or not text.strip():
        raise RevikError('Ollama returned empty, incomplete, or wrong-model answer')
    return {'language': cfg['language'], 'tone': cfg['tone'], 'model': actual, 'answer': text.strip(), 'elapsed_seconds': round(time.monotonic() - started, 3),
            'prompt_sha256': hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
            'input_tokens': data.get('prompt_eval_count'), 'output_tokens': data.get('eval_count'),
            'local_inference': True}


def links(root, finding):
    target = root / finding['path']
    return {'file': target.as_uri(),
            'vscode': 'vscode://file/' + quote(str(target).lstrip('/'), safe='/') + f":{finding['line']}:{finding['column']}"}


def save_report(root, report):
    directory = Path(git(root, 'rev-parse', '--git-path', 'revik-reports').decode().strip())
    if not directory.is_absolute():
        directory = root / directory
    directory.mkdir(parents=True, exist_ok=True)
    language = report.get('language', 'ru')
    lines = [f"# {tr(language, 'name')}: {report['status']}", '', report.get('reason', ''), '',
             f"Git tree: `{report.get('tree', '')}`", '', tr(language, 'staged_note'), '']
    for i, f in enumerate(report.get('findings', []), 1):
        f['id'] = i
        f['links'] = links(root, f)
        lines += [f"## {i}. {f['rule']}", '', f"{f['path']}:{f['line']}:{f['column']}", '',
                  f['message'], '', f"[{tr(language, 'file')}]({f['links']['file']}) · [VS Code, {tr(language, 'line')} {f['line']}]({f['links']['vscode']})", '']
    if report.get('llm'):
        lines += ['## ' + tr(language, 'llm_advice'), '', report['llm']['answer'], '']
    if report.get('llm_error'):
        lines += [tr(language, 'llm_error') + report['llm_error'], '']
    for name, content in [('latest.json', json.dumps(report, ensure_ascii=False, indent=2)), ('latest.md', '\n'.join(lines))]:
        with tempfile.NamedTemporaryFile('w', dir=directory, encoding='utf-8', delete=False) as out:
            out.write(content + '\n')
            temp = out.name
        os.replace(temp, directory / name)
    # HTML is escaped; recommendations cannot inject executable markup.
    items = []
    for f in report.get('findings', []):
        items.append('<li><a href="' + html.escape(f['links']['vscode'], quote=True) + '">' +
                     html.escape(f"{f['path']}:{f['line']}:{f['column']}") + '</a> — ' + html.escape(f['rule'] + ': ' + f['message']) + '</li>')
    page = '<!doctype html><meta charset="utf-8"><title>' + tr(language, 'name') + '</title><h1>' + html.escape(report['status']) + '</h1><p>' + html.escape(report.get('reason', '')) + '</p><p>' + html.escape(tr(language, 'staged_note')) + '</p><ul>' + ''.join(items) + '</ul><pre style="white-space:pre-wrap">' + html.escape((report.get('llm') or {}).get('answer', report.get('llm_error', ''))) + '</pre>'
    (directory / 'latest.html').write_text(page, encoding='utf-8')
    print(tr(language, 'report') + (directory / 'latest.html').as_uri(), flush=True)
    print('JSON: ' + str(directory / 'latest.json'), flush=True)


def check(root, cfg):
    language = cfg['language']
    tree = git(root, 'write-tree').decode().strip()
    files = tree_files(root, tree)
    report = {'language': language, 'tone': cfg['tone'], 'schema_version': 1, 'tree': tree, 'status': 'skipped', 'findings': [], 'llm': None}
    if cfg['detekt_config'] not in files:
        report['reason'] = tr(language, 'missing_config', path=cfg['detekt_config'])
        return report, 0
    sources, all_sources = selected_files(root, tree, files, cfg)
    report.update(files=sources, scope='all_staged_kotlin' if all_sources else 'changed_staged_kotlin')
    if not sources:
        report['reason'] = tr(language, 'no_sources')
        return report, 0
    print(tr(language, 'checking', count=len(sources)), flush=True)
    with tempfile.TemporaryDirectory(prefix='revik-') as temporary:
        snapshot = Path(temporary) / 'sources'
        snapshot.mkdir()
        paths = sources + [cfg['detekt_config']] + ([cfg['baseline']] if cfg['baseline'] else [])
        materialize(root, snapshot, files, paths)
        xml = Path(temporary) / 'detekt.xml'
        cmd = cfg['detekt_command'] + ['--input', str(snapshot), '--config', str(snapshot / cfg['detekt_config']),
                                     '--base-path', str(snapshot), '--report', 'xml:' + str(xml)]
        if cfg['baseline']:
            cmd += ['--baseline', str(snapshot / cfg['baseline'])]
        if cfg['build_upon_default_config']:
            cmd += ['--build-upon-default-config']
        if cfg['detekt_plugins']:
            for plugin in cfg['detekt_plugins']:
                if not Path(plugin).is_file():
                    raise RevikError('Missing Detekt plugin jar: ' + plugin)
            cmd += ['--plugins', ','.join(cfg['detekt_plugins'])]
        p = run(cmd, snapshot, cfg['detekt_timeout'])
        report['detekt_exit_code'] = p.returncode
        if p.returncode not in (0, 2):
            raise RevikError(f'Detekt failed (exit={p.returncode}): ' + (p.stderr + p.stdout).decode('utf-8', 'replace')[-4000:])
        findings = parse_xml(xml, snapshot, sources)
        report['findings'] = findings
        blocked = bool(findings) or p.returncode != 0
        report['status'] = 'blocked' if blocked else 'allowed'
        report['reason'] = tr(language, 'summary', count=len(findings)) + tr(language, 'blocked' if blocked else 'allowed')
        entries = []
        for i, f in enumerate(findings[:cfg['max_findings_for_llm']], 1):
            content = (snapshot / f['path']).read_text(encoding='utf-8', errors='replace').splitlines()
            start = max(0, f['line'] - 1 - cfg['snippet_lines'])
            end = min(len(content), f['line'] + cfg['snippet_lines'])
            entries.append({'id': i, **f, 'snippet': '\n'.join(f'{j+1}: {content[j][:300]}' for j in range(start, end))})
        payload = {'gate': report['status'], 'checked_file_count': len(sources), 'finding_count': len(findings),
                   'omitted_findings': len(findings) - len(entries), 'findings': entries}
        print(tr(language, 'calling'), flush=True)
        try:
            report['llm'] = explain(cfg, payload)
        except Exception as e:
            report['llm_error'] = f'{type(e).__name__}: {e}'
            if cfg['require_llm']:
                report['status'] = 'error'
                report['reason'] += tr(language, 'llm_failed')
        if git(root, 'write-tree').decode().strip() != tree:
            report['status'] = 'error'
            report['reason'] += tr(language, 'index_changed')
    return report, 0 if report['status'] == 'allowed' else (1 if report['status'] == 'blocked' else 2)


def install(root, directory, language="ru"):
    destination = Path(git(root, 'rev-parse', '--git-path', 'hooks/pre-commit').decode().strip())
    if not destination.is_absolute():
        destination = root / destination
    marker = '# Installed by Revik 1.0'
    if destination.exists() and marker not in destination.read_text(encoding='utf-8'):
        raise RevikError('Existing pre-commit hook preserved. Add the command manually; see README.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Absolute interpreter for IDE commits where shell PATH differs.
    script = '#!/bin/sh\n' + marker + '\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(directory / 'revik_cli.py')) + ' check\n'
    destination.write_text(script, encoding='utf-8')
    destination.chmod(0o755)
    print(tr(language, 'installed') + str(destination))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ревик — Detekt staged gate + local Ollama')
    parser.add_argument('command', choices=['check', 'install', 'doctor'])
    parser.add_argument('--language', choices=('ru', 'en'), help='Override .revik.json for this run')
    parser.add_argument('--tone', choices=('professional', 'light_troll', 'hard_troll'), help='Override reviewer tone for this run')
    args = parser.parse_args(argv)
    root = None
    language = args.language or 'ru'
    cfg = None
    try:
        root = root_path()
        cfg = settings(root, {'language': args.language, 'tone': args.tone})
        language = cfg['language']
        if args.command == 'install':
            install(root, Path(__file__).resolve().parent.parent, language)
            return 0
        if args.command == 'doctor':
            print(json.dumps(cfg, ensure_ascii=False, indent=2))
            p = run(cfg['detekt_command'] + ['--version'], root)
            if p.returncode:
                raise RevikError('Detekt --version failed')
            print(p.stdout.decode('utf-8', 'replace'))
            result = explain(cfg, {'gate': 'diagnostic', 'finding_count': 0, 'findings': []})
            print(result['answer'])
            print('Local inference OK: ' + result['model'])
            return 0
        report, code = check(root, cfg)
        for f in report['findings']:
            print(f"{root / f['path']}:{f['line']}:{f['column']}: {f['rule']}: {f['message']}")
        if report.get('llm'):
            print('\n' + tr(language, 'llm_heading') + '\n' + report['llm']['answer'])
        print('\n' + report['reason'])
        save_report(root, report)
        return code
    except KeyboardInterrupt:
        print('\n' + tr(language, 'interrupted'), file=sys.stderr)
        return 130
    except Exception as e:
        message = f'{type(e).__name__}: {e}'
        print(tr(language, 'error') + message, file=sys.stderr)
        if root and args.command == 'check':
            try:
                save_report(root, {'language': language, 'tone': (cfg or DEFAULT)['tone'], 'status': 'error', 'reason': message, 'findings': []})
            except Exception:
                pass
        return 2
