"""Local llama.cpp HTTP requests, exact tokenization, and response streaming."""
import json
import secrets
import threading
import urllib.error
import urllib.request

import diagnostics
from log_store import chat_event
from log_reader import TOOL


class API:
    def __init__(self, address, log_reader=None, capacity=None):
        self.address = address
        self.log_reader, self.capacity = log_reader, capacity
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

    def body(self, messages):
        body = {'messages': messages, 'chat_template_kwargs': {'enable_thinking': True}}
        if self.log_reader is not None:
            body['tools'] = [TOOL]
            body['parallel_tool_calls'] = False
        return body

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
        working = messages.copy()
        remaining = reserve
        while True:
            allowance = remaining
            if working != messages:
                prompt_tokens = self.count(working)
                allowance = min(allowance, self.capacity - prompt_tokens - 1)
                chat_event('context', prompt_tokens=prompt_tokens, context_capacity=self.capacity,
                           reply_allowance=max(0, allowance), phase='before_tool_continuation')
            if allowance <= 0:
                raise RuntimeError('Log review reached the context or generation allowance.')
            message, finish, used = self._stream(working, allowance, on_delta=on_delta)
            calls = message.get('tool_calls', [])
            if not calls:
                return message['content'], finish
            if self.log_reader is None or len(calls) != 1:
                raise RuntimeError('Log review requires one tool call at a time.')
            if used is None:
                # Conservatively count all generated fields if the server omitted usage.
                used = len(self.tokenize(json.dumps(message)))
            remaining -= used
            call = calls[0]
            if not call.get('id') or call.get('type') != 'function':
                raise RuntimeError('Invalid tool-call identity.')
            function = call['function']
            chat_event('tool_call', tool_call_id=call['id'], function=function)
            diagnostics.log('Log read requested: ' + json.dumps(function, ensure_ascii=False))
            if on_delta is not None:
                on_delta('tool', 'Reading active logs…')
            try:
                if function['name'] != 'read_logs':
                    raise ValueError('Only read_logs is available.')
                arguments = json.loads(function['arguments'])
                result = self.log_reader.read(arguments)
            except (ValueError, KeyError, TypeError) as error:
                result = {'error': str(error), 'untrusted_log_data': True}
            encoded = json.dumps(result, ensure_ascii=False)
            chat_event('tool_result', tool_call_id=call['id'], content=encoded)
            diagnostics.log('Log read completed: ' + json.dumps(
                {'records': len(result.get('records', [])), 'available': result.get('available'),
                 'error': result.get('error')}))
            working += [message, {'role': 'tool', 'tool_call_id': call['id'],
                                  'name': 'read_logs', 'content': encoded}]

    def _stream(self, messages, reserve, *, on_delta=None):
        body = self.body(messages) | {'stream': True, 'max_tokens': reserve,
                                      'stream_options': {'include_usage': True}}
        if self.log_reader is not None:
            body['tool_choice'] = 'auto'
        pieces, thoughts, finish = [], [], None
        calls, used = {}, None
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
                        message = {'role': 'assistant', 'content': ''.join(pieces)}
                        if calls:
                            if finish != 'tool_calls':
                                raise RuntimeError('Incomplete tool call; no log read was executed.')
                            message['tool_calls'] = [calls[i] for i in sorted(calls)]
                            message['reasoning_content'] = ''.join(thoughts)
                        elif finish == 'tool_calls':
                            raise RuntimeError('Missing tool-call data.')
                        if '<tool_call>' in message['content']:
                            completed = False
                            raise RuntimeError('Model returned unparsed tool syntax; no final answer was accepted.')
                        return message, finish, used
                    event = json.loads(payload)
                    if 'error' in event:
                        raise RuntimeError(str(event['error']))
                    for choice in event.get('choices', []):
                        delta = choice.get('delta', {})
                        for fragment in delta.get('tool_calls', []):
                            index = fragment.get('index', 0)
                            if type(index) is not int or not 0 <= index < 4:
                                raise RuntimeError('Invalid tool-call index.')
                            call = calls.setdefault(index, {'id': '', 'type': 'function',
                                                           'function': {'name': '', 'arguments': ''}})
                            if fragment.get('id'):
                                call['id'] += fragment['id']
                            for key in ('name', 'arguments'):
                                call['function'][key] += fragment.get('function', {}).get(key, '')
                            if len(call['function']['arguments']) > 4096:
                                raise RuntimeError('Tool arguments exceed the allowed size.')
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
                        chat_event('usage', generation_kind='tool_call' if calls else 'answer', **event['usage'])
                        used = event['usage'].get('completion_tokens')
            raise RuntimeError('Response stream closed early; partial reply was not kept.')
        finally:
            if thoughts:
                chat_event('reasoning', content=''.join(thoughts), complete=completed)
            if pieces:
                chat_event('assistant_note' if calls else 'answer', role='assistant', content=''.join(pieces),
                           complete=completed, finish_reason=finish)
