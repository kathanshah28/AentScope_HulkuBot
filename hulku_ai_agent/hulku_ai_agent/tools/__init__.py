"""Tool registration. Import and register all tools here."""

from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult
from hulku_ai_agent.tools.registry import ToolRegistry
from hulku_ai_agent.tools.move_joints import MoveJointsTool
from hulku_ai_agent.tools.move_gripper import MoveGripperTool
from hulku_ai_agent.tools.buzzer import BuzzerTool
from hulku_ai_agent.tools.torque_mode import TorqueModeTool
from hulku_ai_agent.tools.get_joint_states import GetJointStatesTool
from hulku_ai_agent.tools.go_home import GoHomeTool
from hulku_ai_agent.tools.wait import WaitTool
from hulku_ai_agent.tools.print_message import PrintMessageTool
from hulku_ai_agent.tools.rgb_light import RGBLightTool

__all__ = [
    'BaseTool', 'ToolResult', 'ToolRegistry',
    'MoveJointsTool', 'MoveGripperTool', 'BuzzerTool',
    'TorqueModeTool', 'GetJointStatesTool', 'GoHomeTool',
    'WaitTool', 'PrintMessageTool', 'RGBLightTool',
]

