"""Tool to save explicit user facts and preferences to Declarative Memory."""

from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult
import logging

logger = logging.getLogger(__name__)

class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = (
        "Save an important fact, user preference, or piece of information to long-term declarative memory. "
        "Use this tool ONLY when the user explicitly asks you to remember or save something, or when they tell you a fact about themselves. "
        "The fact should be written clearly and concisely as a standalone statement (e.g., 'The user\\'s favorite color is blue' or 'The project is called Hulkubot')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The clear, standalone fact or preference to save to memory.",
            }
        },
        "required": ["fact"],
    }

    def __init__(self, memory_manager):
        self._memory_manager = memory_manager

    def execute(self, fact: str = "", **kwargs) -> ToolResult:
        if not fact:
            return ToolResult(False, "Fact cannot be empty.")

        try:
            self._memory_manager.save_user_memory(fact)
            return ToolResult(True, f"Successfully saved fact to memory: '{fact}'")
        except Exception as e:
            logger.error(f"SaveMemoryTool failed: {e}")
            return ToolResult(False, f"Failed to save fact to memory due to an error: {e}")
