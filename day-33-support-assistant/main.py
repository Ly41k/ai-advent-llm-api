"""Local HTTP / CLI. HTTP is always offline; live is an explicit one-shot CLI."""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from common import MAX_BODY, SupportError, parse_json, require
from llm_adapter import GroqAdapter, OfflineAdapter
from support_agent import answer, prepare
from mcp_client import fetch_context
from support_agent import validate_context
import asyncio


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def send_json(self,status,value):
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def local_request(self):
        port=self.server.server_port
        require(self.headers.get_all('Host',[]) in ([f'127.0.0.1:{port}'],[f'localhost:{port}']), 'invalid_host',403)
        origins=self.headers.get_all('Origin',[])
        require(not origins or origins in ([f'http://127.0.0.1:{port}'],[f'http://localhost:{port}']), 'invalid_origin',403)

    def do_GET(self):
        try:
            self.local_request()
            require(self.path=='/health','not_found',404)
            self.send_json(200,{'status':'alive','mode':'offline_mock','scope':'process_liveness_only'})
        except SupportError as e:
            self.send_json(e.status,{'error':{'code':e.code}})

    def do_POST(self):
        try:
            self.local_request()
            require(self.path=='/support/answer','not_found',404)
            require(not self.headers.get_all('Transfer-Encoding'),'invalid_request',400)
            require(self.headers.get('Content-Type','').split(';')[0].strip()=='application/json','unsupported_media_type',415)
            lengths=self.headers.get_all('Content-Length',[])
            require(len(lengths)==1 and lengths[0].isdigit(),'invalid_content_length',400)
            length=int(lengths[0])
            require(0<length<=MAX_BODY,'request_too_large',413)
            request=parse_json(self.rfile.read(length))
            self.send_json(200,answer(request,OfflineAdapter()))
        except SupportError as e:
            self.send_json(e.status,{'error':{'code':e.code}})
        except Exception:
            self.send_json(500,{'error':{'code':'internal_error'}})


def server(port=8033):
    return HTTPServer(('127.0.0.1',port),Handler)


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('answer','prepare','live'):
        part=sub.add_parser(name)
        part.add_argument('--ticket',default=None)
        part.add_argument('--question',required=True)
        part.add_argument('--output',type=Path)
        if name=='live':
            part.add_argument('--approve-one-groq-post',action='store_true')
    serve=sub.add_parser('serve')
    serve.add_argument('--port',type=int,default=8033)
    return p


def main():
    args=parser().parse_args()
    output=None
    adapter=None
    try:
        if args.command=='serve':
            require(1024 <= args.port <= 65535)
            with server(args.port) as httpd:
                print(f'Offline mock HTTP: http://127.0.0.1:{args.port}',file=sys.stderr)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    pass
            return 0
        request={'question':args.question,'ticket_id':args.ticket}
        from common import validate_request
        validate_request(request)
        if args.command=='live':
            require(args.approve_one_groq_post,'live_not_approved',403)
            require(args.output is not None,'live_output_required')
            adapter=GroqAdapter(approved=True)
        else:
            adapter=OfflineAdapter()
        # Reserve the result path before any generation. Never overwrite evidence.
        if args.output:
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            output=os.fdopen(fd,'w',encoding='utf-8')
        if args.command=='prepare':
            ticket=user=None
            if args.ticket:
                ticket,user=asyncio.run(fetch_context(args.ticket))
                validate_context(ticket,user)
            result={'mode':'preflight_only','generation_calls':0,'payload':prepare(args.question,ticket,user)}
        else:
            result=answer(request,adapter)
        code=0
    except SupportError as e:
        result={'error':{'code':e.code},'generation_attempted':bool(getattr(adapter,'used',False))}
        if getattr(adapter,'last_meta',None):
            result['llm']=adapter.last_meta
        code=1
    except (OSError,ValueError):
        result={'error':{'code':'local_io_or_configuration_error'},'generation_attempted':bool(getattr(adapter,'used',False))}
        code=1
    except Exception:
        result={'error':{'code':'internal_error'},'generation_attempted':bool(getattr(adapter,'used',False))}
        code=1
    raw=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if output:
        with output:
            output.write(raw)
    sys.stdout.write(raw)
    return code


if __name__=='__main__':
    raise SystemExit(main())
