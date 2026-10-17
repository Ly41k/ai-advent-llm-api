"""Read pinned Day 33 inputs, create Markdown only in an exclusive Day 34 run."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

MODULE = 'day-34-file-assistant'
MAX_FILE = 65536
MAX_DOCUMENT = 20000
MAX_OPERATIONS = 24
CORE = ['day-33-support-assistant/' + n for n in ('main.py', 'mcp_client.py', 'support_agent.py')]
REF = re.compile(r'([A-Za-z0-9_./-]+\.(?:py|json|md)):(\d+)')


class Rejected(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Rejected(code)


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate_json_key')
            result[k] = v
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, 'nonfinite_json'))
    except (TypeError, UnicodeError, json.JSONDecodeError):
        raise Rejected('invalid_json') from None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parts(path):
    require(isinstance(path, str) and 0 < len(path) <= 240, 'invalid_path')
    p = PurePosixPath(path)
    require(not p.is_absolute() and '\\' not in path and '\x00' not in path
            and all(x not in ('', '.', '..') for x in path.split('/')), 'unsafe_path')
    return p.parts


def directory(root, components, create=False):
    """Walk directory descriptors, rejecting symlinks including during races."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in components:
            if create:
                try:
                    os.mkdir(name, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_bytes(root, path):
    components = parts(path)
    parent = directory(root, components[:-1])
    try:
        fd = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_FILE, 'input_size_or_type')
            raw = stream.read(MAX_FILE + 1)
            require(len(raw) <= MAX_FILE, 'input_too_large')
            return raw
    finally:
        os.close(parent)


def exclusive_write(root, path, raw):
    parent = directory(root, parts(path)[:-1])
    try:
        fd = os.open(parts(path)[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(parent)


class FileTools:
    def __init__(self, root, run_id, manifest, read_policy='strict-v1'):
        require(read_policy in ('strict-v1', 'bounded-v2', 'bounded-v3'), 'unknown_read_policy')
        self.read_policy = read_policy
        self.root = Path(root).resolve()
        require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', run_id or '') is not None, 'invalid_run_id')
        self.expected = dict(manifest['files'])
        require(set(CORE) <= self.expected.keys(), 'missing_core_inputs')
        self.inputs = self.snapshot()  # fail before reserving output or provider calls
        self.text = {p: read_bytes(self.root, p).decode('utf-8') for p in sorted(self.expected)}
        require(self.snapshot() == self.inputs, 'inputs_changed_during_load')
        # Verify the content used by tools, not just the surrounding snapshots.
        require(all(digest(t.encode()) == self.expected[p] for p, t in self.text.items()), 'input_hash_mismatch')
        self.output_rel = f'{MODULE}/results/{run_id}'
        parent = directory(self.root, (MODULE, 'results'), create=True)
        try:
            os.mkdir(run_id, 0o700, dir_fd=parent)  # no reuse, no automatic overwrite
        finally:
            os.close(parent)
        self.count = 0
        self.seen = set()
        self.created = {}
        self.evidence = {}

    def snapshot(self):
        actual = {p: digest(read_bytes(self.root, p)) for p in sorted(self.expected)}
        require(actual == self.expected, 'input_hash_mismatch')
        return actual

    def save(self, name, value):
        require(re.fullmatch(r'[A-Za-z0-9_.-]+', name) is not None, 'invalid_artifact_name')
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
        exclusive_write(self.root, self.output_rel + '/' + name, raw)

    def execute(self, action):
        self.count += 1
        require(self.count <= MAX_OPERATIONS, 'operation_limit')
        require(isinstance(action, dict) and set(action) == {'tool', 'args'}, 'invalid_action')
        tool, args = action['tool'], action['args']
        require(isinstance(tool, str) and tool in {'list_files', 'search_files', 'read_file', 'write_file'}, 'unknown_tool')
        require(isinstance(args, dict), 'invalid_arguments')
        return getattr(self, tool)(**self.arguments(tool, args))

    @staticmethod
    def arguments(tool, args):
        fields = {'list_files': (set(), set()),
                  'search_files': ({'query'}, {'paths'}),
                  'read_file': ({'path'}, {'start', 'end'}),
                  'write_file': ({'path', 'content', 'evidence'}, set())}
        required, optional = fields[tool]
        require(required <= set(args) <= required | optional, 'invalid_arguments')
        return args

    def allowed(self, path):
        parts(path)
        require(path in self.text, 'read_not_allowed')
        return self.text[path].splitlines()

    def list_files(self):
        return {'files': [{'path': p, 'lines': len(t.splitlines()), 'sha256': self.inputs[p]}
                          for p, t in self.text.items()]}

    def search_files(self, query, paths=None):
        require(isinstance(query, str) and 0 < len(query) <= 120 and '\n' not in query, 'invalid_query')
        paths = sorted(self.text) if paths is None else paths
        require(isinstance(paths, list) and 1 <= len(paths) <= len(self.text)
                and all(isinstance(p, str) for p in paths) and len(set(paths)) == len(paths), 'invalid_paths')
        matches = []
        for p in paths:
            for i, line in enumerate(self.allowed(p), 1):
                if query in line:
                    matches.append({'path': p, 'line': i, 'text': line})
        require(len(matches) <= 80, 'too_many_matches_narrow_query')
        return {'query': query, 'searched_files': paths, 'matches': matches, 'truncated': False}

    def read_file(self, path, start=1, end=None):
        lines = self.allowed(path)
        end = min(start + 199, len(lines)) if end is None and type(start) is int else end
        require(type(start) is int and type(end) is int and 1 <= start <= len(lines) and start <= end
                and (self.read_policy == 'bounded-v3' or end <= len(lines))
                and (self.read_policy != 'strict-v1' or end - start < 200), 'invalid_line_range')
        requested_end = end
        end = min(end, start + 199, len(lines))
        self.seen.update((path, n) for n in range(start, end + 1))
        result = {'path': path, 'start': start, 'end': end, 'total_lines': len(lines),
                  'lines': [{'line': i, 'text': lines[i-1]} for i in range(start, end + 1)]}
        if requested_end != end:
            result.update(requested_end=requested_end, truncated=True, next_start=end + 1)
            if self.read_policy == 'bounded-v3':
                result.update(next_start=end + 1 if end < len(lines) else None,
                              end_of_file=end == len(lines))
        return result

    def quote_mismatches(self, evidence):
        """Diagnostic only: never repairs an argument, writes, or marks a line read."""
        require(isinstance(evidence, list) and 1 <= len(evidence) <= 40, 'invalid_evidence')
        mismatches = []
        for item in evidence:
            require(isinstance(item, dict) and set(item) == {'path', 'line', 'quote'}, 'invalid_evidence')
            p, n, quote = item['path'], item['line'], item['quote']
            lines = self.allowed(p)
            require(type(n) is int and 1 <= n <= len(lines) and (p, n) in self.seen, 'unread_evidence')
            require(isinstance(quote, str), 'invalid_evidence')
            if quote != lines[n-1]:
                mismatches.append({'path':p, 'line':n, 'provided_quote':quote,
                                   'actual_read_source_line':lines[n-1]})
        return mismatches

    def write_file(self, path, content, evidence):
        parts(path)
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.md', path) is not None, 'write_not_allowed')
        require(isinstance(content, str) and 40 <= len(content.encode()) <= MAX_DOCUMENT, 'invalid_document_size')
        require(isinstance(evidence, list) and 1 <= len(evidence) <= 40, 'invalid_evidence')
        refs = set()
        for item in evidence:
            require(isinstance(item, dict) and set(item) == {'path', 'line', 'quote'}, 'invalid_evidence')
            p, n = item['path'], item['line']
            lines = self.allowed(p)
            require(type(n) is int and 1 <= n <= len(lines) and (p, n) in self.seen, 'unread_evidence')
            require(isinstance(item['quote'], str) and item['quote'] == lines[n-1] and bool(item['quote'].strip()), 'quote_mismatch')
            require((p, n) not in refs, 'duplicate_evidence')
            refs.add((p, n))
        doc_refs = {(p, int(n)) for p, n in REF.findall(content)}
        require(doc_refs == refs, 'document_reference_mismatch')
        raw = content.encode()
        exclusive_write(self.root, self.output_rel + '/' + path, raw)
        self.created[path] = {'path': self.output_rel + '/' + path, 'sha256': digest(raw), 'bytes': len(raw)}
        self.evidence[path] = evidence
        return {'created': path, 'sha256': digest(raw), 'validated_references': len(refs)}
