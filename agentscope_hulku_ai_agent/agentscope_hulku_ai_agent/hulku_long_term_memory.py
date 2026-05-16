"""
HulkuLongTermMemory — AgentScope LongTermMemoryBase integration.

Wraps ChromaDB to provide:
  - Episodic Memory: past successful tool sequences
  - Declarative Memory: user-stated facts / preferences

Plugged into ReActAgent with long_term_memory_mode="both":
  - AgentScope auto-calls retrieve() before each reply (injects into sys_prompt)
  - AgentScope auto-calls record() after each reply
  - The agent can also call record_to_memory() and retrieve_from_memory() as tools
"""

import json
import logging
import uuid
from typing import Any

from agentscope.memory import LongTermMemoryBase
from agentscope.message import Msg, TextBlock
from agentscope.tool._response import ToolResponse

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class HulkuLongTermMemory(LongTermMemoryBase):
    """
    Hybrid long-term memory for HulkuBot.

    Stores two separate ChromaDB collections:
      - agent_experiences : episodic memory (tool sequences that worked)
      - user_facts        : declarative memory (facts the user asked to save)

    retrieve() is called by AgentScope automatically before each agent reply.
    record()   is called by AgentScope automatically after each agent reply.
    record_to_memory() / retrieve_from_memory() are exposed as agent tools.
    """

    def __init__(
        self,
        db_path: str = "./hulku_memory_db",
        similarity_threshold: float = 0.75,
    ) -> None:
        self._db_path = db_path
        self._threshold = similarity_threshold
        self._collection = None        # episodic memory
        self._user_collection = None   # declarative memory
        self._db_client = None

        self._init_chroma()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_chroma(self) -> None:
        if not CHROMA_AVAILABLE:
            logger.warning(
                "ChromaDB not installed. Long-term memory (episodic/declarative) disabled."
            )
            return

        try:
            import os
            os.makedirs(self._db_path, exist_ok=True)
            self._db_client = chromadb.PersistentClient(
                path=self._db_path,
                settings=Settings(anonymized_telemetry=False),
            )

            self._collection = self._db_client.get_or_create_collection(
                name="agent_experiences",
                metadata={"hnsw:space": "cosine"},
            )
            self._user_collection = self._db_client.get_or_create_collection(
                name="user_facts",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "HulkuLongTermMemory: ChromaDB initialised at '%s'", self._db_path
            )
        except Exception as exc:
            logger.error("HulkuLongTermMemory init failed: %s", exc)
            self._collection = None
            self._user_collection = None

    # ------------------------------------------------------------------
    # Developer-facing methods (called by AgentScope automatically)
    # ------------------------------------------------------------------
    async def retrieve(
        self,
        msg: "Msg | list[Msg] | None",
        limit: int = 3,
        **kwargs: Any,
    ) -> str:
        """
        Called by AgentScope before each reply.
        Returns a formatted string that is injected into the system prompt.
        """
        if msg is None:
            return ""

        # Build query text from the latest user message
        if isinstance(msg, list):
            query_text = " ".join(
                m.content if isinstance(m.content, str) else str(m.content)
                for m in msg
                if m is not None
            )
        else:
            query_text = (
                msg.content if isinstance(msg.content, str) else str(msg.content)
            )

        if not query_text.strip():
            return ""

        parts = []

        # --- Episodic ---
        episodic = self._query_collection(
            self._collection, query_text, limit, self._threshold
        )
        if episodic:
            parts.append(
                "📚 Relevant past experiences:\n"
                + "\n".join(f"  • {e}" for e in episodic)
            )

        # --- Declarative / User facts ---
        user_facts = self._query_collection(
            self._user_collection, query_text, limit, self._threshold
        )
        if user_facts:
            parts.append(
                "🧠 Known facts from memory:\n"
                + "\n".join(f"  • {f}" for f in user_facts)
            )

        return "\n\n".join(parts) if parts else ""

    async def record(
        self,
        msgs: "list[Msg | None]",
        **kwargs: Any,
    ) -> None:
        """
        Called by AgentScope after each reply.
        Saves tool-call sequences to episodic memory.
        """
        if not self._collection or not msgs:
            return

        # Collect tool names from assistant messages in this turn
        tool_names = []
        user_content = ""

        for msg in msgs:
            if msg is None:
                continue
            if msg.role == "user" and isinstance(msg.content, str):
                user_content = msg.content
            # AgentScope stores tool use info in content blocks
            if msg.role == "assistant" and msg.content:
                content = msg.content
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "type") and block.type == "tool_use":
                            tool_names.append(getattr(block, "name", "unknown"))
                        elif isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_names.append(block.get("name", "unknown"))

        if user_content and tool_names:
            doc_text = (
                f"Command: '{user_content}' -> Tools: {json.dumps(tool_names)}"
            )
            try:
                self._collection.add(
                    documents=[doc_text],
                    metadatas=[{"command": user_content}],
                    ids=[str(uuid.uuid4())],
                )
                logger.info("Saved episodic memory: %s", doc_text)
            except Exception as exc:
                logger.error("Failed to save episodic memory: %s", exc)

    # ------------------------------------------------------------------
    # Agent-controlled tool methods (exposed as tools in ReActAgent)
    # ------------------------------------------------------------------
    async def record_to_memory(
        self,
        thinking: str,
        content: "list[str]",
        **kwargs: Any,
    ) -> ToolResponse:
        """Use this function to save an important fact or user preference to
        long-term memory. Call this when the user explicitly asks you to
        remember something or when they share a personal fact.

        Args:
            thinking (str): Your reasoning about what to save and why.
            content (list[str]): A list of concise, standalone facts to save.
                Each item should read like a self-contained statement,
                e.g. ["The user's name is Kathan", "Preferred home position: all joints at 0"].
        """
        if not self._user_collection:
            return ToolResponse(
                content=[TextBlock(type="text", text="⚠️ Memory storage unavailable.")]
            )

        saved = []
        for fact in content:
            if not fact.strip():
                continue
            try:
                self._user_collection.add(
                    documents=[fact],
                    metadatas=[{"type": "user_fact"}],
                    ids=[str(uuid.uuid4())],
                )
                saved.append(fact)
            except Exception as exc:
                logger.error("record_to_memory failed for '%s': %s", fact, exc)

        if saved:
            msg = f"✅ Saved {len(saved)} fact(s) to memory:\n" + "\n".join(
                f"  • {s}" for s in saved
            )
        else:
            msg = "⚠️ No facts were saved (empty or failed)."

        return ToolResponse(content=[TextBlock(type="text", text=msg)])

    async def retrieve_from_memory(
        self,
        keywords: "list[str]",
        limit: int = 5,
        **kwargs: Any,
    ) -> ToolResponse:
        """Search your long-term memory for relevant facts or past experiences.

        Args:
            keywords (list[str]): Search terms to query memory with,
                e.g. ["user name", "favorite position", "gripper"].
            limit (int): Maximum number of results per keyword. Defaults to 5.
        """
        if not self._user_collection and not self._collection:
            return ToolResponse(
                content=[TextBlock(type="text", text="⚠️ Memory unavailable.")]
            )

        results = []
        for kw in keywords:
            # Search user facts
            facts = self._query_collection(
                self._user_collection, kw, limit, threshold=0.0
            )
            for f in facts:
                if f not in results:
                    results.append(f"[Fact] {f}")

            # Search episodic
            episodes = self._query_collection(
                self._collection, kw, limit, threshold=0.0
            )
            for e in episodes:
                if e not in results:
                    results.append(f"[Experience] {e}")

        if results:
            text = "🔍 Retrieved from memory:\n" + "\n".join(
                f"  {i+1}. {r}" for i, r in enumerate(results)
            )
        else:
            text = "🔍 No relevant memories found."

        return ToolResponse(content=[TextBlock(type="text", text=text)])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _query_collection(
        self,
        collection: Any,
        query: str,
        limit: int,
        threshold: float,
    ) -> list:
        if collection is None:
            return []
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(limit, max(1, collection.count())),
            )
            if (
                not results
                or not results.get("documents")
                or not results["documents"][0]
            ):
                return []

            docs = []
            for doc, dist in zip(
                results["documents"][0], results["distances"][0]
            ):
                similarity = 1.0 - dist  # cosine distance → similarity
                if similarity >= threshold:
                    docs.append(doc)
            return docs
        except Exception as exc:
            logger.error("ChromaDB query error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # StateModule compatibility
    # ------------------------------------------------------------------
    def state_dict(self) -> dict:
        return {"db_path": self._db_path, "threshold": self._threshold}

    def load_state_dict(self, state_dict: dict, strict: bool = True) -> None:
        pass  # ChromaDB is persistent; nothing to restore in-memory
