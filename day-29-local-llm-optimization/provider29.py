"""Local adapter retaining raw usage and sampling the actual Ollama processes."""
import math
from time import perf_counter
from bridge29 import OllamaProvider, ProviderError, model_matches, StructuredHTTP
from resources29 import ResourceSampler


class MeasuredOllama(OllamaProvider):
    def __init__(self, profile, url, timeout, seed=42, http=None, sample_interval=.5):
        super().__init__(profile['model'], url, timeout, profile['temperature'],
                         profile['max_tokens'], profile['num_ctx'],
                         http=http or StructuredHTTP(timeout, local=True))
        self.seed = seed
        self.last_raw = None
        self.last_resources = None
        self.sample_interval = sample_interval

    def running(self):
        models = self.http.request(self.url + '/api/ps').get('models')
        if not isinstance(models, list):
            raise ProviderError('Ollama returned an invalid running-model list.')
        return [{k: x.get(k) for k in ('name', 'model', 'digest', 'size', 'size_vram',
                                      'context_length', 'details')} for x in models if isinstance(x, dict)]

    def generate(self, messages):
        # The existing Day 26 parser remains authoritative. This interceptor adds
        # seed and preserves raw performance metadata without changing validation.
        original = self.http
        owner = self
        class Capture:
            def request(self, url, body=None, headers=None):
                if url.endswith('/api/chat') and body is not None:
                    body = dict(body)
                    body['options'] = {**body['options'], 'seed': owner.seed}
                response = original.request(url, body, headers)
                owner.last_raw = response
                return response
        self.last_raw = None
        with ResourceSampler(self.sample_interval) as sampler:
            self.http = Capture()
            try:
                return super().generate(messages)
            finally:
                self.http = original
                # Final sample is collected by __exit__; assign after unwinding below.
                self._sampler = sampler

    def resources(self):
        return self._sampler.result() if hasattr(self, '_sampler') else {'available': False}

    def unload(self):
        return self.http.request(self.url + '/api/generate',
                                 {'model': self.model, 'keep_alive': 0})

    def warmup(self):
        start = perf_counter()
        raw = self.http.request(self.url + '/api/generate', {
            'model': self.model, 'prompt': 'Reply OK.', 'stream': False, 'keep_alive': '5m',
            'options': {'temperature': 0, 'seed': self.seed, 'num_predict': 1, 'num_ctx': self.num_ctx}})
        if not model_matches(raw.get('model'), self.model):
            raise ProviderError('Warmup returned a different model.')
        return {'kind': 'warmup', 'model': self.model, 'wall_seconds': perf_counter() - start,
                'load_duration': raw.get('load_duration'), 'done_reason': raw.get('done_reason')}


def usage(raw):
    fields = ('total_duration', 'load_duration', 'prompt_eval_duration', 'eval_duration',
              'prompt_eval_count', 'prompt_eval_cached_count', 'eval_count', 'done_reason')
    result = {field: (raw or {}).get(field) for field in fields}
    for key in fields:
        value = result[key]
        if key != 'done_reason' and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            result[key] = None
    return result
