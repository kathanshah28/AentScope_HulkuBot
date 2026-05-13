"""OpenRouter LLM backend with tool calling and reasoning support."""

import os
import json

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


class OpenRouterBackend(BaseLLMBackend):
    """
    OpenRouter backend using the OpenAI Python SDK.
    Supports reasoning models via OpenRouter's extra_body parameters.
    
    API key resolution order:
        1. OPENROUTER_API_KEY environment variable
        2. Explicitly passed api_key parameter
    """

    def __init__(self, model_name: str = "openai/gpt-oss-120b:free", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY env var "
                "or pass api_key parameter."
            )

        # pyrefly: ignore [missing-import]
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key,
        )

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to OpenAI-compatible format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
            })
        return openai_tools

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Convert messages to OpenAI/OpenRouter format
        openai_messages = []
        for msg in messages:
            role = msg["role"]
            if role == "tool_result":
                openai_messages.append({
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
                
                # Preserve reasoning_details if present
                if "reasoning_details" in msg:
                    out_msg["reasoning_details"] = msg["reasoning_details"]
                    
                openai_messages.append(out_msg)

        kwargs = {
            "model": self._model_name,
            "messages": openai_messages,
            "temperature": 0.1,
            "extra_body": {"reasoning": {"enabled": True}}
        }

        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(text=f"Error calling OpenRouter: {str(e)}")

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
            reasoning_details=getattr(message, "reasoning_details", None)
        )
