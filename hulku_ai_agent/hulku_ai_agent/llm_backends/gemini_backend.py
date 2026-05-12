"""Gemini LLM backend with native function calling support."""

import os
import json
from typing import List

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse, ToolCall


# Type mapping from JSON Schema to Gemini proto types
_TYPE_MAP = {
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


class GeminiBackend(BaseLLMBackend):
    """
    Google Gemini backend using the google-genai SDK.
    
    Uses gemini-2.0-flash by default — it has the best free-tier quota 
    and full function calling support. Users with Google AI Pro plan
    can also use gemini-2.5-flash or gemini-2.5-pro.
    
    API key resolution order:
        1. GEMINI_API_KEY environment variable (default)
        2. Explicitly passed api_key parameter
    """

    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: str = None):
        self._model_name = model_name
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

        if not self._api_key:
            raise ValueError(
                "Gemini API key not found. Set GEMINI_API_KEY env var "
                "or pass api_key parameter."
            )

        import google.generativeai as genai
        genai.configure(api_key=self._api_key)
        self._genai = genai

    def _json_schema_to_proto_schema(self, schema: dict):
        """Convert a JSON Schema dict into a genai.protos.Schema object."""
        protos = self._genai.protos

        schema_type = schema.get("type", "object").upper()
        # Map JSON Schema type strings to proto Type enum
        proto_type = getattr(protos.Type, _TYPE_MAP.get(schema.get("type", "object"), "OBJECT"))

        kwargs = {"type": proto_type}

        if "description" in schema:
            kwargs["description"] = schema["description"]

        if "enum" in schema:
            kwargs["enum"] = schema["enum"]

        # Handle properties (for object types)
        if "properties" in schema:
            props = {}
            for prop_name, prop_schema in schema["properties"].items():
                props[prop_name] = self._json_schema_to_proto_schema(prop_schema)
            kwargs["properties"] = props

        if "required" in schema:
            kwargs["required"] = schema["required"]

        # Handle array items
        if "items" in schema:
            kwargs["items"] = self._json_schema_to_proto_schema(schema["items"])

        return protos.Schema(**kwargs)

    def _convert_tools(self, tools: list) -> list:
        """Convert our tool definitions to Gemini FunctionDeclaration format."""
        protos = self._genai.protos
        declarations = []

        for tool in tools:
            params = tool.get("parameters", {})
            # Convert JSON Schema to Gemini proto Schema
            proto_schema = self._json_schema_to_proto_schema(params)

            declarations.append(
                protos.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters=proto_schema,
                )
            )

        return [protos.Tool(function_declarations=declarations)]

    def chat(self, messages: list, tools: list) -> LLMResponse:
        # Separate system prompt from conversation
        system_instruction = None
        history = []
        latest_message = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                latest_message = content
            elif role == "assistant":
                history.append({"role": "model", "parts": [content]})
            elif role == "tool_result":
                # Gemini expects function responses with this specific structure
                history.append({
                    "role": "function",
                    "parts": [self._genai.protos.Part(
                        function_response=self._genai.protos.FunctionResponse(
                            name=msg.get("tool_name", "unknown"),
                            response={"result": content}
                        )
                    )]
                })

        # All user messages except the last go into history
        user_msgs = [m for m in messages if m["role"] == "user"]
        if len(user_msgs) > 1:
            for um in user_msgs[:-1]:
                history.append({"role": "user", "parts": [um["content"]]})

        gemini_tools = self._convert_tools(tools) if tools else None

        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_instruction,
            tools=gemini_tools,
        )

        chat = model.start_chat(history=history)
        response = chat.send_message(latest_message)

        # Parse the response
        candidate = response.candidates[0]
        tool_calls = []
        text_parts = []

        for part in candidate.content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                fc = part.function_call
                # Convert protobuf args to a clean Python dict
                args = {}
                if fc.args:
                    try:
                        # Use protobuf's json_format on the underlying proto message
                        from google.protobuf import json_format as proto_json
                        args = json.loads(proto_json.MessageToJson(fc._pb.args))
                    except Exception:
                        # Fallback: manually iterate the MapComposite
                        for k, v in fc.args.items():
                            args[k] = self._convert_proto_value(v)
                tool_calls.append(ToolCall(name=fc.name, args=args))
            elif hasattr(part, 'text') and part.text:
                text_parts.append(part.text)

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _convert_proto_value(val):
        """Recursively convert a protobuf Value/MapComposite to native Python."""
        if isinstance(val, (str, int, float, bool)):
            return val
        if isinstance(val, (list, tuple)):
            return [GeminiBackend._convert_proto_value(v) for v in val]
        if isinstance(val, dict):
            return {k: GeminiBackend._convert_proto_value(v) for k, v in val.items()}
        # Try accessing as a proto Value
        if hasattr(val, 'number_value'):
            return val.number_value
        if hasattr(val, 'string_value'):
            return val.string_value
        if hasattr(val, 'bool_value'):
            return val.bool_value
        if hasattr(val, 'items'):
            return {k: GeminiBackend._convert_proto_value(v) for k, v in val.items()}
        return str(val)
