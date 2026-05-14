import sys

def modify_agent_core():
    with open('./hulku_ai_agent/hulku_ai_agent/agent_core.py', 'r') as f:
        content = f.read()

    # We need to add self._conversation_history = []
    # And we need to append to messages instead of just using system+user

    # 1. Add _conversation_history in __init__
    content = content.replace(
        "self._feedback_cb = feedback_cb",
        "self._feedback_cb = feedback_cb\n        self._conversation_history = []"
    )

    # 2. Add history management in run()
    run_def = """        messages = [
            {"role": "system", "content": augmented_system_prompt},
        ]

        # Append short-term conversation history
        messages.extend(self._conversation_history)

        # Append current user command
        messages.append({"role": "user", "content": user_content})"""

    content = content.replace(
        """        messages = [
            {"role": "system", "content": augmented_system_prompt},
            {"role": "user", "content": user_content},
        ]""",
        run_def
    )

    # 3. Save to history at the end
    end_text = """                # Save to episodic memory if we successfully executed tools
                if executed_tools:
                    self._memory_manager.save_episodic_memory(user_message, executed_tools)

                # Update conversation history
                self._conversation_history.append({"role": "user", "content": user_message})
                self._conversation_history.append({"role": "assistant", "content": final_text})

                # Keep history short (e.g., last 10 messages)
                if len(self._conversation_history) > 10:
                    self._conversation_history = self._conversation_history[-10:]

                return final_text"""

    content = content.replace(
        """                # Save to episodic memory if we successfully executed tools
                if executed_tools:
                    self._memory_manager.save_episodic_memory(user_message, executed_tools)

                return final_text""",
        end_text
    )

    with open('./hulku_ai_agent/hulku_ai_agent/agent_core.py', 'w') as f:
        f.write(content)

modify_agent_core()
