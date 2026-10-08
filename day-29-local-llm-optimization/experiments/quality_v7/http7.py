"""Local JSON-schema transport; legacy chat/embedding requests are unchanged."""
from copy import deepcopy
import json
from urllib.parse import urlsplit
from bridge29 import StructuredHTTP
from rag28 import ReliableHTTP
from selection7 import PREFIX, ROLES, selection_schema


class SelectionHTTP(StructuredHTTP):
    def request(self, url, body=None, headers=None):
        if body is not None and urlsplit(url).path == '/api/chat':
            payload = json.loads(body['messages'][1]['content'])
            if str(payload.get('contract', '')).startswith(PREFIX):
                ids = payload['allowed_ids']
                if set(ids) != set(ROLES) or any(not isinstance(ids[k], list) for k in ROLES):
                    raise ValueError('Invalid role catalog for selector schema.')
                schema = selection_schema(ids)
                if schema != payload['schema']:
                    raise ValueError('Sealed prompt schema differs from request schema.')
                body = deepcopy(body)
                body['format'] = schema
                # Avoid the legacy claims schema replacing the selector schema.
                return ReliableHTTP.request(self, url, body, headers)
        return super().request(url, body, headers)
