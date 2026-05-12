"""Ollama Cloud LLM backend with tool calling support."""

import os
import json
import requests
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class OllamaCloudBackend(BaseLLMBackend):
    """
    Ollama Cloud backend using the /api/chat endpoint with tool calling.
    Designed for remote Ollama instances that may require authentication.
    """

    def __init__(self, model_name: str = "glm4:9b", base_url: str = None, api_key: str = None):
        self._model_name = model_name
        
        # Resolve URL: default to a typical remote proxy, or environment variable, or fallback
        self._base_url = base_url or os.environ.get("OLLAMA_CLOUD_URL", "http://your-remote-ollama.com:11434")
        self._base_url = self._base_url.rstrip("/")
        
        # Resolve API Key
        self._api_key = api_key or os.environ.get("OLLAMA_CLOUD_API_KEY", "")

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

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = requests.post(
                f"{self._base_url}/api/chat",
                headers=headers,
                json=payload,
                timeout=120, # Cloud calls might take longer
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            return LLMResponse(text=f"Error calling Ollama Cloud: {str(e)}")

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
