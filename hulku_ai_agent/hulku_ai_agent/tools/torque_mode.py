"""Toggle torque (Drag & Teach mode) via gpio_controller topic."""

from std_msgs.msg import Float64MultiArray
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class TorqueModeTool(BaseTool):
    name = "torque_mode"
    description = (
        "Enable or disable motor torque (Drag & Teach mode). "
        "When torque is OFF (enabled=false), the robot can be freely moved by hand. "
        "When torque is ON (enabled=true), the motors hold their position."
    )
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "true to enable torque (hold position), false to disable (allow free movement).",
            }
        },
        "required": ["enabled"],
    }

    def __init__(self, node, gpio_pub, gpio_state):
        self._node = node
        self._pub = gpio_pub
        self._state = gpio_state  # shared list [buzzer, torque, r, g, b]

    def execute(self, enabled: bool = True, **kwargs) -> ToolResult:
        self._state[1] = 1.0 if enabled else 0.0
        msg = Float64MultiArray()
        msg.data = [float(v) for v in self._state]
        self._pub.publish(msg)

        return ToolResult(True, "Torque ON (Hold mode)" if enabled else "Torque OFF (Drag mode)")
