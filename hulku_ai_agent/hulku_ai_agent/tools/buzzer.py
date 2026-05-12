"""Toggle the robot buzzer via gpio_controller topic."""

import time
from std_msgs.msg import Float64MultiArray
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class BuzzerTool(BaseTool):
    name = "buzzer"
    description = "Turn the robot's buzzer ON or OFF, or beep for a duration (0.1s increments, max 5s)."
    parameters = {
        "type": "object",
        "properties": {
            "state": {
                "type": "boolean",
                "description": "true to turn buzzer ON, false to turn OFF.",
            },
            "duration": {
                "type": "number",
                "description": "Optional beep duration in seconds (0.1-5.0). If provided, buzzer beeps for this duration then stops.",
            }
        },
        "required": ["state"],
    }

    def __init__(self, node, gpio_pub, gpio_state):
        self._node = node
        self._pub = gpio_pub
        self._state = gpio_state  # shared list [buzzer, torque, r, g, b]

    def execute(self, state: bool = False, duration: float = 0.0, **kwargs) -> ToolResult:
        if duration and duration > 0:
            # MCU: value 1-50 = beep for 0.1s * value
            val = min(50, max(1, int(duration * 10)))
        else:
            val = 255 if state else 0

        self._state[0] = float(val)
        msg = Float64MultiArray()
        msg.data = [float(v) for v in self._state]
        self._pub.publish(msg)

        if duration and duration > 0:
            return ToolResult(True, f"Buzzer activated for {duration:.1f} seconds.")
        return ToolResult(True, "Buzzer ON" if state else "Buzzer OFF")
