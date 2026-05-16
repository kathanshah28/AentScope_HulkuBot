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
    assert "Args:" in wrapped_func.__doc__
    assert "seconds (float):" in wrapped_func.__doc__

    # Test execution
    res = wrapped_func(seconds=1)
    assert res["status"] == "success"
    assert "waited for" in res["message"]

def test_create_toolkit():
    tool = WaitTool()
    tk = create_toolkit([tool])

    schemas = tk.get_json_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "wait"
    assert "seconds" in schemas[0]["function"]["parameters"]["properties"]
