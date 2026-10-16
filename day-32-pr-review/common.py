"""Small, fixed policy for a single public course repository. Python 3.12+."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

REPOSITORY = "Ly41k/ai-advent-llm-api"
OWNER = "Ly41k"
TRUSTED_BRANCH = "day32-demo"
MODEL = "openai/gpt-oss-120b"  # Hosted by Groq, NOT an OpenAI API call.
MAX_FILES = 20
MAX_PATCH_BYTES = 32768
MAX_FILE_BYTES = 32768
MAX_INPUT_TOKENS = 4000
MAX_OUTPUT_TOKENS = 2000
TEMPLATE_RESERVE = 1024
MAX_FINDINGS = 5
SHA = re.compile(r"[0-9a-f]{40}")
# Adapted from Day 31 git_tools.SECRET. Heuristics, not a complete secret scanner.
SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|"
    r"\b(?:gsk_|sk-(?:proj-)?)[A-Za-z0-9_-]{16,}\b|"
    r"(?i:authorization\s*[:=]\s*[\"']?bearer\s+\S+)|"
    r"(?i:(?:api[_-]?key|password|secret[_-]?key|access[_-]?token)\s*[\"']?\s*[:=]\s*[\"'][^\"'\n]{12,})"
)


class ReviewError(Exception):
    """Only fixed codes are logged; external response bodies never appear in errors."""


def fail(code):
    raise ReviewError(code)


def contains_secret(value):
    """Scan decoded values too: JSON escaping must not hide assignment patterns."""
    if isinstance(value, str):
        return bool(SECRET.search(value))
    if isinstance(value, dict):
        return any(contains_secret(key) or contains_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_secret(item) for item in value)
    return False


def strict_json(raw):
    """Adapted from Day 24 evidence.parse_json: duplicates/NaN are errors."""
    if not isinstance(raw, str) or len(raw.encode()) > 262144:
        fail("json_size")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                fail("json_duplicate_key")
            result[key] = value
        return result
    def constant(_):
        fail("json_constant")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError):
        fail("invalid_json")


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def safe_path(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        fail("unsafe_path")
    path = PurePosixPath(value)
    if (path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/"))
            or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or SECRET.search(value)):
        fail("unsafe_path")
    return value


def local_file(root, name):
    safe_path(name)
    root = Path(root).resolve()
    target = root / name
    if any(part.is_symlink() for part in [target, *target.parents] if part != root.parent):
        fail("symlink")
    if not target.resolve().is_relative_to(root):
        fail("unsafe_path")
    return target


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("invalid_sha")
    return value


def number(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        fail("invalid_pr_number")
    return value


def check_pr(pr, expected_head, source_revision, actor):
    """Branch trust ALSO requires owner-controlled push permissions; see README."""
    sha(expected_head)
    sha(source_revision)
    try:
        valid = (pr["state"] == "open" and pr["base"]["repo"]["full_name"] == REPOSITORY
                 and pr["head"]["repo"]["full_name"] == REPOSITORY
                 and pr["base"]["repo"]["private"] is False
                 and pr["head"]["repo"]["private"] is False
                 and pr["base"]["ref"] == "main" and pr["head"]["ref"] == TRUSTED_BRANCH
                 and pr["user"]["login"] == OWNER and actor == OWNER)
        if not valid:
            fail("untrusted_pr")
        if pr["head"]["sha"] != expected_head or pr["base"]["sha"] != source_revision:
            fail("sha_changed")
        number(pr["number"])
    except (KeyError, TypeError):
        fail("invalid_pr_metadata")


def assert_same(before, after):
    try:
        if any(before[part]["sha"] != after[part]["sha"] for part in ("base", "head")):
            fail("sha_changed")
    except (KeyError, TypeError):
        fail("invalid_pr_metadata")
