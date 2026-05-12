"""Read current joint positions from the /joint_states topic."""

import math
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class GetJointStatesTool(BaseTool):
    name = "get_joint_states"
    description = (
        "Read the current position of all robot joints in degrees. "
        "Use this to check where the robot is before planning a move."
    )
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, node, joint_names):
        self._node = node
        self._joint_names = joint_names

    def execute(self, **kwargs) -> ToolResult:
        state = self._node.current_joint_state
        if state is None:
            return ToolResult(False, "Joint state not received yet. Is the robot running?")

        js_map = dict(zip(state.name, state.position))

        angles = {}
        for name in self._joint_names:
            rad = js_map.get(name, 0.0)
            angles[name] = round(math.degrees(rad), 1)

        return ToolResult(
            True,
            f"Current joint positions (degrees): {angles}",
            data={"joint_angles": angles}
        )
