import os
import shutil
import pytest
from hulku_ai_agent.memory.memory_manager import MemoryManager
from hulku_ai_agent.tools.save_memory import SaveMemoryTool

TEST_DB_PATH = "./test_memory_db"

@pytest.fixture
def memory_manager():
    # Setup
    if os.path.exists(TEST_DB_PATH):
        shutil.rmtree(TEST_DB_PATH)

    mm = MemoryManager(config={'robot': {}}, db_path=TEST_DB_PATH)
    yield mm

    # Teardown
    if os.path.exists(TEST_DB_PATH):
        try:
            # Try to clean up after tests, ignoring file-in-use errors sometimes caused by Chroma
            shutil.rmtree(TEST_DB_PATH, ignore_errors=True)
        except Exception:
            pass

def test_save_and_retrieve_user_memory(memory_manager):
    """Test that explicit user facts are saved and can be retrieved via similarity."""

    # If Chroma isn't available, we skip the assertion logic
    if not memory_manager._user_collection:
        pytest.skip("ChromaDB not available for memory tests.")

    fact = "The user's favorite color is specifically neon green."

    # Ensure it's empty first
    result_empty = memory_manager.retrieve_user_memory("What is my favorite color?")
    assert result_empty == ""

    # Save memory directly
    memory_manager.save_user_memory(fact)

    # Retrieve it
    result_found = memory_manager.retrieve_user_memory("Can you remember what my favorite color is?", threshold=0.7)

    assert "neon green" in result_found
    assert "Relevant known facts" in result_found

def test_save_memory_tool(memory_manager):
    """Test that the tool correctly bridges the gap to MemoryManager."""
    if not memory_manager._user_collection:
        pytest.skip("ChromaDB not available for memory tests.")

    tool = SaveMemoryTool(memory_manager)

    # Test execution
    res = tool.execute(fact="The project is called Hulkubot.")
    assert res.success == True
    assert "Successfully saved" in res.message

    # Verify retrieval
    retrieved = memory_manager.retrieve_user_memory("What is the project called?", threshold=0.7)
    assert "Hulkubot" in retrieved
