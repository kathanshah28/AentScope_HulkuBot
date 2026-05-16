import pytest
import os
import sys

# Ensure imports can find the code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../hulku_ai_agent')))

from hulku_ai_agent.tools.wait import WaitTool
from agentscope_hulku_ai_agent.tool_wrapper import create_toolkit, wrap_legacy_tool

@pytest.mark.asyncio
async def test_wrap_legacy_tool():
    tool = WaitTool()
    wrapped_func = wrap_legacy_tool(tool)

    assert wrapped_func.__name__ == "wait"

    # Test execution
    res = await wrapped_func(seconds=1)

    import json

    if hasattr(res, 'content'):
        content_obj = res.content[0]
        content_text = content_obj.text if hasattr(content_obj, 'text') else content_obj['text']
    else:
        # Assuming res is the ToolResponse directly? Wait, the wrapper returns ToolResponse
        pass
    parsed_res = json.loads(content_text)

    assert parsed_res["status"] == "success"
    assert "waited for" in parsed_res["message"]

def test_create_toolkit():
    tool = WaitTool()
    tk = create_toolkit([tool])

    schemas = tk.get_json_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "wait"
    assert "seconds" in schemas[0]["function"]["parameters"]["properties"]
