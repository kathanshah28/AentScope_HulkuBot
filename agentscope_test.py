import agentscope
import asyncio
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel
from agentscope.formatter import OpenAIChatFormatter

model = OpenAIChatModel(model_name="gpt-4o-mini", api_key="test")
formatter = OpenAIChatFormatter()

agent = ReActAgent(
    name="TestAgent",
    sys_prompt="You are a helpful assistant.",
    model=model,
    formatter=formatter
)

print(agent.sys_prompt)
