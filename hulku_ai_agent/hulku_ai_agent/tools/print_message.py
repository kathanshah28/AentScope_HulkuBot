"""Tool to print messages to the user interface."""

from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult

class PrintMessageTool(BaseTool):
    name = "print_message"
    description = (
        "Print a message directly to the user's chat interface. "
        "Use this when the user explicitly asks you to 'print here' or 'tell me' "
        "intermediate information (like joint states) during a long sequence of tasks. "
        "IMPORTANT: You MUST format the actual numerical values or data into the message string yourself. "
        "Do not use placeholders like '[joint_angles]'. Pass the actual numbers."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to display to the user in the UI.",
            }
        },
        "required": ["message"],
    }

    def __init__(self, agent_node):
        self._node = agent_node

    def execute(self, message: str = "", **kwargs) -> ToolResult:
        if not message:
            return ToolResult(False, "Message cannot be empty.")
        
        # Inject the special tag so the GUI knows to render it as a chat bubble
        if hasattr(self._node, '_agent') and self._node._agent._feedback_cb:
            self._node._agent._feedback_cb(f"[USER_MSG]{message}")
            
        return ToolResult(True, "Successfully printed message to the UI.")
