"""Original owned model worker with an external private response recorder."""
import argparse,json,sys
from bublik_developer.model_worker import execute
from bublik_developer.generation import validate_context
from prompt_profile import CoverageQwen as Qwen,CoverageBaseline as BaselineQwen
from bublik_developer.baseline import validate_baseline_context
from bublik_developer.errors import DeveloperError,ErrorCode
from bublik_developer.contracts import canonical
from forensic_capture import capture_client


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['single','multi'],required=True)
    parser.add_argument('--raw-dir',required=True);args=parser.parse_args();payload=None
    try:
        raw=sys.stdin.buffer.read(32769)
        if len(raw)>32768:raise DeveloperError(ErrorCode.CONTEXT_BUDGET)
        payload=json.loads(raw)
        client=capture_client(BaselineQwen if args.mode=='single' else Qwen,args.mode,payload,args.raw_dir)
        reply=execute(payload,client_class=client,
            context_validator=validate_baseline_context if args.mode=='single' else validate_context)
    except DeveloperError as error:
        reply={'data':{},'error_code':error.code.value,'metrics':{'llm_calls':0}}
    except BaseException:
        # May follow actual dispatch/capture I/O. Preserve uncertainty, never retry.
        reply={'data':{},'error_code':ErrorCode.AGENT_FAILED.value,'metrics':{'llm_calls':None,'status':'unknown'}}
    if isinstance(payload,dict):
        for key in ['task_id','request_id']:
            if isinstance(payload.get(key),str):reply['metrics'][key]=payload[key]
    print(canonical(reply));return 0


if __name__=='__main__':raise SystemExit(main())
