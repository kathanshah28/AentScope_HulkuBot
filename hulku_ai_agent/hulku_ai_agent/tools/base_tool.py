"""Abstract base class for all robot tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Standard result returned by every tool execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.message}"


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.
    
    Every tool must define:
        - name: unique identifier (e.g., "move_joints")
        - description: human-readable description for the LLM
        - parameters: JSON Schema dict describing the tool's arguments
    
    To add a new tool:
        1. Create a new .py file in the tools/ directory
        2. Subclass BaseTool
        3. Implement execute(**kwargs) -> ToolResult
        4. Register it in tools/__init__.py
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given keyword arguments."""
        pass

    def to_function_declaration(self) -> dict:
        """
        Generates a function declaration dict compatible with 
        Gemini / OpenAI / Groq tool calling APIs.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
