"""TEST ONLY: real capture_worker/model_worker/generate with synthetic transport."""
import argparse,json,socket,sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

def main():
    p=argparse.ArgumentParser();p.add_argument('--v103',required=True);p.add_argument('--frame',required=True)
    p.add_argument('--mode',required=True);p.add_argument('--raw-dir',required=True);p.add_argument('--log',required=True)
    a=p.parse_args();sys.path.insert(0,a.v103)
    from bublik_developer.generation import Qwen,MODEL
    import bublik_developer.model_worker as worker
    import capture_worker
    frame=json.loads(Path(a.frame).read_text())
    class Lease:
        def validate(self):pass
        def begin(self):pass
        def finish(self):pass
        def uncertain(self):pass
    class Session:
        def __init__(self,*args,**kwargs):pass
        @contextmanager
        def lease(self):yield Lease()
    def transport(endpoint,body):
        if endpoint=='/api/tags':return {'models':[{'name':MODEL,'digest':'a'*64}]}
        if endpoint=='/api/show':return {'details':{'family':'qwen2','parameter_size':'14.8B','quantization_level':'Q4_K_M'}}
        if endpoint=='/api/ps':return {'models':[]}
        if endpoint!='/api/chat':raise AssertionError('No other model operation allowed.')
        with Path(a.log).open('a') as f:f.write(json.dumps({'mode':a.mode,'synthetic':True})+'\n')
        return {'model':MODEL,'done':True,'done_reason':'stop','message':{'role':'assistant','content':json.dumps(frame,ensure_ascii=False)},'prompt_eval_count':42,'eval_count':17}
    original=Qwen.__init__
    def init(self,lease,**kwargs):original(self,lease,transport=transport)
    sys.argv=['capture_worker.py','--mode',a.mode,'--raw-dir',a.raw_dir]
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No real network in synthetic worker')),patch.object(worker,'ModelSession',Session),patch.object(Qwen,'__init__',init):
        return capture_worker.main()

if __name__=='__main__':raise SystemExit(main())
