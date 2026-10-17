"""Small shared contracts. No imports from earlier lessons."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRODUCT = 'Bublik Private AI Service'
BASE_SHA = 'c654e24610bdabed15747088f9e1691ed36d0b17'
MAX_BODY = 8192
SECRET = re.compile(r'(?i)(bearer\s+\S+|(?:gsk_|sk-)[A-Za-z0-9_-]{8,}|(?:password|token|api_key|cookie|пароль|токен)\s*[:=]\s*\S+)')


class SupportError(Exception):
    def __init__(self, code, status=422):
        super().__init__(code)
        self.code, self.status = code, status


def require(condition, code='invalid_request', status=422):
    if not condition:
        raise SupportError(code, status)


def safe_text(value, limit=2000):
    require(isinstance(value, str) and 0 < len(value.encode('utf-8')) <= limit)
    require(not SECRET.search(value) and not any(ord(c) < 32 and c not in '\n\t' for c in value), 'unsafe_input')
    return value


def identifier(value, prefix):
    require(isinstance(value, str) and re.fullmatch(prefix + r'-[0-9]{3}', value) is not None)
    return value


def parse_json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'invalid_json')
            obj[key] = value
        return obj
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(SupportError('invalid_json')))
    except (ValueError, UnicodeError, TypeError):
        raise SupportError('invalid_json') from None


def validate_request(request):
    require(isinstance(request, dict) and set(request) <= {'question', 'ticket_id'} and 'question' in request)
    safe_text(request['question'])
    if request.get('ticket_id') is not None:
        identifier(request['ticket_id'], 'T')
    return request
