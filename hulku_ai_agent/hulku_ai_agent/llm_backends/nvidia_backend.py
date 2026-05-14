"""NVIDIA NIM LLM backend with tool calling support."""

import os
import json

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class NvidiaBackend(BaseLLMBackend):
    """
    NVIDIA backend using the OpenAI Python SDK.
    
    API key resolution order:
        1. NVIDIA_API_KEY environment variable
        2. Explicitly passed api_key parameter
    """

    def __init__(self, model_name: str = "qwen/qwen3-coder-480b-a35b-instruct", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "NVIDIA API key not found. Set NVIDIA_API_KEY env var "
                "or pass api_key parameter."
            )

        # pyrefly: ignore [missing-import]
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self._api_key,
        )

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to OpenAI-compatible format."""
        nvidia_tools = []
        for tool in tools:
            nvidia_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return nvidia_tools

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Convert messages to OpenAI format
        nvidia_messages = []
        for msg in messages:
            role = msg["role"]
            if role == "tool_result":
                nvidia_messages.append({
                    "role": "tool",
                    "content": msg["content"],
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "name": msg.get("tool_name", ""),
                })
            else:
                out_msg = {
                    "role": role,
                    "content": msg["content"],
                }
                if "tool_calls" in msg:
                    out_msg["tool_calls"] = msg["tool_calls"]
                
                nvidia_messages.append(out_msg)

        kwargs = {
            "model": self._model_name,
            "messages": nvidia_messages,
            "temperature": 0.1,
            # Keeping stream=False (default) as the AgentCore expects full response
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(text=f"Error calling NVIDIA API: {str(e)}")

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
