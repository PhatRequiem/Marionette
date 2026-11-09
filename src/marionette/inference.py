"""Local llama.cpp HTTP requests, exact tokenization, and response streaming."""
import json
import secrets
import threading
import urllib.error
import urllib.request

import diagnostics
from log_store import chat_event


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
        body = self.body(messages) | {'stream': True, 'max_tokens': reserve,
                                      'stream_options': {'include_usage': True}}
        pieces, thoughts, finish = [], [], None
        completed = False
        try:
            with self.open('/v1/chat/completions', body) as response:
                for line in response:
                    if self.closing.is_set():
                        raise RuntimeError('Session is closing.')
                    if not line.startswith(b'data: '):
                        continue
                    payload = line[6:].strip()
                    if payload == b'[DONE]':
                        if finish is None:
                            raise RuntimeError('Response ended without a completion status.')
                        if thoughts:
                            diagnostics.log('Reasoning: ' + json.dumps(''.join(thoughts), ensure_ascii=False))
                        completed = True
                        return ''.join(pieces), finish
                    event = json.loads(payload)
                    if 'error' in event:
                        raise RuntimeError(str(event['error']))
                    for choice in event.get('choices', []):
                        delta = choice.get('delta', {})
                        reasoning = delta.get('reasoning_content') or ''
                        if reasoning:
                            if on_delta is not None:
                                on_delta('reasoning', reasoning)
                            thoughts.append(reasoning)
                        text = delta.get('content') or ''
                        if text:
                            if on_delta is not None:
                                on_delta('answer', text)
                            pieces.append(text)
                        finish = choice.get('finish_reason') or finish
                    if event.get('usage'):
                        diagnostics.log('Runtime usage: ' + json.dumps(event['usage']))
                        chat_event('usage', **event['usage'])
            raise RuntimeError('Response stream closed early; partial reply was not kept.')
        finally:
            if thoughts:
                chat_event('reasoning', content=''.join(thoughts), complete=completed)
            if pieces:
                chat_event('answer', role='assistant', content=''.join(pieces),
                           complete=completed, finish_reason=finish)
