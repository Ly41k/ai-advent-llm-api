"""Minimal captured Single/Multi adapter at Pipeline's common return hook."""
from pathlib import Path
from bublik_developer.paired_research import SnapshotPipeline
from bublik_developer.pipeline import Pipeline
from bublik_developer.publication import publish_verified
from anchor_acceptance import attach,verify_envelope


class PublicationSnapshotPipeline(SnapshotPipeline):
    def __init__(self,*args,anchor_raw_dir,anchor_report_dir,anchor_contexts,
                 anchor_result_version,anchor_review=None,anchor_authorities=None,**kwargs):
        if not hasattr(Pipeline,'publication_result'):
            raise ValueError('publication_boundary_overlay_required_before_dispatch')
        super().__init__(*args,**kwargs)
        self.anchor_raw_dir=Path(anchor_raw_dir);self.anchor_report_dir=Path(anchor_report_dir)
        self.anchor_contexts=anchor_contexts;self.anchor_result_version=anchor_result_version
        self.anchor_review=anchor_review;self.anchor_authorities=anchor_authorities

    def publication_result(self,result):
        from runner import read_json,private_dir,write_new
        if len(result['inference_tasks'])!=1:
            raise ValueError('publication_adapter_requires_one_captured_model_task')
        task=result['inference_tasks'][0]
        witness=read_json(self.anchor_raw_dir/('raw-'+task['task_id']+'.json'))
        context=self.anchor_contexts[witness['context_digest']]
        output=attach(result,witness,context,self.anchor_result_version,
                      self.anchor_review,authorities=self.anchor_authorities)
        verify_envelope(output,self.anchor_review,authorities=self.anchor_authorities)
        # Compute the public projection before committing it. Any integration
        # error propagates; no original answer is returned as fallback.
        public=publish_verified(output,self.anchor_review,authorities=self.anchor_authorities)
        folder=private_dir(self.anchor_report_dir)
        stem='result-'+result['request_id']+'-'+output['anchor_binding']['binding_sha256']
        for name,value in [(stem+'-audit.json',output)]:
            target=folder/name
            if target.exists():
                if read_json(target)!=value:raise ValueError('persisted_publication_result_changed')
            else:write_new(target,value)
        return public

    async def run(self,question,**kwargs):
        from runner import read_json,private_dir,write_new
        public=await super().run(question,**kwargs)
        # Snapshot accounting is added after Pipeline's common hook; persist
        # exactly the public result returned to every consumer.
        folder=private_dir(self.anchor_report_dir)
        binding=public['publication']['result_binding_sha256']
        target=folder/('result-'+public['request_id']+'-'+binding+'-public.json')
        if target.exists():
            if read_json(target)!=public:raise ValueError('persisted_publication_result_changed')
        else:write_new(target,public)
        return public
