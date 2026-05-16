"""
MistralChatFormatter — OpenAIChatFormatter subclass that removes the `name`
field from all formatted messages.

Mistral's API uses the OpenAI-compatible endpoint but enforces a stricter
message schema that forbids the `name` field (which OpenAI allows). AgentScope's
OpenAIChatFormatter always injects `"name": msg.name`, causing a 422 error.

This formatter simply strips `name` (and any other keys Mistral rejects) from
the final message list before the model call.

Usage:
    formatter = MistralChatFormatter()
"""

from typing import Any

from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg


class MistralChatFormatter(OpenAIChatFormatter):
    """Drop-in replacement for OpenAIChatFormatter that strips the `name`
    field from all messages, making output compatible with the Mistral API."""

    async def _format(self, msgs: list[Msg]) -> list[dict[str, Any]]:
        # Let the parent do all the heavy lifting
        formatted = await super()._format(msgs)

        # Strip fields that Mistral rejects
        cleaned = []
        for msg in formatted:
            cleaned_msg = {k: v for k, v in msg.items() if k != "name"}
            cleaned.append(cleaned_msg)

        return cleaned
