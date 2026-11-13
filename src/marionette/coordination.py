"""Qwen-Agent tool loop with only explicitly supplied local tool objects."""
import json

from qwen_agent import Agent
from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.tools import BaseTool

import diagnostics


def tool_action(name, arguments):
    """Only expose known operation labels, never argument contents."""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except (ValueError, TypeError):
        return None
    if not isinstance(args, dict):
        return None
    key, allowed = {
        'read_vault': ('action', ('list', 'search', 'read', 'inspect', 'tags', 'links', 'open')),
        'query_logs': ('lookup', ('setup', 'status', 'processing', 'delivery', 'errors')),
        'update_contact_notes': ('action', ('add', 'patch', 'remove')),
    }.get(name, ('', ()))
    value = args.get(key)
    return value if isinstance(value, str) and value in allowed else None


def tool_outcome(name, result):
    """Summarize explicit tool contracts; an arbitrary return is not success."""
    if isinstance(result, str) and result.startswith(f'An error occurred when calling tool `{name}`:\n'):
        return 'Failed'
    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (ValueError, TypeError):
        return 'Returned (unverified)'
    if isinstance(data, dict):
        if name in ('update_soul', 'update_contact_notes'):
            if data.get('success') is True:
                return 'Success'
            if data.get('success') is False:
                return 'Failed'
        elif name in ('query_logs', 'read_vault'):
            status = data.get('status')
            if isinstance(status, str):
                return {'ok': 'Success', 'partial': 'Partial', 'unavailable': 'Unavailable',
                        'no_matches': 'No matches', 'error': 'Failed'}.get(status, 'Returned (unverified)')
    return 'Returned (unverified)'


class Coordinator(FnCallAgent):
    def __init__(self, model, tools, closing):
        self.closing = closing
        self.request_number = 0
        self.tool_number = 0
        self.log_result_received = False
        self.protocol_tool_id = None
        # Use the public base initializer: FnCallAgent's initializer also creates
        # document retrieval/parser tools. We need its loop, not its file memory.
        if any(not isinstance(tool, BaseTool) or tool.file_access for tool in tools):
            raise ValueError('Only explicit tool objects without automatic file attachments are supported.')
        if any(not isinstance(tool.parameters, dict) for tool in tools):
            raise ValueError('Native API tools require JSON Schema object parameters.')
        if len({tool.name for tool in tools}) != len(tools):
            raise ValueError('Tool names must be unique.')
        Agent.__init__(self, function_list=list(tools), llm=model, system_message='')

    def _detect_tool(self, message):
        result = super()._detect_tool(message)
        # The pinned loop preserves this ID on the function result but does not
        # pass it to _call_tool. Capture it from the exact detected call.
        self.protocol_tool_id = message.extra.get('function_id', '1') if result[0] else None
        return result

    def _call_tool(self, tool_name, tool_args='{}', **kwargs):
        self.tool_number += 1
        with diagnostics.operation_scope('TOOL CALL', self.tool_number,
                                         request=self.request_number or None):
            diagnostics.log('Tool call identity: ' + json.dumps({
                'name': tool_name, 'protocol_tool_call_id': self.protocol_tool_id}, ensure_ascii=True))
            summary = {'name': tool_name, 'protocol_tool_call_id': self.protocol_tool_id,
                       'request': self.request_number or None, 'tool': self.tool_number}
            action = tool_action(tool_name, tool_args)
            if action:
                summary['action'] = action
            diagnostics.log('Tool summary: ' + json.dumps(summary, ensure_ascii=True))
            try:
                if self.closing.is_set():
                    raise RuntimeError('Session is closing.')
                if tool_name not in self.function_map:
                    raise RuntimeError(f'Tool is not enabled: {tool_name}')
                diagnostics.log(f'Tool started: {tool_name}.')
                result = Agent._call_tool(self, tool_name, tool_args, **kwargs)
            except Exception:
                diagnostics.log('Tool result summary: ' + json.dumps({**summary, 'outcome': 'Failed'}, ensure_ascii=True))
                raise
            diagnostics.log('Tool result summary: ' + json.dumps(
                {**summary, 'outcome': tool_outcome(tool_name, result)}, ensure_ascii=True))
            # The framework can return an error as text. "Returned" describes
            # execution flow, not whether a tool's domain operation succeeded.
            if tool_name == 'query_logs':
                self.log_result_received = True
            diagnostics.log(f'Tool returned: {tool_name}.')
            return result
