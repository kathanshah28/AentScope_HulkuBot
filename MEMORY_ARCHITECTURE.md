# Hybrid Memory Architecture for HulkuBot AI Agent

This document details the newly implemented Hybrid Memory Architecture for the HulkuBot AI Agent. The architecture consists of four distinct layers: Short-Term Memory, Working Memory, Semantic Memory, and Episodic Memory.

## Overview

The memory layers address the following shortcomings of the previous ReAct loop:
1. Wasting an LLM call to get joint states.
2. Generating physically impossible movements.
3. Not learning from past successful tool sequences.
4. Lacking context of recent conversation turns ("short-term memory").

The newly created `MemoryManager` module (`hulku_ai_agent/hulku_ai_agent/memory/memory_manager.py`) seamlessly integrates these layers into the `AgentCore` and `HulkuAgentNode`.

**New Update:** Added a 5th layer—**Declarative Memory (User Facts)**—to allow the system to explicitly memorize and recall facts through a persistent RAG system.

## 1. Short-Term Memory (Conversation History)

**Purpose**: Maintains context of the recent conversation, allowing the user to refer back to previous commands (e.g., "repeat previous task").
**Flow**:
- The `MemoryManager` maintains a list of the most recent user and assistant messages (capped to the last 10 messages to limit context window bloat).
- Before each LLM call, `AgentCore` retrieves the conversation history via `MemoryManager.get_conversation_history()`.
- The history is appended to the message list right after the system prompt.
- Once the LLM completes a task and returns a final response, both the user's initial command and the assistant's final textual response are appended to the history via `MemoryManager.add_to_conversation_history()`.

## 2. Working Memory (Real-Time State Injection)

**Purpose**: Provides the LLM with immediate context regarding the physical state of the hardware.
**Flow**:
- When a new `ArmTask` is received in `agent_node.py`, it retrieves `self.current_joint_state` and `self._gpio_state`.
- These states are passed directly to `AgentCore.run()`.
- The `MemoryManager` parses these objects and extracts joint angles (in degrees) and hardware statuses (buzzer, torque, RGB).
- The parsed information is formatted as a concise JSON string.
- This JSON string is injected into the system prompt before every query, saving an LLM tool call for `get_joint_states`.

## 3. Semantic Memory (Rules & Constraints)

**Purpose**: Grounds the LLM with deterministic facts and configuration-based physical rules to prevent hallucinated limits.
**Flow**:
- `MemoryManager` parses the loaded `agent_config.yaml`.
- It dynamically generates constraints related to the robot's physical layout, including:
  - Total Degrees of Freedom (DOF).
  - List of accessible Joint Names.
  - Safe Home Position values.
  - Payload limits (Max Payload: 500g).
  - Trajectory instructions (Ensure smooth movement, enable torque mode).
- This string is pre-pended to the injected state in the LLM's system prompt.

## 4. Episodic Memory (Experience via RAG)

**Purpose**: Allows the agent to recall successful long-chain tasks and adapt faster via few-shot prompting, enabling "learning by doing."
**Implementation**: Uses a local Vector DB via ChromaDB (collection: `agent_experiences`).

**Write (Learning)**:
- In `agent_core.py`, when a sequence of tool calls successfully completes and yields a final text response, the `MemoryManager` captures the user's initial command and the array of tools executed.
- `MemoryManager.save_episodic_memory()` embeds this data and stores it in the `agent_experiences` collection in the local ChromaDB.

**Retrieve (Recall)**:
- Upon receiving a new user command, `AgentCore` invokes `MemoryManager.retrieve_episodic_memory()`.
- The user's command is embedded and evaluated against the database.
- If similar successful tasks are found with a cosine similarity > 0.85, the tool trajectories are attached to the end of the user's prompt as "Previous successful experiences."

## 5. Declarative Memory (User Facts via RAG)

**Purpose**: Gives the agent the ability to remember explicit facts, user preferences, and specific references indefinitely (e.g., "The user's favorite color is blue" or "The home position for the gripper is 90 degrees").
**Implementation**: Uses the same local ChromaDB, but a separate collection (`user_facts`).

**Write (Explicit Save via Tool)**:
- A dedicated tool `save_memory` is exposed to the LLM.
- When the user issues a command like "remember my name is Jules," the LLM intelligently invokes `save_memory(fact="User's name is Jules")`.
- `MemoryManager.save_user_memory()` explicitly saves this fact into the `user_facts` collection in ChromaDB.

**Retrieve (Automatic Context Injection)**:
- Upon receiving any user command, `AgentCore` queries `MemoryManager.retrieve_user_memory()`.
- If the user's query mathematically aligns (cosine similarity > 0.85) with previously saved facts, those facts are automatically retrieved.
- They are injected seamlessly into the System Prompt before the LLM generates a response, providing silent but reliable context (e.g., *Relevant known facts: User's name is Jules*).

## Graceful DB Degradation
ChromaDB instances are safely caught using `try-except` blocks. If Vector DB fails to instantiate or query properly (due to missing packages or local read/write issues), the agent will gracefully fall back to executing tasks solely on Semantic and Working Memory, without crashing the core ROS2 loop.
