"""ReAct (Reasoning + Acting) agent loop engine."""

import json
import logging

from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse
from hulku_ai_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentCore:
    """
    The ReAct loop engine.
    
    Flow:
        1. User sends a message
        2. LLM receives message + available tool definitions
        3. LLM either:
           a) Returns a tool_call → Agent executes it → feeds result back to LLM → repeat
           b) Returns text → Agent returns the text to the user (done)
        4. Loop continues until LLM produces text or max_steps is reached
    """

    def __init__(
        self,
        llm_backend: BaseLLMBackend,
        tool_registry: ToolRegistry,
        system_prompt: str,
        max_steps: int = 5,
        feedback_cb = None,
    ):
        self._llm = llm_backend
        self._registry = tool_registry
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._feedback_cb = feedback_cb

    def run(self, user_message: str) -> str:
        """
        Execute the full ReAct loop for a user message.
        
        Returns the final text response from the LLM.
        """
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_message},
        ]

        tool_definitions = self._registry.get_tool_definitions()

        for step in range(self._max_steps):
            logger.info(f"[Agent Step {step + 1}/{self._max_steps}]")

            response: LLMResponse = self._llm.chat(messages, tools=tool_definitions)

            if response.has_tool_calls():
                # Add the assistant's tool call as a single message
                assistant_msg = {
                    "role": "assistant",
                    "content": response.text or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.args)
                            }
                        } for tc in response.tool_calls
                    ]
                }
                messages.append(assistant_msg)

                for tc in response.tool_calls:
                    logger.info(f"  🔧 Calling tool: {tc.name}({tc.args})")
                    if self._feedback_cb:
                        self._feedback_cb(f"🔧 Calling tool: {tc.name}({tc.args})")

                    result = self._registry.execute(tc.name, **tc.args)

                    logger.info(f"  📋 Result: {result}")
                    if self._feedback_cb:
                        res_str = str(result)
                        if len(res_str) > 200:
                            res_str = res_str[:197] + "..."
                        self._feedback_cb(f"📋 Result: {res_str}")

                    # Add the tool result so the LLM can see what happened
                    messages.append({
                        "role": "tool_result",
                        "content": str(result),
                        "tool_name": tc.name,
                        "tool_call_id": tc.id if tc.id else "",
                    })
            else:
                # LLM returned a text response — we're done
                final_text = response.text or "Task completed."
                logger.info(f"  💬 Final response: {final_text}")
                return final_text

        # Max steps reached
        return "I completed the available steps. Some actions may have been executed successfully."
