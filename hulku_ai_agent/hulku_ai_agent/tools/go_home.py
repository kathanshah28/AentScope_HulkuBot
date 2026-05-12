"""Convenience tool to move all joints to the home position."""

from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class GoHomeTool(BaseTool):
    name = "go_home"
    description = "Move all robot joints to the home/default position (all zeros)."
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, move_joints_tool):
        self._move_joints = move_joints_tool

    def execute(self, **kwargs) -> ToolResult:
        home = [0, 0, 0, 0, 0]
        result = self._move_joints.execute(joint_angles=home)
        if result.success:
            return ToolResult(True, "Robot moved to home position (all joints at 0°).")
        return ToolResult(False, f"Failed to move home: {result.message}")
