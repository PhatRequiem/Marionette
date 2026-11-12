"""Qwen-Agent tool loop with only explicitly supplied local tool objects."""
import json

from qwen_agent import Agent
from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.tools import BaseTool

import diagnostics


class Coordinator(FnCallAgent):
    def __init__(self, model, tools, closing, *, check=None):
        self.closing = closing
        self.check = check
        self.request_number = 0
        self.tool_number = 0
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
        if self.check is not None:
            from thinking import TOOL_CALLS
            self.check()
            if self.tool_number >= TOOL_CALLS:
                raise RuntimeError("Thinking step reached its tool-call limit.")
        self.tool_number += 1
        with diagnostics.operation_scope('TOOL CALL', self.tool_number,
                                         request=self.request_number or None):
            diagnostics.log('Tool call identity: ' + json.dumps({
                'name': tool_name, 'protocol_tool_call_id': self.protocol_tool_id}, ensure_ascii=True))
            if self.closing.is_set():
                raise RuntimeError('Session is closing.')
            if tool_name not in self.function_map:
                raise RuntimeError(f'Tool is not enabled: {tool_name}')
            diagnostics.log(f'Tool started: {tool_name}.')
            result = Agent._call_tool(self, tool_name, tool_args, **kwargs)
            # The framework can return an error as text. "Returned" describes
            # execution flow, not whether a tool's domain operation succeeded.
            diagnostics.log(f'Tool returned: {tool_name}.')
            return result
