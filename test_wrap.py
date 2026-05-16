import os
import sys
sys.path.append(os.path.abspath('hulku_ai_agent'))

from hulku_ai_agent.tools.wait import WaitTool
from agentscope_hulku_ai_agent.agentscope_hulku_ai_agent.tool_wrapper import create_toolkit

tk = create_toolkit([WaitTool()])
print(tk.get_json_schemas())
