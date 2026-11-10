"""Local llama.cpp HTTP requests, exact tokenization, and response streaming."""
import json
import secrets
import threading
import urllib.error
import urllib.request

import httpx
from openai import OpenAI, OpenAIError
from qwen_agent.llm.base import ModelServiceError
from qwen_agent.llm.oai import TextChatAtOAI

import diagnostics


class API:
    def __init__(self, address):
        self.address = address
        self.closing = threading.Event()
        self.worker = None
        # Local traffic must not use an inherited HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, path, body=None):
        if self.closing.is_set():
            raise RuntimeError('Session is closing.')
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.address + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            return self.opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'HTTP {error.code}: {error.read().decode(errors="replace")}') from error

    def json(self, path, body=None):
        with self.open(path, body) as response:
            result = json.load(response)
        if 'error' in result:
            raise RuntimeError(str(result['error']))
        return result

    @staticmethod
    def body(messages):
        return {'messages': messages, 'chat_template_kwargs': {'enable_thinking': True}}

    def tokenize(self, prompt):
        return self.json('/tokenize', {'content': prompt, 'add_special': True,
                                       'parse_special': True})['tokens']

    def count(self, messages):
        prompt = self.json('/apply-template', self.body(messages))['prompt']
        return len(self.tokenize(prompt))

    def prepare(self, messages):
        # Render with a following user turn so the template treats the last reply
        # as history (Qwen formats its final assistant turn differently).
        marker = 'MARIONETTE_NEXT_INPUT_' + secrets.token_hex(16)
        prompt = self.json('/apply-template', self.body(messages +
                           [{'role': 'user', 'content': marker}]))['prompt']
        if prompt.count(marker) != 1:
            raise RuntimeError('Cannot locate next-message boundary in chat template.')
        prefix = prompt.split(marker)[0]
        tokens = self.tokenize(prefix)
        # Leave the boundary token for the real input in case tokenization merges it.
        result = self.json('/completion', {'prompt': tokens[:-1], 'n_predict': 0,
                                          'cache_prompt': True})
        diagnostics.log('Prepared cache timings: ' + json.dumps(result.get('timings', {})))

    def reply(self, messages, reserve, *, on_delta=None):
        # Qwen-Agent owns message conversion and streamed reasoning/answer assembly.
        # Marionette owns exact context fitting; disable the framework's rough trimming.
        model = TextChatAtOAI({'model': 'Qwen3.5-4B', 'model_server': self.address + '/v1',
            'api_key': 'EMPTY', 'generate_cfg': {'use_raw_api': True, 'max_input_tokens': 0,
                'max_retries': 0, 'seed': -1, 'max_tokens': reserve,
                'stream_options': {'include_usage': True},
                'extra_body': {'chat_template_kwargs': {'enable_thinking': True}}}})
        finish = None
        answer, reasoning = '', ''
        # The framework drops finish/usage metadata. Observe SDK chunks without
        # implementing another SSE parser, and reject incomplete generations.
        with OpenAI(base_url=self.address + '/v1', api_key='EMPTY', max_retries=0,
                    http_client=httpx.Client(trust_env=False, timeout=120)) as client:
            def create(**kwargs):
                nonlocal finish
                if self.closing.is_set():
                    raise RuntimeError('Session is closing.')
                with client.chat.completions.create(**kwargs) as response:
                    for chunk in response:
                        if self.closing.is_set():
                            raise RuntimeError('Session is closing.')
                        for choice in chunk.choices:
                            if choice.delta.tool_calls:
                                raise RuntimeError('Tools are not enabled in this integration.')
                            finish = choice.finish_reason or finish
                        if chunk.usage:
                            diagnostics.log('Runtime usage: ' + json.dumps(chunk.usage.model_dump()))
                        yield chunk
            # Adapter point in pinned Qwen-Agent 0.0.34; covered by HTTP-boundary tests.
            model._chat_complete_create = create
            try:
                for response in model.chat(messages=messages):
                    thought = ''.join(m.reasoning_content or '' for m in response)
                    text = ''.join(m.content or '' for m in response)
                    if on_delta is not None:
                        if thought[len(reasoning):]:
                            on_delta('reasoning', thought[len(reasoning):])
                        if text[len(answer):]:
                            on_delta('answer', text[len(answer):])
                    answer, reasoning = text, thought
            except (OpenAIError, ModelServiceError, httpx.HTTPError) as error:
                raise RuntimeError(f'Local model request failed: {error}') from error
        if finish not in ('stop', 'length'):
            raise RuntimeError('Response ended without a completion status; partial reply was not kept.')
        if reasoning:
            diagnostics.log('Reasoning: ' + json.dumps(reasoning, ensure_ascii=False))
        return answer, finish
