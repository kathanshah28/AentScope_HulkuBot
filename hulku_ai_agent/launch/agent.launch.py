"""Launch file for the HulkuBot AI Agent."""

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory('hulku_ai_agent'),
        'config',
        'agent_config.yaml'
    )

    return LaunchDescription([
        Node(
            package='hulku_ai_agent',
            executable='agent_node',
            name='hulku_agent_node',
            output='screen',
            parameters=[{
                'config_file': config_file,
                # Override these via CLI: --ros-args -p provider:=ollama -p model:=llama3.1:8b
                'provider': '',    # empty = use config default
                'model': '',       # empty = use config default
                'api_key': '',     # empty = use env var
            }],
        ),
    ])
