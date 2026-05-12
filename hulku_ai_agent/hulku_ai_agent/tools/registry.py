"""Tool registry that collects and manages all available tools."""

from typing import Dict, List, Any
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class ToolRegistry:
    """
    Central registry for all agent tools.
    
    Provides:
        - Registration of BaseTool instances
        - Tool schema generation for LLM function calling
        - Tool execution by name
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a tool instance. Overwrites if name already exists."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """Get a tool by name. Raises KeyError if not found."""
        return self._tools[name]

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_tool_definitions(self) -> List[dict]:
        """
        Returns a list of function declarations for the LLM.
        Each declaration follows the Gemini/OpenAI function calling schema.
        """
        return [tool.to_function_declaration() for tool in self._tools.values()]

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name with the given arguments.
        Returns a ToolResult with success/failure status.
        """
        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                message=f"Unknown tool: '{tool_name}'. Available: {list(self._tools.keys())}"
            )

        try:
            return self._tools[tool_name].execute(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"Tool '{tool_name}' crashed: {str(e)}"
            )

    def list_tools(self) -> str:
        """Pretty-print all registered tools."""
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"  - {name}: {tool.description}")
        return "\n".join(lines)
