"""Local llama.cpp HTTP requests, exact tokenization, and response streaming."""
import json
from pathlib import Path
import secrets
import threading
import urllib.error
import urllib.request

import httpx
from openai import OpenAI, OpenAIError
from qwen_agent.llm.base import ModelServiceError
from qwen_agent.llm.oai import TextChatAtOAI
from qwen_agent.llm.schema import Message
from qwen_agent.tools.base import ToolServiceError

from coordination import Coordinator

import diagnostics


class API:
    def __init__(self, address, *, tools=()):
        self.address = address
        self.closing = threading.Event()
        self.cancelled = threading.Event()
        self.active_response = None
        self.worker = None
        self.capacity = 65536
        self.tools = tuple(tools)
        self.system_prompt = None
        self.feature_prompts = {}
        self.response_messages = None
        # Local traffic must not use an inherited HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def cancel_reply(self):
        self.cancelled.set()
        response = self.active_response
        if response is not None:
            try:
                response.close()
            except (OSError, RuntimeError):
                pass  # Cancellation flag still stops the next stream/tool boundary.

    def is_set(self):
        # Coordinator checks this before executing each tool.
        return self.closing.is_set() or self.cancelled.is_set()

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

    def feature_prompt(self, filename):
        """Load and validate application guidance once per API instance."""
        if filename not in self.feature_prompts:
            path = Path(__file__).resolve().parents[2] / 'prompts' / filename
            prompt = path.read_text(encoding='utf-8').strip()
            if not prompt:
                raise ValueError(f'Tool guidance prompt is empty: {filename}')
            self.feature_prompts[filename] = prompt
        return self.feature_prompts[filename]

    def with_system(self, messages):
        # A rendered system message is already present on tool follow-up requests.
        if messages and messages[0]["role"] == "system":
            return messages
        parts = []
        guidance = {'read_vault': 'vault.md', 'query_logs': 'log-queries.md',
                    'update_contact_notes': 'contact-notes.md', 'update_soul': 'soul.md'}
        enabled = {tool.name for tool in self.tools}
        files = [filename for name, filename in guidance.items() if name in enabled]
        if files:
            files.insert(0, 'tool-guidance.md')
        parts.extend(self.feature_prompt(filename) for filename in files)
        if self.system_prompt:
            parts.append(self.system_prompt)
        if parts:
            return [{"role": "system", "content": '\n\n'.join(parts)}] + messages
        return messages

    def body(self, messages):
        messages = self.with_system(messages)
        body = {'messages': self.wire_messages(messages), 'chat_template_kwargs': {'enable_thinking': True}}
        if self.tools:
            body['tools'] = [{'type': 'function', 'function': tool.function} for tool in self.tools]
        return body

    @staticmethod
    def wire_messages(messages):
        # Keep Qwen-Agent's native history internally, using its pinned converter
        # for both token counting/preparation and the actual model request.
        if any(m['role'] == 'function' or m.get('function_call') for m in messages):
            messages = TextChatAtOAI._conv_qwen_agent_messages_to_oai(messages)
        return [dict(role='tool', content=m['content'],
                     tool_call_id=m.get('tool_call_id', m.get('id')))
                if m['role'] == 'tool' else m for m in messages]

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
        self.active_response = None
        self.response_messages = None
        messages = self.with_system(messages)
        # Qwen-Agent owns message conversion and streamed reasoning/answer assembly.
        # Marionette owns exact context fitting; disable the framework's rough trimming.
        model = TextChatAtOAI({'model': 'Qwen3.5-4B', 'model_server': self.address + '/v1',
            'api_key': 'EMPTY', 'generate_cfg': {'use_raw_api': True, 'max_input_tokens': 0,
                'max_retries': 0, 'seed': -1, 'max_tokens': reserve,
                'stream_options': {'include_usage': True},
                'extra_body': {'chat_template_kwargs': {'enable_thinking': True}}}})
        coordinator = Coordinator(model, self.tools, self)
        finish = None
        answer, reasoning = '', ''
        # The framework drops finish/usage metadata. Observe SDK chunks without
        # implementing another SSE parser, and reject incomplete generations.
        with OpenAI(base_url=self.address + '/v1', api_key='EMPTY', max_retries=0,
                    http_client=httpx.Client(trust_env=False, timeout=120)) as client:
            def create(**kwargs):
                coordinator.request_number += 1
                with diagnostics.operation_scope('MODEL REQUEST', coordinator.request_number):
                    yield from create_request(**kwargs)

            def create_request(**kwargs):
                nonlocal finish
                if self.is_set():
                    raise RuntimeError('Session is closing.')
                finish = None
                requested_tool = False
                # Qwen-Agent 0.0.34 emits legacy tool `id`/`extra` fields.
                # Normalize its tool results to the OpenAI-compatible wire schema.
                kwargs['messages'] = self.wire_messages(kwargs['messages'])
                if coordinator.log_result_received or coordinator.vault_result_received:
                    # Qwen requires one initial system message. Amend a copy for
                    # this follow-up only; keep instructions out of tool data/history.
                    system = dict(kwargs['messages'][0])
                    if coordinator.log_result_received:
                        system['content'] += '\n\n' + self.feature_prompt('log-results.md')
                    if coordinator.vault_result_received:
                        system['content'] += '\n\n' + self.feature_prompt('vault-results.md')
                    kwargs['messages'] = [system, *kwargs['messages'][1:]]
                if self.tools:
                    tokens = self.count(kwargs['messages'])
                    if tokens + reserve >= self.capacity:
                        raise ValueError('Tool request exceeds context budget; history is unchanged.')
                    diagnostics.log(f'Tool-loop prompt budget: {tokens} tokens + {reserve} reply allowance < {self.capacity}.')
                with client.chat.completions.create(**kwargs) as response:
                    self.active_response = response
                    for chunk in response:
                        if self.is_set():
                            raise RuntimeError('Session is closing.')
                        for choice in chunk.choices:
                            requested_tool = requested_tool or bool(choice.delta.tool_calls)
                            if choice.delta.tool_calls and not self.tools:
                                raise RuntimeError('Tools are not enabled in this integration.')
                            finish = choice.finish_reason or finish
                        if chunk.usage:
                            diagnostics.log('Runtime usage: ' + json.dumps(chunk.usage.model_dump()))
                        yield chunk
                # Reject interrupted/truncated tool requests before the agent executes them.
                if finish not in ('stop', 'length', 'tool_calls') or (requested_tool and finish != 'tool_calls'):
                    raise RuntimeError('Response ended without a completion status; partial reply was not kept.')
                diagnostics.log(f'Model request finished: finish_reason={finish}.')
            # Adapter point in pinned Qwen-Agent 0.0.34; covered by HTTP-boundary tests.
            model._chat_complete_create = create
            try:
                for response in coordinator.run(messages=[Message(**m) for m in messages]):
                    thought = ''.join(m.reasoning_content or '' for m in response)
                    last_tool = max((i for i, m in enumerate(response) if m.role == 'function'), default=-1)
                    text = ''.join(m.content or '' for m in response[last_tool + 1:]
                                   if m.role == 'assistant' and not m.function_call)
                    if thought[len(reasoning):]:
                        diagnostics.log('Reasoning delta: ' + json.dumps(thought[len(reasoning):], ensure_ascii=False))
                    if on_delta is not None:
                        if thought[len(reasoning):]:
                            on_delta('reasoning', thought[len(reasoning):])
                        if not self.tools and text[len(answer):]:
                            on_delta('answer', text[len(answer):])
                    answer, reasoning = text, thought
            except (OpenAIError, ModelServiceError, ToolServiceError, httpx.HTTPError) as error:
                raise RuntimeError(f'Local model/tool request failed: {error}') from error
        self.active_response = None
        if self.cancelled.is_set():
            raise RuntimeError('Generation cancelled.')
        if finish not in ('stop', 'length') or any(m.function_call for m in response[last_tool + 1:]):
            raise RuntimeError('Response ended without a completion status; partial reply was not kept.')
        if reasoning:
            diagnostics.log('Reasoning: ' + json.dumps(reasoning, ensure_ascii=False))
        if self.tools and answer and on_delta is not None:
            on_delta('answer', answer)
        # Commit only a complete successful response. Past reasoning remains in
        # diagnostics, not replayed context; calls, IDs and tool results survive.
        self.response_messages = []
        for message in response:
            item = message.model_dump(exclude={'reasoning_content'})
            if item.get('extra') == {}:
                item.pop('extra')
            if item.get('content') or item.get('function_call') or item['role'] == 'function':
                self.response_messages.append(item)
        return answer, finish
