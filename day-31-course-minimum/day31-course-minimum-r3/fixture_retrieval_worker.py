"""TEST ONLY: same FTS selector on existing local index with its actual UUID.

Only the expected index_version comparison is adapted to this fixture. Source
quotes, IDs, spans, ranking/selection and native index bytes remain unchanged.
Never used by entry.py preflight/live on the actual project.
"""
import argparse,sys
from copy import deepcopy
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--v103',required=True);p.add_argument('--index-version',required=True)
    a=p.parse_args();sys.path.insert(0,a.v103)
    import runner as core
    original=core.read_json
    def read(path):
        value=original(path)
        if Path(path).resolve()==(Path(a.v103)/'expected-selection.json').resolve():
            value=deepcopy(value)
            for entry in value.values():
                for source in entry['sources']:source['index_version']=a.index_version
        return value
    core.read_json=read
    import retrieval_worker
    return retrieval_worker.worker.main()

if __name__=='__main__':raise SystemExit(main())
