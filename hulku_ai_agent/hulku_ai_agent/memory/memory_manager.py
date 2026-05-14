import json
import logging
import math
import os
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages the Hybrid Memory Architecture for the Agent.
    Handles Working Memory (real-time state), Semantic Memory (rules/constraints),
    and Episodic Memory (past successful experiences via RAG).
    """

    def __init__(self, config: Dict[str, Any], db_path: str = "./memory_db"):
        self.config = config
        self._db_path = db_path
        self._collection = None
        self._db_client = None
        self._conversation_history: List[Dict[str, str]] = []

        # Try to initialize Episodic Memory (ChromaDB)
        self._init_episodic_memory()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Returns the short-term conversation history."""
        return self._conversation_history

    def add_to_conversation_history(self, role: str, content: str) -> None:
        """Adds a message to the short-term conversation history."""
        self._conversation_history.append({"role": role, "content": content})
        # Keep only the last 10 messages (5 pairs)
        if len(self._conversation_history) > 10:
            self._conversation_history = self._conversation_history[-10:]

    def _init_episodic_memory(self) -> None:
        if not CHROMA_AVAILABLE:
            logger.warning("ChromaDB not installed. Episodic Memory disabled.")
            return

        try:
            os.makedirs(self._db_path, exist_ok=True)
            self._db_client = chromadb.PersistentClient(path=self._db_path, settings=Settings(anonymized_telemetry=False))
            self._collection = self._db_client.get_or_create_collection(
                name="agent_experiences",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Episodic Memory initialized at {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Vector DB: {e}. Episodic Memory disabled.")
            self._collection = None

    def get_working_memory(self, joint_state: Any, gpio_state: List[float], joint_names: List[str]) -> str:
        """
        Formats real-time state into a concise JSON string.
        """
        if joint_state is None:
            state_dict = {"status": "Joint states not available yet."}
        else:
            js_map = dict(zip(joint_state.name, joint_state.position))
            angles = {}
            for name in joint_names:
                rad = js_map.get(name, 0.0)
                angles[name] = round(math.degrees(rad), 1)

            # Extract GPIO states based on expected index
            # [buzzer, torque, r, g, b]
            buzzer = bool(gpio_state[0]) if len(gpio_state) > 0 else False
            torque = bool(gpio_state[1]) if len(gpio_state) > 1 else True
            r = int(gpio_state[2]) if len(gpio_state) > 2 else 0
            g = int(gpio_state[3]) if len(gpio_state) > 3 else 0
            b = int(gpio_state[4]) if len(gpio_state) > 4 else 0

            state_dict = {
                "joints_degrees": angles,
                "hardware_status": {
                    "torque_enabled": torque,
                    "buzzer_active": buzzer,
                    "rgb_light": [r, g, b]
                }
            }

        return json.dumps(state_dict)

    def get_semantic_memory(self) -> str:
        """
        Retrieves rules and constraints from configuration to ground the LLM.
        """
        robot_config = self.config.get('robot', {})
        dof = robot_config.get('dof', 5)
        joint_names = robot_config.get('joint_names', [])
        home_pos = robot_config.get('home_position', [0]*dof)

        semantic_str = (
            f"Physical Constraints:\n"
            f"- Degrees of Freedom (DOF): {dof}\n"
            f"- Joint Names: {', '.join(joint_names)}\n"
            f"- Home Position (degrees): {home_pos}\n"
            f"- Max Payload: 500g (do not attempt to lift heavy objects)\n"
            f"- Workspace limits: Avoid self-collision and exceeding joint limits.\n"
            f"- Maintain smooth trajectories. Torque mode must be enabled for movement."
        )
        return semantic_str

    def retrieve_episodic_memory(self, user_command: str, threshold: float = 0.85) -> str:
        """
        Queries Vector DB for past successful tool sequences matching the command.
        """
        if not self._collection:
            return ""

        try:
            results = self._collection.query(
                query_texts=[user_command],
                n_results=3
            )

            if not results or not results['documents'] or not results['documents'][0]:
                return ""

            experiences = []
            for i, doc in enumerate(results['documents'][0]):
                # Distance in cosine space: smaller is more similar. For threshold mapping, use distance directly or convert.
                distance = results['distances'][0][i]
                similarity = 1.0 - distance # rough similarity for cosine

                if similarity >= threshold:
                    experiences.append(doc)

            if experiences:
                return "Previous successful experiences:\n" + "\n".join(f"- {exp}" for exp in experiences)
            return ""

        except Exception as e:
            logger.error(f"Error querying episodic memory: {e}")
            return ""

    def save_episodic_memory(self, user_command: str, tool_sequence: List[str]) -> None:
        """
        Saves a successful natural language command and its executed tool sequence to Vector DB.
        """
        if not self._collection:
            return

        try:
            import uuid
            doc_id = str(uuid.uuid4())
            doc_text = f"Command: '{user_command}' -> Tools: {json.dumps(tool_sequence)}"

            self._collection.add(
                documents=[doc_text],
                metadatas=[{"command": user_command}],
                ids=[doc_id]
            )
            logger.info(f"Saved successful experience to memory: {doc_text}")
        except Exception as e:
            logger.error(f"Error saving to episodic memory: {e}")
