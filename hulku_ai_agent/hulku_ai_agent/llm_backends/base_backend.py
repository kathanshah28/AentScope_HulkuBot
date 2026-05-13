"""Abstract base class for LLM backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """Represents a single tool call from the LLM."""
    name: str
    args: Dict[str, Any]
    id: str = ""  # Some APIs return a call ID for tracking


@dataclass
class LLMResponse:
    """Standard response from any LLM backend."""
    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    reasoning_details: Any = None

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class BaseLLMBackend(ABC):
    """
    Abstract interface for LLM providers.
    
    All backends must implement chat() which:
    1. Accepts a message history and tool definitions
    2. Returns an LLMResponse with either text or tool_calls
    """

    @abstractmethod
    def chat(self, messages: list, tools: list) -> LLMResponse:
        """
        Send a chat request to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'/'parts'
            tools: List of tool function declarations
            
        Returns:
            LLMResponse with either text or tool_calls
        """
        pass
