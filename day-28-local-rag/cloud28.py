"""Optional OpenAI adapter, kept entirely within Day 28."""
from time import perf_counter

from bridge28 import HTTP, ProviderError
from providers import Generation, count


class OpenAIProvider:
    name = 'cloud'
    url = 'https://api.openai.com/v1'
    default_model = 'gpt-4.1-mini-2025-04-14'
    aliases = {'gpt-4.1-mini': default_model, 'gpt-4o-mini': 'gpt-4o-mini-2024-07-18'}
    models = frozenset(aliases.values())

    @classmethod
    def normalize_model(cls, model):
        resolved = cls.aliases.get(model, model)
        if resolved not in cls.models:
            raise ProviderError('Day 28 OpenAI supports gpt-4.1-mini or gpt-4o-mini and their pinned snapshots.')
        return resolved

    def __init__(self, api_key, model=default_model, timeout=180,
                 temperature=0, max_tokens=2048, http=None):
        if not api_key or not api_key.strip():
            raise ProviderError('OPENAI_API_KEY is missing. Set it in the environment or existing root .env.')
        self.model = self.normalize_model(model)
        self.api_key = api_key.strip()
        self.temperature, self.max_tokens = temperature, max_tokens
        self.http = http or HTTP(timeout)

    def request(self, endpoint, body=None):
        try:
            return self.http.request(self.url + endpoint, body,
                                     {'Authorization': f'Bearer {self.api_key}'})
        except ProviderError as error:
            # The shared Day 26 transport has a Groq-specific 401 hint.
            raise ProviderError(str(error).replace('Check GROQ_API_KEY.', 'Check OPENAI_API_KEY.')) from None

    def doctor(self):
        models = self.request('/models').get('data')
        if not isinstance(models, list):
            raise ProviderError('OpenAI returned an invalid model list.')
        if not any(isinstance(x, dict) and x.get('id') == self.model for x in models):
            raise ProviderError('Requested OpenAI snapshot is unavailable to this API project.')
        return {'provider': self.name, 'cloud_api': 'openai', 'model': self.model,
                'url': self.url, 'available': True,
                'note': 'Model access checked; billing and generation are verified separately.'}

    def generate(self, messages):
        start = perf_counter()
        response = self.request('/chat/completions', {
            'model': self.model, 'messages': messages, 'stream': False, 'store': False,
            'temperature': self.temperature, 'max_completion_tokens': self.max_tokens})
        elapsed = perf_counter() - start
        try:
            choice = response['choices'][0]
            message = choice['message']
            answer = message['content']
            reason = choice.get('finish_reason')
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError('OpenAI returned an invalid completion.') from None
        if message.get('refusal'):
            raise ProviderError('OpenAI returned a provider safety refusal, not a grounded RAG abstention.')
        if not isinstance(answer, str) or not answer.strip():
            raise ProviderError('OpenAI returned an empty answer.')
        if response.get('model') != self.model:
            raise ProviderError('OpenAI returned a different model snapshot than requested.')
        usage = response.get('usage')
        if usage is None:
            usage = {}
        if not isinstance(usage, dict):
            raise ProviderError('OpenAI returned invalid usage metadata.')
        return Generation(self.name, self.model, answer.strip(), elapsed,
                          count(usage.get('prompt_tokens')), count(usage.get('completion_tokens')),
                          reason, reason == 'stop')
