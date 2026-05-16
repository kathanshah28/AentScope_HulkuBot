#!/usr/bin/env python3
"""
HulkuBot AI Agent Node.

ROS 2 action server that receives natural language commands and
executes them using a ReAct tool-calling loop with LLM backends.
"""

import os
import logging
import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient

from custom_interfaces.action import ArmTask
from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.action import ExecuteTrajectory
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

import agentscope
from agentscope.agent import ReActAgent
from agentscope.message import Msg

from hulku_ai_agent.memory.memory_manager import MemoryManager
from hulku_ai_agent.tools import (
    MoveJointsTool, MoveGripperTool, BuzzerTool,
    TorqueModeTool, GetJointStatesTool, GoHomeTool, WaitTool, PrintMessageTool, RGBLightTool
)
from agentscope_hulku_ai_agent.tool_wrapper import create_toolkit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger('hulku_ai_agent')


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
            # Try loading from the installed share directory
            from ament_index_python.packages import get_package_share_directory
            share_dir = get_package_share_directory('hulku_ai_agent')
            default_config = os.path.join(share_dir, 'config', 'agent_config.yaml')
            if os.path.exists(default_config):
                with open(default_config, 'r') as f:
                    self._config = yaml.safe_load(f)
            else:
                self.get_logger().error("No config file found!")
                raise RuntimeError("Config file not found")

        agent_config = self._config.get('agent', {})
        robot_config = self._config.get('robot', {})

        # Allow ROS param overrides
        provider = self.get_parameter('provider').value or agent_config.get('default_provider', 'gemini')
        model = self.get_parameter('model').value or agent_config.get('default_model', 'gemini-2.0-flash')
        api_key = self.get_parameter('api_key').value or ''

        self._system_prompt = agent_config.get('system_prompt', 'You are a robot assistant.')
        self._max_steps = agent_config.get('max_steps', 5)

        # Robot config
        self._arm_group = robot_config.get('arm_group', 'arm')
        self._gripper_group = robot_config.get('gripper_group', 'gripper')
        self._joint_names = robot_config.get('joint_names', [])
        self._gripper_joint = robot_config.get('gripper_joint', 'Rlink1_Joint')

        self.get_logger().info(f"Provider: {provider} | Model: {model}")
        self.get_logger().info(f"Arm group: {self._arm_group} | Joints: {self._joint_names}")

        # ==============================
        # JOINT STATE SUBSCRIBER
        # ==============================
        self.current_joint_state = None
        self.create_subscription(JointState, '/joint_states', self._joint_state_cb, 10)

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
        # AGENTSCOPE INITIALIZATION
        # ==============================
        agentscope.init(project="HulkuBot", name="hulku_agent")

        self.get_logger().info(f"Provider: {provider} | Model: {model}")

        # Initialize the model and formatter
        provider = provider.lower()
        if provider == "gemini":
            from agentscope.model import GeminiChatModel
            from agentscope.formatter import GeminiChatFormatter
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            self._model = GeminiChatModel(model_name=model, api_key=key)
            self._formatter = GeminiChatFormatter()
        elif provider in ["ollama", "ollama_cloud"]:
            from agentscope.model import OllamaChatModel
            from agentscope.formatter import OllamaChatFormatter
            self._model = OllamaChatModel(model_name=model)
            self._formatter = OllamaChatFormatter()
        else:
            # Handle custom endpoints via OpenAIChatModel
            from agentscope.model import OpenAIChatModel
            from agentscope.formatter import OpenAIChatFormatter

            client_kwargs = {}
            if provider == "groq":
                client_kwargs["base_url"] = "https://api.groq.com/openai/v1"
                key = api_key or os.environ.get("GROQ_API_KEY", "")
            elif provider == "openrouter":
                client_kwargs["base_url"] = "https://openrouter.ai/api/v1"
                key = api_key or os.environ.get("OPEN_ROUTER_KEY", "")
            elif provider == "mistral":
                client_kwargs["base_url"] = "https://api.mistral.ai/v1"
                key = api_key or os.environ.get("MISTRAL_API_KEY", "")
            elif provider == "nvidia":
                client_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
                key = api_key or os.environ.get("NVIDIA_API_KEY", "")
            else:
                key = api_key or os.environ.get("API_KEY", "")

            self._model = OpenAIChatModel(
                model_name=model,
                api_key=key,
                client_kwargs=client_kwargs if client_kwargs else None
            )
            self._formatter = OpenAIChatFormatter()

        # GPIO controller publisher (shared by buzzer, torque, RGB tools)
        self._gpio_pub = self.create_publisher(
            Float64MultiArray, '/gpio_controller/commands', 10)
        self._gpio_state = [0.0, 1.0, 0.0, 0.0, 0.0]  # [buzzer, torque, r, g, b]

        # ==============================
        # MEMORY MANAGER
        # ==============================
        self._memory_manager = MemoryManager(config=self._config)

        # ==============================
        # TOOLKIT
        # ==============================
        move_joints_tool = MoveJointsTool(
            self, self._plan_client, self._execute_client,
            self._joint_names, self._arm_group
        )

        def move_joints(angles):
            # Helper for GoHome
            return move_joints_tool.execute(joint_angles=angles)

        from hulku_ai_agent.tools.save_memory import SaveMemoryTool
        legacy_tools = [
            move_joints_tool,
            MoveGripperTool(
                self, self._plan_client, self._execute_client,
                self._gripper_joint, self._gripper_group
            ),
            BuzzerTool(self, self._gpio_pub, self._gpio_state),
            TorqueModeTool(self, self._gpio_pub, self._gpio_state),
            GetJointStatesTool(self, self._joint_names),
            GoHomeTool(move_joints),
            WaitTool(),
            PrintMessageTool(self),
            RGBLightTool(self, self._gpio_pub, self._gpio_state),
            SaveMemoryTool(self._memory_manager)
        ]

        self._toolkit = create_toolkit(legacy_tools)

        # ==============================
        # AGENT CORE
        # ==============================
        self._agent = ReActAgent(
            name="HulkuBot",
            sys_prompt=self._system_prompt,
            model=self._model,
            formatter=self._formatter,
            toolkit=self._toolkit,
            max_iters=self._max_steps
        )

        # Enable nest_asyncio to support nested event loops
        import nest_asyncio
        nest_asyncio.apply()

        # ==============================
        # ACTION SERVER
        # ==============================
        self._action_server = ActionServer(
            self, ArmTask, 'arm_command', self._execute_callback
        )

        self.get_logger().info("🤖 HulkuBot AI Agent is ready!")

    def _joint_state_cb(self, msg):
        self.current_joint_state = msg

    def _execute_callback(self, goal_handle):
        """Handle incoming ArmTask action goals."""
        user_message = goal_handle.request.json_command
        self.get_logger().info(f"📩 Received: {user_message}")

        try:
            # Publish initial feedback
            feedback = ArmTask.Feedback()
            feedback.state = "Processing..."
            goal_handle.publish_feedback(feedback)

            # AgentScope execution
            import asyncio

            # ReActAgent.reply is an async method
            async def run_agent():
                return await self._agent.reply(Msg(name="user", content=user_message, role="user"))

            # Since rclpy action servers in Python are typically synchronous unless customized,
            # we need to run the asyncio event loop for the agent.
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # If running in an async context, this needs to be handled properly
                # We assume rclpy action server threads provide their own context here,
                # but we can fallback to run_coroutine_threadsafe if needed.
                import nest_asyncio
                nest_asyncio.apply()

            reply_msg = loop.run_until_complete(run_agent())
            result_text = reply_msg.content if reply_msg and reply_msg.content else str(reply_msg)

            feedback.state = "Task complete."
            goal_handle.publish_feedback(feedback)

            self.get_logger().info(f"✅ Agent result: {result_text}")

            goal_handle.succeed()
            result = ArmTask.Result()
            result.success = True
            result.message = str(result_text)
            return result

        except Exception as e:
            self.get_logger().error(f"❌ Agent error: {str(e)}")
            goal_handle.abort()
            result = ArmTask.Result()
            result.success = False
            result.message = f"Agent error: {str(e)}"
            return result


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
