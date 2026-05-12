"""Ollama LLM backend with tool calling support (Ollama 0.5+)."""

import json
import requests
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class OllamaBackend(BaseLLMBackend):
    """
    Ollama backend using the /api/chat endpoint with tool calling.
    Requires Ollama 0.5+ for native tool support.
    """

    def __init__(self, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to Ollama tool format."""
        ollama_tools = []
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return ollama_tools

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            role = msg["role"]
            if role == "tool_result":
                ollama_messages.append({
                    "role": "tool",
                    "content": msg["content"],
                })
            else:
                ollama_messages.append({
                    "role": role,
                    "content": msg["content"],
                })

        payload = {
            "model": self._model_name,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }

        if tools:
            payload["tools"] = self._convert_tools(tools)

        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            return LLMResponse(text=f"Error calling Ollama: {str(e)}")

        message = result.get("message", {})
        tool_calls_data = message.get("tool_calls", [])
        text = message.get("content", "")

        tool_calls = []
        for tc in tool_calls_data:
            func = tc.get("function", {})
            tool_calls.append(ToolCall(
                name=func.get("name", ""),
                args=func.get("arguments", {}),
            ))

        return LLMResponse(
            text=text if text else None,
            tool_calls=tool_calls,
        )
