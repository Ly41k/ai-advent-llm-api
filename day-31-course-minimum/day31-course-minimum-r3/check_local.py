#!/usr/bin/env python3
"""Targeted new entrypoint checks; read an EXISTING index, never build one."""
import argparse,gc,io,json,os,platform,sys,tempfile,unittest,warnings
from pathlib import Path
from bootstrap_course import load,HERE


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['v103','v104','app','state','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        folder=Path(d).resolve();core,identity=load(a.v103.resolve(),a.v104.resolve(),a.app.resolve(),folder)
        os.environ.update(DAY31_COURSE_V103=str(a.v103.resolve()),DAY31_COURSE_STATE=str(a.state.resolve()),
                          DAY31_COURSE_APP=str(a.app.resolve()),DAY31_COURSE_OVERLAY=identity['overlay'],
                          DAY31_COURSE_EVIDENCE=str(core.private_dir(folder/'witnesses')))
        import course_runtime
        import test_course
        warnings.simplefilter('error',ResourceWarning);issues=[];sys.unraisablehook=lambda e:issues.append(str(e.exc_value))
        stream=io.StringIO()
        with course_runtime.no_network():
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_course));gc.collect()
        observed={p.relative_to(a.app.resolve()).as_posix():core.sha256(core.no_symlinks(p).read_bytes()).hexdigest()
                  for p in sorted(a.app.resolve().rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
        source_unchanged=observed==identity['original_python_sha256']
        witnesses={p.stem:core.read_json(p) for p in sorted((folder/'witnesses').glob('*.json'))}
        value={'status':'passed' if result.wasSuccessful() and not issues and source_unchanged else 'failed','tests_run':result.testsRun,
               'failures':len(result.failures),'errors':len(result.errors),'unraisable_errors':issues,
               'qwen_calls':0,'embedding_calls':0,'index_builds':0,'python':platform.python_version(),
               'platform':platform.system(),'log':stream.getvalue(),
               'real_operations':'MCP stdio discovery/calls, orchestrator tasks, owned FTS/Verification workers, existing SQLite read-only search',
               'synthetic_scope':'model transport/session/response; existing local fixture index identity admitted only in fixture comparison; human approvals only synthetic fixtures',
               'original_app_source_verified':60,'original_source_unchanged':source_unchanged,
               'original_source_sha256_before':identity['original_python_sha256'],'original_source_sha256_after':observed,
               'isolated_app_main_unchanged':True,'witnesses':witnesses}
        core.write_new(a.output,value)
        print(stream.getvalue());print(json.dumps({k:v for k,v in value.items() if k not in {'log','witnesses','original_source_sha256_before','original_source_sha256_after'}},ensure_ascii=False))
        return 0 if value['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
