"""ReAct (Reasoning + Acting) agent loop engine."""

import json
import logging

from typing import Any, List, Optional
from hulku_ai_agent.llm_backends.base_backend import BaseLLMBackend, LLMResponse
from hulku_ai_agent.tools.registry import ToolRegistry
from hulku_ai_agent.memory.memory_manager import MemoryManager

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
        memory_manager: MemoryManager,
        max_steps: int = 5,
        feedback_cb = None,
    ):
        self._llm = llm_backend
        self._registry = tool_registry
        self._system_prompt = system_prompt
        self._memory_manager = memory_manager
        self._max_steps = max_steps
        self._feedback_cb = feedback_cb
        self._conversation_history = []

    def run(
        self,
        user_message: str,
        current_joint_state: Any = None,
        gpio_state: Optional[List[float]] = None,
        joint_names: Optional[List[str]] = None
    ) -> str:
        """
        Execute the full ReAct loop for a user message.
        
        Returns the final text response from the LLM.
        """
        # Gather semantic memory
        semantic_mem = self._memory_manager.get_semantic_memory()

        # Gather working memory
        gpio_state = gpio_state or []
        joint_names = joint_names or []
        working_mem = self._memory_manager.get_working_memory(current_joint_state, gpio_state, joint_names)

        # Build comprehensive system prompt
        augmented_system_prompt = f"{self._system_prompt}\n\n---\n{semantic_mem}\n\n---\nReal-Time Hardware State (Working Memory):\n{working_mem}\n"

        # Gather episodic memory
        episodic_mem = self._memory_manager.retrieve_episodic_memory(user_message)
        user_content = user_message
        if episodic_mem:
            user_content = f"{episodic_mem}\n\nUser Command: {user_message}"

        # Gather short-term conversation history
        conv_history = self._memory_manager.get_conversation_history()

        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        # Add conversation history
        messages.extend(conv_history)

        # Add the current user message
        messages.append({"role": "user", "content": user_content})

        tool_definitions = self._registry.get_tool_definitions()

        executed_tools = []

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

                    executed_tools.append(tc.name)
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

                # Save to episodic memory if we successfully executed tools
                if executed_tools:
                    self._memory_manager.save_episodic_memory(user_message, executed_tools)

                # Save to short-term memory
                self._memory_manager.add_to_conversation_history("user", user_message)
                self._memory_manager.add_to_conversation_history("assistant", final_text)

                return final_text

        # Max steps reached
        self._memory_manager.add_to_conversation_history("user", user_message)
        self._memory_manager.add_to_conversation_history("assistant", "I completed the available steps. Some actions may have been executed successfully.")
        return "I completed the available steps. Some actions may have been executed successfully."
