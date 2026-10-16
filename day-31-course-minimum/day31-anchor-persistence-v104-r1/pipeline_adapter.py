"""Opt-in v103 pipeline finalizer; normalized claims/model calls stay unchanged."""
from pathlib import Path
from bublik_developer.paired_research import SnapshotPipeline
from anchor_acceptance import attach, verify_envelope


class AnchorSnapshotPipeline(SnapshotPipeline):
    def __init__(self, *args, anchor_raw_dir, anchor_report_dir, anchor_contexts, anchor_result_version,
                 anchor_review=None, anchor_authorities=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.anchor_raw_dir = Path(anchor_raw_dir)
        self.anchor_report_dir = Path(anchor_report_dir)
        self.anchor_contexts = anchor_contexts
        self.anchor_result_version = anchor_result_version
        self.anchor_review = anchor_review
        self.anchor_authorities = anchor_authorities

    async def run(self, question, **kwargs):
        from runner import read_json,private_dir,write_new
        result = await super().run(question, **kwargs)
        # This adapter is deliberately limited to a v103 single model-response
        # documentation experiment. It does not silently generalize to Chain.
        if len(result['inference_tasks']) != 1:
            raise ValueError('anchor_adapter_requires_one_captured_model_task')
        task = result['inference_tasks'][0]
        witness = read_json(self.anchor_raw_dir/('raw-'+task['task_id']+'.json'))
        context = self.anchor_contexts[witness['context_digest']]
        output = attach(result, witness, context, self.anchor_result_version,
                        self.anchor_review, authorities=self.anchor_authorities)
        verify_envelope(output, self.anchor_review, authorities=self.anchor_authorities)
        directory = private_dir(self.anchor_report_dir)
        target = directory/('result-'+result['request_id']+'-'+output['anchor_binding']['binding_sha256']+'.json')
        # Keep original trace/raw files; publish a new final envelope exclusively.
        if target.exists():
            if read_json(target)!=output:raise ValueError('persisted_grounding_result_changed')
        else:
            write_new(target,output)
        return output
