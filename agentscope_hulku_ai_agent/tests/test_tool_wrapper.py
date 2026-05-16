import pytest
import os
import sys

# Ensure imports can find the code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../hulku_ai_agent')))

from hulku_ai_agent.tools.wait import WaitTool
from agentscope_hulku_ai_agent.tool_wrapper import create_toolkit, wrap_legacy_tool

def test_wrap_legacy_tool():
    tool = WaitTool()
    wrapped_func = wrap_legacy_tool(tool)

    assert wrapped_func.__name__ == "wait"
    # AgentScope Toolkit no longer relies on docstrings here, skip docstring tests

    import asyncio
    # Test execution
    res = asyncio.run(wrapped_func(seconds=1))
    import json

    # TextBlock might be dict if accessed directly from ToolResponse content depending on agentscope version
    if hasattr(res.content[0], 'text'):
        res_dict = json.loads(res.content[0].text)
    else:
        res_dict = json.loads(res.content[0]["text"])

    assert res_dict["status"] == "success"
    assert "waited for" in res_dict["message"]

def test_create_toolkit():
    tool = WaitTool()
    tk = create_toolkit([tool])

    schemas = tk.get_json_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "wait"
    assert "seconds" in schemas[0]["function"]["parameters"]["properties"]
