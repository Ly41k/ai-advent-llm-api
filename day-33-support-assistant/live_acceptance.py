"""One approved Mac call, with observable MCP/HTTP receipts. No alternate pipeline."""
import argparse
import getpass
import hashlib
import json
import os
import platform
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

from common import ROOT, SupportError, parse_json, require
import llm_adapter
import mcp_client
from support_agent import answer

TARGET = Path('/tmp/day33-live-mac.json')
OFFLINE = Path('/tmp/day33-offline-mac.json')
QUESTION = 'Почему не работает авторизация?'
EXPECTED_SOURCES = ['DOC-ERRORS', 'FAQ-AUTH', 'DOC-AUTH']


def check_offline(path=OFFLINE):
    report_path = path
    report = parse_json(path.read_bytes())
    require(report.get('status') == 'passed' and report.get('tests_run') == 22
            and report.get('failures') == 0 and report.get('errors') == 0
            and report.get('skipped') == 0 and report.get('real_generation_calls') == 0,
            'offline_acceptance_required')
    manifest = report.get('source_sha256', {})
    require(isinstance(manifest, dict) and len(manifest) == 15, 'invalid_offline_manifest')
    for name, expected in manifest.items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT), 'invalid_offline_manifest')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                'source_changed_since_Mac_acceptance')
    return {'manifest_files': len(manifest), 'manifest_matched': True,
            'report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest()}


def execute_once():
    """Instrument real SDK calls and the existing GroqAdapter, never synthesize results."""
    receipt = {'status': 'failed', 'scope': 'one_real_Groq_E2E',
               'execution_environment': platform.platform(),
               'mcp_calls': [], 'http': {'post_attempts': 0, 'status': None},
               'automatic_retries': 0, 'fallback_calls': 0, 'result': None}
    real_call = mcp_client.call
    real_build = llm_adapter.urllib.request.build_opener
    secret = os.environ.get('GROQ_API_KEY', '')

    async def traced_call(session, name, arguments):
        expected = [('get_ticket', {'ticket_id': 'T-101'}),
                    ('get_user', {'user_id': 'U-001'})]
        index = len(receipt['mcp_calls'])
        require(index < 2 and (name, arguments) == expected[index], 'unexpected_MCP_call')
        event = {'tool': name, 'arguments': arguments, 'completed': False}
        receipt['mcp_calls'].append(event)
        value = await real_call(session, name, arguments)
        record = value.get('ticket' if name == 'get_ticket' else 'user')
        require(isinstance(record, dict) and record.get('synthetic') is True,
                'invalid_synthetic_context')
        event.update(completed=True, user_id=record.get('user_id'))
        if name == 'get_ticket':
            event['ticket_id'] = record.get('ticket_id')
        return value

    class ObservedResponse:
        def __init__(self, response):
            self.response = response
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.response.close()
        def read(self, limit):
            raw = self.response.read(limit)
            try:
                # Preserve only provider/model data, never credentials or request headers.
                value = parse_json(raw)
                receipt['http']['usage'] = value.get('usage')
                receipt['http']['response_id'] = value.get('id')
                choice = value['choices'][0]
                receipt['http']['finish_reason'] = choice.get('finish_reason')
                content = choice['message']['content']
                if isinstance(content, str):
                    cleaned = content.replace(secret, '[REDACTED]') if secret else content
                    receipt['model_reply'] = cleaned
                    try:
                        receipt['model_plan'] = parse_json(cleaned)
                    except SupportError:
                        pass
            except Exception:
                pass
            return raw

    class ObservedOpener:
        def __init__(self, opener):
            self.opener = opener
        def open(self, request, timeout):
            require(receipt['http']['post_attempts'] == 0, 'second_POST_blocked', 403)
            require(request.method == 'POST' and request.full_url ==
                    'https://api.groq.com/openai/v1/chat/completions', 'unexpected_endpoint')
            data = parse_json(request.data)
            require(data['model'] == 'openai/gpt-oss-120b'
                    and data['max_completion_tokens'] == 1800
                    and data['reasoning_effort'] == 'low' and data['stream'] is False,
                    'unexpected_model_parameters')
            payload = parse_json(data['messages'][1]['content'])
            require(payload['question'] == QUESTION and payload['ticket_id'] == 'T-101'
                    and payload['context']['user.user_id'] == 'U-001'
                    and payload['context']['ticket.user_id'] == 'U-001'
                    and payload['context']['ticket.session_state'] == 'expired',
                    'unexpected_model_context')
            source_ids = [source['id'] for source in payload['sources']]
            require(source_ids == EXPECTED_SOURCES, 'unexpected_retrieval')
            require(len(receipt['mcp_calls']) == 2 and
                    all(event['completed'] for event in receipt['mcp_calls']),
                    'MCP_not_completed')
            receipt['model_input'] = {'question': QUESTION, 'ticket_id': 'T-101',
                                      'context': payload['context'],
                                      'sources': payload['sources'],
                                      'max_completion_tokens': 1800}
            receipt['http']['post_attempts'] = 1
            try:
                response = self.opener.open(request, timeout=timeout)
                receipt['http']['status'] = response.status
                return ObservedResponse(response)
            except urllib.error.HTTPError as error:
                receipt['http']['status'] = error.code
                error.close()
                raise

    def observed_build(*handlers):
        return ObservedOpener(real_build(*handlers))

    adapter = llm_adapter.GroqAdapter(approved=True)
    try:
        with patch.object(mcp_client, 'call', traced_call), patch.object(
                llm_adapter.urllib.request, 'build_opener', observed_build):
            result = answer({'ticket_id': 'T-101', 'question': QUESTION}, adapter)
        receipt['result'] = result
        require(receipt['http']['status'] == 200, 'unexpected_HTTP_status')
        receipt['status'] = 'passed'
    except SupportError as error:
        receipt['error'] = {'code': error.code}
    except Exception:
        receipt['error'] = {'code': 'acceptance_failed'}
    # No requests, retries or fallback after this point, including failed validation.
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approve-one-groq-post', action='store_true')
    args = parser.parse_args()
    try:
        require(args.approve_one_groq_post, 'explicit_approval_flag_required', 403)
        require(platform.system() == 'Darwin', 'Mac_required')
        offline = check_offline()
        # Reserve before credentials/network. An existing receipt blocks another run.
        fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except (SupportError, OSError, ValueError):
        print('STOP: preflight failed or result path already exists; no POST was performed.', file=sys.stderr)
        return 1
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        try:
            if not os.environ.get('GROQ_API_KEY'):
                require(sys.stdin.isatty(), 'interactive_terminal_required')
                os.environ['GROQ_API_KEY'] = getpass.getpass('Groq API key (hidden): ')
                require(bool(os.environ['GROQ_API_KEY']), 'missing_groq_key')
            receipt = execute_once()
        except (Exception, KeyboardInterrupt):
            receipt = {'status': 'failed', 'scope': 'one_real_Groq_E2E',
                       'error': {'code': 'setup_or_execution_interrupted'},
                       'instruction': 'STOP. Do not retry; check the existing receipt.'}
        receipt['offline_acceptance'] = offline
        receipt['runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        output.write(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({'status': receipt['status'], 'output': str(TARGET),
                      'http': receipt.get('http'), 'instruction': 'STOP. Do not rerun.'},
                     ensure_ascii=False, indent=2))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
