"""Tool to pause execution for a specified duration."""

import time
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class WaitTool(BaseTool):
    name = "wait"
    description = (
        "Wait or pause execution for a specific number of seconds. "
        "Use this when you need to introduce a delay between actions, "
        "such as waiting for a process to complete or keeping a state active for some time."
    )
    parameters = {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "number",
                "description": "Number of seconds to wait (e.g., 5.0, 60).",
            }
        },
        "required": ["seconds"],
    }

    def execute(self, seconds: float = 0.0, **kwargs) -> ToolResult:
        try:
            sec = float(seconds)
        except (ValueError, TypeError):
            return ToolResult(False, f"Invalid value for seconds: {seconds}")

        if sec <= 0:
            return ToolResult(False, "Seconds must be greater than 0.")
        
        # Safety cap to prevent completely locking up the agent indefinitely
        if sec > 300:
            return ToolResult(False, "Cannot wait for more than 300 seconds (5 minutes) at a time.")
            
        time.sleep(sec)
        return ToolResult(True, f"Successfully waited for {sec} seconds.")
