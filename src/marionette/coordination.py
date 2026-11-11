"""Qwen-Agent tool loop with only explicitly supplied local tool objects."""
from qwen_agent import Agent
from qwen_agent.agents.fncall_agent import FnCallAgent
from qwen_agent.tools import BaseTool

import diagnostics


class Coordinator(FnCallAgent):
    def __init__(self, model, tools, closing):
        self.closing = closing
        # Use the public base initializer: FnCallAgent's initializer also creates
        # document retrieval/parser tools. We need its loop, not its file memory.
        if any(not isinstance(tool, BaseTool) or tool.file_access for tool in tools):
            raise ValueError('Only explicit tool objects without automatic file attachments are supported.')
        if any(not isinstance(tool.parameters, dict) for tool in tools):
            raise ValueError('Native API tools require JSON Schema object parameters.')
        if len({tool.name for tool in tools}) != len(tools):
            raise ValueError('Tool names must be unique.')
        Agent.__init__(self, function_list=list(tools), llm=model, system_message='')

    def _call_tool(self, tool_name, tool_args='{}', **kwargs):
        if self.closing.is_set():
            raise RuntimeError('Session is closing.')
        if tool_name not in self.function_map:
            raise RuntimeError(f'Tool is not enabled: {tool_name}')
        diagnostics.log(f'Tool started: {tool_name}.')
        result = Agent._call_tool(self, tool_name, tool_args, **kwargs)
        diagnostics.log(f'Tool completed: {tool_name}.')
        return result
