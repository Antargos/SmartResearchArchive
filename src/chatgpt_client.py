"""Public Responses API with account-specific models and completed SSE results."""

import json

from .chatgpt_auth import ConnectionError, RESOURCE, refresh, request


def completed_text(response):
    """Never accept partial output, including a failure after some text arrived."""
    parts, data = [], []
    size = 0
    for raw in response:
        size += len(raw)
        if size > 2_000_000:
            raise ConnectionError('Model response exceeded the prototype output limit.')
        line = raw.decode('utf-8').rstrip('\r\n')
        if line.startswith('data:'):
            data.append(line[5:].lstrip())
        elif not line and data:
            try:
                event = json.loads('\n'.join(data))
            except ValueError:
                raise ConnectionError('Invalid model event; partial output discarded.') from None
            data = []
            kind = event.get('type')
            if kind == 'response.output_text.delta':
                parts.append(event['delta'])
            elif kind in ('error', 'response.failed', 'response.incomplete'):
                raise ConnectionError('Model request failed, was incomplete or reached a usage limit. '
                                      'Partial output discarded; check ChatGPT Settings > Usage.')
            elif kind == 'response.completed':
                if event.get('response', {}).get('status', 'completed') != 'completed':
                    raise ConnectionError('Model response did not complete.')
                return ''.join(parts)
    raise ConnectionError('Model stream ended early; partial output discarded.')


class ChatGPTClient:
    def __init__(self, profile, model, state=None):
        self.profile = profile
        self.model = model
        self.state = state

    @staticmethod
    def list_models(profile):
        result = request(RESOURCE + '/models', token=profile['access_token'])
        models = [item for item in result.get('models', []) if item.get('visibility') == 'list']
        if not models:
            raise ConnectionError('No models are available for this ChatGPT connection.')
        return models

    @staticmethod
    def choose_model(profile, requested=None, ask=input, show=print):
        models = ChatGPTClient.list_models(profile)
        if requested:
            if requested not in [item['slug'] for item in models]:
                raise ConnectionError('Requested model is not available to this account.')
            return requested
        for index, item in enumerate(models, 1):
            show(f'{index}. {item["display_name"]} ({item["slug"]})')
        while True:
            choice = ask('Choose model number: ').strip()
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                return models[int(choice) - 1]['slug']
            show('Choose an available model number.')

    def json_result(self, instructions, content):
        if self.state is not None:
            refresh(self.state, self.profile)
        # The plan-usage preview requires streamed, unstored requests. No API key,
        # backend-api route, tools, hidden retry, temperature or unsupported fields.
        response = request(RESOURCE + '/responses',
                           dict(model=self.model, instructions=instructions,
                                input=[{'role': 'user', 'content': content}],
                                store=False, stream=True), token=self.profile['access_token'], stream=True)
        with response:
            text = completed_text(response)
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError('object required')
            return value
        except ValueError:
            raise ConnectionError('Model did not return valid JSON. Nothing was moved; try again.') from None
