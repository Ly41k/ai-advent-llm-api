#!/usr/bin/env python3
"""Targeted local tests only; all sockets blocked, no model calls."""
import argparse,gc,io,json,os,platform,socket,sys,unittest,warnings
from pathlib import Path
from unittest.mock import patch

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v103',type=Path,required=True)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    os.environ['DAY31_V103_PACKAGE']=str(args.v103.resolve());os.environ['DAY31_TEST_APP']=str(args.app.resolve())
    warnings.simplefilter('error',ResourceWarning);unraisable=[]
    sys.unraisablehook=lambda e:unraisable.append(str(e.exc_value))
    stream=io.StringIO()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden in offline tests')):
        suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_acceptance.py')
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        gc.collect()
    report={'status':'passed' if result.wasSuccessful() and not unraisable else 'failed',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'python':platform.python_version(),'platform':platform.system(),'qwen_calls':0,
            'network_connections_permitted':False,'unraisable_errors':unraisable,'log':stream.getvalue(),
            'scope':'Targeted native replay and synthetic review/finalization cases; no full regression, no live model.'}
    if args.output:
        with args.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    sys.stdout.write(stream.getvalue());print(json.dumps({k:v for k,v in report.items() if k!='log'},ensure_ascii=False))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
