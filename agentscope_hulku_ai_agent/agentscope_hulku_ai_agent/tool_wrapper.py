"""
Adapter layer: converts legacy BaseTool instances into AgentScope-compatible
tool functions registered in a Toolkit.

Key differences from the previous implementation:
  - Returns agentscope.tool._response.ToolResponse (with TextBlock content)
    instead of a plain dict, so AgentScope's tool-call lifecycle works correctly.
  - Passes the tool's JSON schema directly to register_tool_function(json_schema=...)
    instead of relying on fragile docstring/signature reconstruction.
  - Accepts an optional postprocess_func that is forwarded to register_tool_function,
    allowing the caller (agent_node) to publish ROS 2 feedback after every tool call.
"""

import json
import logging
from typing import Callable, Optional

from agentscope.tool import Toolkit
from agentscope.message import TextBlock
from agentscope.tool._response import ToolResponse

logger = logging.getLogger(__name__)


def _build_agentscope_json_schema(legacy_tool) -> dict:
    """
    Convert a BaseTool's parameter dict into the JSON schema format expected
    by AgentScope's register_tool_function:

      {
        "type": "function",
        "function": {
          "name": "...",
          "description": "...",
          "parameters": { <JSON Schema object> }
        }
      }
    """
    return {
        "type": "function",
        "function": {
            "name": legacy_tool.name,
            "description": legacy_tool.description,
            "parameters": legacy_tool.parameters,
        },
    }


def wrap_legacy_tool(legacy_tool_instance) -> Callable:
    """
    Wraps a legacy BaseTool into an async function that AgentScope can execute.
    The function returns a ToolResponse so the framework's streaming and
    post-processing hooks work correctly.
    """
    tool_name = legacy_tool_instance.name

    async def tool_func(**kwargs) -> ToolResponse:
        try:
            result = legacy_tool_instance.execute(**kwargs)
            if result.success:
                payload = {"status": "success", "message": result.message}
                if result.data:
                    payload["data"] = result.data
            else:
                payload = {"status": "error", "message": result.message}
        except Exception as exc:
            logger.error("Tool '%s' raised an exception: %s", tool_name, exc)
            payload = {"status": "error", "message": str(exc)}

        return ToolResponse(
            content=[TextBlock(type="text", text=json.dumps(payload, ensure_ascii=False))]
        )

    tool_func.__name__ = tool_name
    return tool_func


def create_toolkit(
    legacy_tools_list: list,
    postprocess_func: Optional[Callable] = None,
) -> Toolkit:
    """
    Build an AgentScope Toolkit from a list of legacy BaseTool instances.

    Args:
        legacy_tools_list: List of BaseTool subclass instances.
        postprocess_func:  Optional hook called after every tool execution.
                           Receives (ToolUseBlock, ToolResponse) and can return
                           a modified ToolResponse or None to keep the original.
                           Used to publish ROS 2 feedback from the agent node.
    """
    tk = Toolkit()
    for tool_instance in legacy_tools_list:
        func = wrap_legacy_tool(tool_instance)
        schema = _build_agentscope_json_schema(tool_instance)

        kwargs = dict(
            tool_func=func,
            json_schema=schema,
            postprocess_func=postprocess_func,
        )

        tk.register_tool_function(**kwargs)
        logger.info("Registered tool: %s", tool_instance.name)

    return tk
