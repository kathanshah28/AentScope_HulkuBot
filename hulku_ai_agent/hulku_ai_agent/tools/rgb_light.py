"""Control the robot RGB light via gpio_controller topic."""

from std_msgs.msg import Float64MultiArray
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class RGBLightTool(BaseTool):
    name = "rgb_light"
    description = "Change the color of the robot's RGB lights."
    parameters = {
        "type": "object",
        "properties": {
            "r": {"type": "integer", "description": "Red value (0-255).", "minimum": 0, "maximum": 255},
            "g": {"type": "integer", "description": "Green value (0-255).", "minimum": 0, "maximum": 255},
            "b": {"type": "integer", "description": "Blue value (0-255).", "minimum": 0, "maximum": 255},
        },
        "required": ["r", "g", "b"],
    }

    def __init__(self, node, gpio_pub, gpio_state):
        self._node = node
        self._pub = gpio_pub
        self._state = gpio_state  # shared list [buzzer, torque, r, g, b]

    def execute(self, r: int, g: int, b: int, **kwargs) -> ToolResult:
        self._state[2] = float(min(255, max(0, int(r))))
        self._state[3] = float(min(255, max(0, int(g))))
        self._state[4] = float(min(255, max(0, int(b))))

        msg = Float64MultiArray()
        msg.data = [float(v) for v in self._state]
        self._pub.publish(msg)

        return ToolResult(True, f"RGB set to ({int(r)}, {int(g)}, {int(b)})")
