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

from hulku_ai_agent.agent_core import AgentCore
from hulku_ai_agent.tools import (
    ToolRegistry,
    MoveJointsTool, MoveGripperTool, BuzzerTool,
    TorqueModeTool, GetJointStatesTool, GoHomeTool, WaitTool, PrintMessageTool, RGBLightTool
)

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
        # TOOL REGISTRY
        # ==============================
        self._registry = ToolRegistry()

        # GPIO controller publisher (shared by buzzer, torque, RGB tools)
        self._gpio_pub = self.create_publisher(
            Float64MultiArray, '/gpio_controller/commands', 10)
        self._gpio_state = [0.0, 1.0, 0.0, 0.0, 0.0]  # [buzzer, torque, r, g, b]

        move_joints = MoveJointsTool(
            self, self._plan_client, self._execute_client,
            self._joint_names, self._arm_group
        )
        self._registry.register(move_joints)
        self._registry.register(MoveGripperTool(
            self, self._plan_client, self._execute_client,
            self._gripper_joint, self._gripper_group
        ))
        self._registry.register(BuzzerTool(self, self._gpio_pub, self._gpio_state))
        self._registry.register(TorqueModeTool(self, self._gpio_pub, self._gpio_state))
        self._registry.register(GetJointStatesTool(self, self._joint_names))
        self._registry.register(GoHomeTool(move_joints))
        self._registry.register(WaitTool())
        self._registry.register(PrintMessageTool(self))
        self._registry.register(RGBLightTool(self, self._gpio_pub, self._gpio_state))

        self.get_logger().info(f"Registered tools:\n{self._registry.list_tools()}")

        # ==============================
        # LLM BACKEND
        # ==============================
        self._llm_backend = self._create_backend(provider, model, api_key)

        # ==============================
        # AGENT CORE
        # ==============================
        self._agent = AgentCore(
            llm_backend=self._llm_backend,
            tool_registry=self._registry,
            system_prompt=self._system_prompt,
            max_steps=self._max_steps,
            # We don't pass feedback_cb here, we will inject it per-request
        )

        # ==============================
        # ACTION SERVER
        # ==============================
        self._action_server = ActionServer(
            self, ArmTask, 'arm_command', self._execute_callback
        )

        self.get_logger().info("🤖 HulkuBot AI Agent is ready!")

    def _create_backend(self, provider: str, model: str, api_key: str):
        """Create the appropriate LLM backend based on provider string."""
        provider = provider.lower()

        if provider == "gemini":
            from hulku_ai_agent.llm_backends.gemini_backend import GeminiBackend
            key = api_key or os.environ.get("GEMINI_API_KEY", "")
            self.get_logger().info(f"Using Gemini backend: {model}")
            return GeminiBackend(model_name=model, api_key=key)

        elif provider == "groq":
            from hulku_ai_agent.llm_backends.groq_backend import GroqBackend
            key = api_key or os.environ.get("GROQ_API_KEY", "")
            self.get_logger().info(f"Using Groq backend: {model}")
            return GroqBackend(model_name=model, api_key=key)

        elif provider == "ollama":
            from hulku_ai_agent.llm_backends.ollama_backend import OllamaBackend
            self.get_logger().info(f"Using local Ollama backend: {model}")
            return OllamaBackend(model_name=model)
            
        elif provider == "ollama_cloud":
            from hulku_ai_agent.llm_backends.ollama_cloud_backend import OllamaCloudBackend
            key = api_key or os.environ.get("OLLAMA_CLOUD_API_KEY", "")
            self.get_logger().info(f"Using Ollama Cloud backend: {model}")
            return OllamaCloudBackend(model_name=model, api_key=key)

        else:
            raise ValueError(f"Unknown LLM provider: '{provider}'. Use 'gemini', 'groq', 'ollama', or 'ollama_cloud'.")

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

            # Define a local callback to publish live feedback from the agent
            def live_feedback_cb(state_str):
                feedback.state = state_str
                goal_handle.publish_feedback(feedback)

            # Temporarily inject the callback for this run
            self._agent._feedback_cb = live_feedback_cb

            # Run the ReAct agent loop
            result_text = self._agent.run(user_message)

            # Clean up callback
            self._agent._feedback_cb = None

            self.get_logger().info(f"✅ Agent result: {result_text}")

            goal_handle.succeed()
            result = ArmTask.Result()
            result.success = True
            result.message = result_text
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
