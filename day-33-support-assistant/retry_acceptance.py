"""Prepare, or run ONE separately authorized attempt-02 via curl. First receipt stays intact."""
import argparse
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch
import urllib.error

from common import ROOT, SupportError, parse_json, require
import llm_adapter
import live_acceptance as first
from mcp_client import fetch_context
from support_agent import prepare, validate_context

ATTEMPT_DIR = Path('/tmp/day33-live-attempt-02')
FIRST = Path('/tmp/day33-live-mac.json')
FIRST_SHA = '0030fa6c427986ee766704ee5542fb5356fe02e10749b7b4c7304ea439a99545'
FIRST_RUNNER_SHA = 'a36f19bb940edbe9210c28696b2cc7ef9c4e4f34b362af59ae82fee2cc2d10be'
MAX_INPUT_BOUND = 12000
SAFE_TOKEN = re.compile(r'[A-Za-z0-9_.:-]{1,128}')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    require(platform.system() == 'Darwin', 'Mac_required')
    offline = first.check_offline()
    require(digest(FIRST) == FIRST_SHA, 'first_receipt_changed')
    require(digest(ROOT / 'live_acceptance.py') == FIRST_RUNNER_SHA, 'first_runner_changed')
    require(shutil.which('curl') is not None, 'curl_missing')
    require(not ATTEMPT_DIR.exists(), 'attempt_02_already_reserved')
    key = os.environ.get('GROQ_API_KEY', '')
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key)), 'export_GROQ_API_KEY_required')
    return offline


def safe_token(value, secret):
    return value if isinstance(value, str) and SAFE_TOKEN.fullmatch(value) and secret not in value else None


def diagnostic(raw, header_text, secret):
    headers = {}
    for line in header_text.splitlines():
        if line.startswith('HTTP/'):
            headers = {}  # last response, not proxy CONNECT or interim headers
        elif ':' in line:
            name, value = line.split(':', 1)
            headers[name.lower().strip()] = value.strip()
    result = {'request_id': safe_token(headers.get('x-request-id'), secret),
              'cf_ray': safe_token(headers.get('cf-ray'), secret),
              'content_type': headers.get('content-type', '').split(';')[0]
                              if headers.get('content-type', '').split(';')[0] in
                              {'application/json','text/html','text/plain'} else None,
              'error_code': None, 'error_type': None, 'usage': None}
    try:
        envelope = parse_json(raw)
        if isinstance(envelope, dict):
            error = envelope.get('error')
            if isinstance(error, dict):
                result['error_code'] = safe_token(error.get('code'), secret)
                result['error_type'] = safe_token(error.get('type'), secret)
            usage = envelope.get('usage')
            if isinstance(usage, dict):
                result['usage'] = {k:v for k,v in usage.items() if k in
                    {'prompt_tokens','completion_tokens','total_tokens'} and type(v) is int and v >= 0}
    except Exception:
        match = re.search(rb'(?i)error code:\s*(10[0-9]{2})\b', raw)
        if match:
            result['error_code'] = match[1].decode('ascii')
    return result


class Response:
    def __init__(self, raw, status):
        self.raw, self.status = raw, status
    def read(self, limit):
        return self.raw[:limit]
    def close(self):
        pass


class CurlOpener:
    def __init__(self, execute=True):
        self.execute = execute
        self.calls = 0
        self.metrics = {'transport':'curl','curl_exit':None,'key_source':'environment:GROQ_API_KEY',
                        'request_id':None,'error_code':None,'error_type':None,'usage':None}

    def open(self, request, timeout):
        require(self.calls == 0, 'second_POST_blocked', 403)
        require(request.method == 'POST' and request.full_url ==
                'https://api.groq.com/openai/v1/chat/completions', 'unexpected_endpoint')
        body = parse_json(request.data)
        require(body['model'] == 'openai/gpt-oss-120b' and body['max_completion_tokens'] == 1800,
                'unexpected_model_or_limit')
        bound = len(request.data) + 1024  # conservative byte-BPE planning bound, not a tokenizer
        require(bound <= MAX_INPUT_BOUND, 'input_budget_exceeded')
        self.metrics.update(request_body_sha256=hashlib.sha256(request.data).hexdigest(),
                            request_body_bytes=len(request.data), input_token_planning_bound=bound,
                            completion_token_cap=1800,
                            estimated_list_cost_bound_usd=round((bound*.15+1800*.60)/1_000_000,8))
        if not self.execute:
            raise SupportError('preflight_only')
        key = os.environ.get('GROQ_API_KEY', '')
        require(re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key) is not None, 'invalid_key_format')
        require(request.get_header('Authorization') == 'Bearer '+key, 'authorization_mismatch')
        self.calls = 1
        with tempfile.TemporaryDirectory(prefix='day33-curl-') as temp:
            temp = Path(temp)
            payload, raw_path, header_path = temp/'body.json', temp/'response.bin', temp/'headers.txt'
            payload.write_bytes(request.data)
            env = {k:v for k,v in os.environ.items() if k != 'GROQ_API_KEY'}
            command = [shutil.which('curl'), '--disable', '--silent', '--show-error',
                       '--request','POST','--url',request.full_url,
                       '--proto','=https','--connect-timeout','15','--max-time','90',
                       '--retry','0','--max-redirs','0','--max-filesize','65536',
                       '--config','-','--data-binary','@'+str(payload),
                       '--output',str(raw_path),'--dump-header',str(header_path),
                       '--write-out','%{http_code}']
            # Credentials go only over stdin, never argv, disk or output.
            config = 'header = "Authorization: Bearer '+key+'"\nheader = "Content-Type: application/json"\n'
            try:
                process = subprocess.run(command, input=config, text=True, capture_output=True,
                                         timeout=100, env=env, check=False)
            except subprocess.TimeoutExpired:
                self.metrics['curl_exit'] = 'process_timeout'
                raise SupportError('curl_timeout_unknown_outcome',502) from None
            self.metrics['curl_exit'] = process.returncode
            raw = raw_path.read_bytes()[:65537] if raw_path.exists() else b''
            headers = header_path.read_text(errors='replace') if header_path.exists() else ''
            self.metrics.update(diagnostic(raw,headers,key))
            status = int(process.stdout.strip()) if re.fullmatch(r'[0-9]{3}',process.stdout.strip()) else 0
            self.metrics['status'] = status or None
            require(process.returncode == 0, 'curl_transport_failed_unknown_outcome',502)
            require(len(raw) <= 65536, 'response_too_large',502)
            if status != 200:
                raise urllib.error.HTTPError(request.full_url,status,'provider_http_error',{},io.BytesIO(b''))
            return Response(raw,status)


def preview_request():
    ticket,user = asyncio.run(fetch_context('T-101'))
    validate_context(ticket,user)
    payload = prepare(first.QUESTION,ticket,user)
    require([s['id'] for s in payload['sources']] == first.EXPECTED_SOURCES, 'unexpected_retrieval')
    opener = CurlOpener(execute=False)
    with patch.object(llm_adapter.urllib.request,'build_opener',return_value=opener):
        try:
            llm_adapter.GroqAdapter(approved=True).generate(payload)
        except SupportError as error:
            require(error.code == 'preflight_only', 'request_preparation_failed')
    return {'mode':'preflight_only','provider_posts':0,'ticket_id':'T-101','user_id':'U-001',
            'source_ids':[s['id'] for s in payload['sources']], **opener.metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true')
    group.add_argument('--approve-one-new-post',action='store_true')
    args = parser.parse_args()
    try:
        offline = preflight()
        if args.prepare:
            prepared = preview_request()  # real MCP, no provider call
            print(json.dumps(prepared,ensure_ascii=False,indent=2))
            return 0
        ATTEMPT_DIR.mkdir(mode=0o700,exist_ok=False)  # exclusive attempt-02 marker
    except Exception:
        print('STOP: preflight failed, key not exported, or attempt-02 already exists. No provider POST performed.')
        return 1
    target = ATTEMPT_DIR/'result.json'
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as output:
        # Persist uncertainty before starting. Crashes must never enable a retry.
        output.write('{"status":"interrupted_or_pending","instruction":"STOP. Do not rerun."}\n')
        output.flush()
        os.fsync(output.fileno())
        transport = CurlOpener()
        try:
            with patch.object(llm_adapter.urllib.request,'build_opener',return_value=transport):
                receipt = first.execute_once()
        except BaseException:
            receipt = {'status':'failed','error':{'code':'interrupted_unknown_outcome'}}
        receipt['http'].update(transport.metrics) if 'http' in receipt else None
        receipt.update(attempt_id='attempt-02',previous_attempt={'path':str(FIRST),'sha256':FIRST_SHA},
                       offline_acceptance=offline,runner_sha256=digest(Path(__file__)),
                       first_receipt_unchanged=digest(FIRST)==FIRST_SHA,
                       actual_billed_usd=None, instruction='STOP. Do not rerun.')
        output.seek(0)
        output.truncate()
        output.write(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({'status':receipt['status'],'output':str(target),'http':receipt.get('http'),
                      'instruction':'STOP. Do not rerun.'},ensure_ascii=False,indent=2))
    return 0 if receipt['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
