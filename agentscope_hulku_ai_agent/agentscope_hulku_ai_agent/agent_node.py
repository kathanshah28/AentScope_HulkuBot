#!/usr/bin/env python3
"""
HulkuBot AI Agent Node — AgentScope Full Integration.

ROS 2 action server that receives natural language commands and
executes them using an AgentScope ReActAgent with:

  - Model:            Mistral AI / devstral-latest (via OpenAI-compat endpoint)
  - Short-term mem:   AgentScope InMemoryMemory (dialogue history)
  - Long-term mem:    HulkuLongTermMemory (ChromaDB episodic + declarative)
  - Tools:            Legacy BaseTool instances wrapped into AgentScope Toolkit
  - Feedback:         ROS 2 ArmTask.Feedback published after every tool call
"""

import os
import logging
import yaml
import asyncio

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient

from custom_interfaces.action import ArmTask
from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.action import ExecuteTrajectory
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

import nest_asyncio
import agentscope
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import OpenAIChatModel, GeminiChatModel, OllamaChatModel
from agentscope.formatter import (
    OpenAIChatFormatter, GeminiChatFormatter, OllamaChatFormatter
)
from agentscope_hulku_ai_agent.mistral_formatter import MistralChatFormatter

from hulku_ai_agent.tools import (
    MoveJointsTool, MoveGripperTool, BuzzerTool,
    TorqueModeTool, GetJointStatesTool, GoHomeTool,
    WaitTool, PrintMessageTool, RGBLightTool,
)

from agentscope_hulku_ai_agent.tool_wrapper import create_toolkit
from agentscope_hulku_ai_agent.hulku_long_term_memory import HulkuLongTermMemory

# Apply nest_asyncio globally so rclpy's synchronous action callbacks can
# drive asyncio event loops without raising "loop already running" errors.
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger('agentscope_hulku_ai_agent')


class HulkuAgentNode(Node):
    def __init__(self):
        super().__init__('hulku_agent_node')

        # ==============================
        # PARAMETERS
        # ==============================
        self.declare_parameter('config_file', '')
        self.declare_parameter('provider', '')
        self.declare_parameter('model', '')
        self.declare_parameter('api_key', '')

        config_file = self.get_parameter('config_file').value

        # Load config
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self._config = yaml.safe_load(f)
        else:
            from ament_index_python.packages import get_package_share_directory
            share_dir = get_package_share_directory('agentscope_hulku_ai_agent')
            default_config = os.path.join(share_dir, 'config', 'agent_config.yaml')
            if os.path.exists(default_config):
                with open(default_config, 'r') as f:
                    self._config = yaml.safe_load(f)
            else:
                self.get_logger().error("No config file found!")
                raise RuntimeError("Config file not found")

        agent_config = self._config.get('agent', {})
        robot_config = self._config.get('robot', {})

        # ROS param overrides take priority over YAML config
        provider = (
            self.get_parameter('provider').value
            or agent_config.get('default_provider', 'mistral')
        )
        model = (
            self.get_parameter('model').value
            or agent_config.get('default_model', 'devstral-latest')
        )
        api_key = self.get_parameter('api_key').value or ''

        self._system_prompt = agent_config.get('system_prompt', 'You are a robot assistant.')
        self._max_steps     = agent_config.get('max_steps', 10)

        # Robot config
        self._arm_group     = robot_config.get('arm_group', 'arm')
        self._gripper_group = robot_config.get('gripper_group', 'gripper')
        self._joint_names   = robot_config.get('joint_names', [])
        self._gripper_joint = robot_config.get('gripper_joint', 'Rlink1_Joint')

        self.get_logger().info(f"Provider: {provider} | Model: {model}")
        self.get_logger().info(f"Arm group: {self._arm_group} | Joints: {self._joint_names}")

        # ==============================
        # JOINT STATE SUBSCRIBER
        # ==============================
        self.current_joint_state = None
        self.create_subscription(
            JointState, '/joint_states', self._joint_state_cb, 10
        )

        # ==============================
        # MOVEIT INTERFACES
        # ==============================
        self.get_logger().info("Waiting for MoveIt services...")
        self._plan_client = self.create_client(GetMotionPlan, '/plan_kinematic_path')
        self._plan_client.wait_for_service(timeout_sec=30.0)

        self._execute_client = ActionClient(self, ExecuteTrajectory, '/execute_trajectory')
        self._execute_client.wait_for_server(timeout_sec=30.0)
        self.get_logger().info("MoveIt services connected!")

        # ==============================
        # GPIO PUBLISHER
        # ==============================
        self._gpio_pub = self.create_publisher(
            Float64MultiArray, '/gpio_controller/commands', 10
        )
        self._gpio_state = [0.0, 1.0, 0.0, 0.0, 0.0]  # [buzzer, torque, r, g, b]

        # ==============================
        # AGENTSCOPE INIT
        # ==============================
        agentscope.init(project="HulkuBot", name="hulku_agent")

        # ==============================
        # MODEL + FORMATTER
        # ==============================
        provider_lower = provider.lower()
        if provider_lower == "gemini":
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            self._model     = GeminiChatModel(model_name=model, api_key=key)
            self._formatter = GeminiChatFormatter()

        elif provider_lower in ("ollama", "ollama_local"):
            self._model     = OllamaChatModel(model_name=model)
            self._formatter = OllamaChatFormatter()

        else:
            # OpenAI-compatible providers: mistral, groq, openrouter, nvidia, openai, etc.
            client_kwargs = {}
            use_mistral_formatter = False

            if provider_lower == "mistral":
                client_kwargs["base_url"] = "https://api.mistral.ai/v1"
                key = api_key or os.environ.get("MISTRAL_API_KEY", "")
                use_mistral_formatter = True
            elif provider_lower == "groq":
                client_kwargs["base_url"] = "https://api.groq.com/openai/v1"
                key = api_key or os.environ.get("GROQ_API_KEY", "")
            elif provider_lower == "openrouter":
                client_kwargs["base_url"] = "https://openrouter.ai/api/v1"
                key = api_key or os.environ.get("OPEN_ROUTER_KEY", "")
            elif provider_lower == "nvidia":
                client_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
                key = api_key or os.environ.get("NVIDIA_API_KEY", "")
            else:
                # Generic OpenAI or unknown provider
                key = api_key or os.environ.get("OPENAI_API_KEY", "")

            self._model = OpenAIChatModel(
                model_name=model,
                api_key=key,
                client_kwargs=client_kwargs if client_kwargs else None,
            )
            # Mistral rejects the 'name' field; use the stripped formatter
            if use_mistral_formatter:
                self._formatter = MistralChatFormatter()
            else:
                self._formatter = OpenAIChatFormatter()

        # ==============================
        # AGENTSCOPE MEMORY
        # ==============================
        # Short-term: AgentScope manages dialogue history natively
        self._short_term_memory = InMemoryMemory()

        # Long-term: ChromaDB-backed episodic + declarative memory
        self._long_term_memory = HulkuLongTermMemory(
            db_path=os.path.expanduser("~/.hulku_memory_db"),
            similarity_threshold=0.75,
        )

        # ==============================
        # TOOLKIT (legacy tools → AgentScope)
        # ==============================
        # We will store the current goal_handle here so the postprocess_func
        # can publish feedback without needing it passed as a parameter.
        self._current_goal_handle = None

        def _tool_feedback_hook(tool_use_block, tool_response):
            """
            Called by AgentScope after every tool execution.
            Publishes a ROS 2 ArmTask.Feedback with the tool name + result snippet.
            """
            if self._current_goal_handle is None:
                return None  # Return None = keep tool_response unchanged

            try:
                tool_name = getattr(tool_use_block, 'name', 'unknown_tool')
                # Extract text from ToolResponse
                result_text = ""
                for block in tool_response.content:
                    if hasattr(block, 'text'):
                        result_text = block.text
                        break
                    elif isinstance(block, dict):
                        result_text = block.get('text', '')
                        break

                feedback_msg = ArmTask.Feedback()
                feedback_msg.state = f"[{tool_name}] {result_text[:120]}"
                self._current_goal_handle.publish_feedback(feedback_msg)
            except Exception as exc:
                self.get_logger().warn(f"Feedback hook error: {exc}")

            return None  # Do not modify the tool response

        # Build legacy tool instances
        move_joints_tool = MoveJointsTool(
            self, self._plan_client, self._execute_client,
            self._joint_names, self._arm_group
        )

        def _move_joints_helper(angles):
            return move_joints_tool.execute(joint_angles=angles)

        legacy_tools = [
            move_joints_tool,
            MoveGripperTool(
                self, self._plan_client, self._execute_client,
                self._gripper_joint, self._gripper_group
            ),
            BuzzerTool(self, self._gpio_pub, self._gpio_state),
            TorqueModeTool(self, self._gpio_pub, self._gpio_state),
            GetJointStatesTool(self, self._joint_names),
            GoHomeTool(_move_joints_helper),
            WaitTool(),
            PrintMessageTool(self),
            RGBLightTool(self, self._gpio_pub, self._gpio_state),
            # NOTE: SaveMemoryTool removed — replaced by LongTermMemory.record_to_memory()
        ]

        self._toolkit = create_toolkit(
            legacy_tools,
            postprocess_func=_tool_feedback_hook,
        )

        # ==============================
        # REACT AGENT
        # ==============================
        self._agent = ReActAgent(
            name="HulkuBot",
            sys_prompt=self._system_prompt,
            model=self._model,
            formatter=self._formatter,
            toolkit=self._toolkit,
            memory=self._short_term_memory,
            long_term_memory=self._long_term_memory,
            long_term_memory_mode="both",   # auto-retrieve + agent can call tools
            max_iters=self._max_steps,
        )

        # ==============================
        # ACTION SERVER
        # ==============================
        self._action_server = ActionServer(
            self, ArmTask, 'arm_command', self._execute_callback
        )

        self.get_logger().info("🤖 HulkuBot AgentScope Node is ready!")
        self.get_logger().info(
            f"   Model: {provider}/{model} | Max steps: {self._max_steps}"
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _joint_state_cb(self, msg: JointState) -> None:
        self.current_joint_state = msg

    def publish_feedback(self, state_str: str):
        """Publishes feedback directly, e.g. for print_message tool."""
        if self._current_goal_handle is not None:
            from custom_interfaces.action import ArmTask
            feedback = ArmTask.Feedback()
            feedback.state = state_str
            self._current_goal_handle.publish_feedback(feedback)
        else:
            self.get_logger().info(f"[Live Feedback] {state_str}")


    def _execute_callback(self, goal_handle):
        """Handle incoming ArmTask action goals."""
        user_message = goal_handle.request.json_command
        self.get_logger().info(f"📩 Received command: {user_message}")

        # Store goal handle so postprocess_func can publish feedback
        self._current_goal_handle = goal_handle

        try:
            # Publish initial feedback
            feedback = ArmTask.Feedback()
            feedback.state = "🔄 Processing..."
            goal_handle.publish_feedback(feedback)

            # Run the async agent in the current (potentially running) event loop
            async def run_agent():
                return await self._agent.reply(
                    Msg(name="user", content=user_message, role="user")
                )

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            reply_msg = loop.run_until_complete(run_agent())
            result_text = (
                reply_msg.content
                if reply_msg and isinstance(reply_msg.content, str)
                else str(reply_msg)
            )

            feedback.state = "✅ Task complete."
            goal_handle.publish_feedback(feedback)

            self.get_logger().info(f"✅ Agent result: {result_text}")

            goal_handle.succeed()
            result = ArmTask.Result()
            result.success = True
            result.message = str(result_text)
            return result

        except Exception as exc:
            self.get_logger().error(f"❌ Agent error: {exc}")
            goal_handle.abort()
            result = ArmTask.Result()
            result.success = False
            result.message = f"Agent error: {exc}"
            return result

        finally:
            self._current_goal_handle = None


def main(args=None):
    rclpy.init(args=args)
    node = HulkuAgentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
