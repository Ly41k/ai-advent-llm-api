"""Run offline acceptance and save one exclusive JSON receipt for Mac review."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import unittest

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    # Reserve first: never run the checks only to discover an existing report.
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as output:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        import test_support
        cases=test_support.Acceptance
        examples={name:getattr(cases,attr,None) for name,attr in [('A_auth','a'),('B_phone','b'),('C_401_unknown','c'),('C_no_documentation','unknown')]}
        source_files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.txt','.md'} and p.name!='offline-linux.json']
        report={'status':'passed' if result.wasSuccessful() else 'failed',
                'scope':'offline_only_real_MCP_stdio_and_mock_LLM',
                'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                'skipped':len(result.skipped),'real_generation_calls':0,'real_provider_http_posts':0,
                'environment':{'platform':platform.platform(),'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,'mcp':importlib.metadata.version('mcp')},
                'base_sha':'c654e24610bdabed15747088f9e1691ed36d0b17',
                'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
                'examples':examples,
                'failures_detail':[{'test':str(test),'traceback':trace} for test,trace in result.failures+result.errors],
                'acceptance_pending':['Mac offline results','one separately approved real LLM E2E','human review of real answer','publication and video']}
        output.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','tests_run','failures','errors','real_generation_calls')},ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
