"""Groq LLM backend with tool calling support."""

import os
import json
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class GroqBackend(BaseLLMBackend):
    """
    Groq backend using the Groq Python SDK with tool calling.
    Fast inference with models like llama-3.1-70b-versatile.
    
    API key resolution order:
        1. GROQ_API_KEY environment variable
        2. Explicitly passed api_key parameter
    """

    def __init__(self, model_name: str = "llama-3.1-70b-versatile", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "Groq API key not found. Set GROQ_API_KEY env var "
                "or pass api_key parameter."
            )

        from groq import Groq
        self._client = Groq(api_key=self._api_key)

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to OpenAI-compatible format used by Groq."""
        groq_tools = []
        for tool in tools:
            groq_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return groq_tools

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Convert messages to Groq/OpenAI format
        groq_messages = []
        for msg in messages:
            role = msg["role"]
            if role == "tool_result":
                groq_messages.append({
                    "role": "tool",
                    "content": msg["content"],
                    "tool_call_id": msg.get("tool_call_id", ""),
                })
            else:
                groq_messages.append({
                    "role": role,
                    "content": msg["content"],
                })

        kwargs = {
            "model": self._model_name,
            "messages": groq_messages,
            "temperature": 0.1,
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"
            # NOTE: Uncheck if needed for parallel tool calls disable if it cause problem with tool calls
            # kwargs["parallel_tool_calls"] = False

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(text=f"Error calling Groq: {str(e)}")

        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    args=args,
                    id=tc.id or "",
                ))

        return LLMResponse(
            text=message.content if message.content else None,
            tool_calls=tool_calls,
        )
