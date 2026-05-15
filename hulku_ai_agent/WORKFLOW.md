# HulkuBot Data Flow and Workflow

This document outlines the high-level data flow of the `hulku_ai_agent` and how the memory layers (including the new User Memory RAG) interact with the core ROS 2 node.

## 1. Request Initialization
1. User provides a natural language command (e.g., via the `hulku_ai_gui` speech-to-text).
2. The command is sent as an `ArmTask` action request via ROS 2 to the `hulku_agent_node` (`agent_node.py`).
3. `HulkuAgentNode` intercepts the request and extracts the raw `user_message`.

## 2. Context Gathering (MemoryManager)
Before querying the LLM, `AgentCore` dynamically constructs a prompt using the `MemoryManager`:
*   **Layer 1 (Short-term):** Retrieves the rolling conversation history (last 10 turns).
*   **Layer 2 (Working):** Injects live ROS 2 `/joint_states` and custom GPIO array states (buzzer, RGB, torque).
*   **Layer 3 (Semantic):** Injects hardcoded limits from `agent_config.yaml` (Max payload, DoF, Home position).
*   **Layer 4 (Episodic):** Queries ChromaDB (`agent_experiences`) to see if a similar command was completed before.
*   **Layer 5 (Declarative):** Queries ChromaDB (`user_facts`) to inject previously saved user preferences/facts relevant to the prompt.

## 3. ReAct LLM Loop (AgentCore)
The combined prompt + user message is sent to the LLM backend (Groq/Gemini).
*   The LLM parses the prompt and decides to either:
    *   **A) Execute a tool:** Returns a JSON tool call.
    *   **B) Return text:** Concludes the task.
*   If a tool is called, `ToolRegistry` matches the name (e.g., `save_memory`, `move_joints`) and runs `execute()`.
*   The tool result (success/fail string) is passed *back* to the LLM.
*   This loop continues until the LLM returns a final text string.

## 4. Finalization & Memory Storage
1. The final text string is sent back to the GUI via the ROS 2 Action server as the result.
2. `MemoryManager` performs cleanup and storage:
    *   Saves the exchange to Layer 1 (Conversation History).
    *   If tools were successfully used, the tool sequence is embedded into Layer 4 (ChromaDB `agent_experiences`).
    *   *(Note: Layer 5 user facts are saved synchronously during the loop if the LLM chose to use the `save_memory` tool)*.
