from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_spawn_controllers_launch


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("dofbot_urdf", package_name="hulkubot_moveit_config").to_moveit_configs()
    spawn_controllers_launch = generate_spawn_controllers_launch(moveit_config)

    # Custom: we also need to spawn the gpio_controller
    gpio_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gpio_controller", "-c", "/controller_manager"],
    )

    # Return a LaunchDescription that contains everything from the auto-generated launch + our custom node
    # generate_spawn_controllers_launch returns a LaunchDescription
    spawn_controllers_launch.add_action(gpio_controller_spawner)
    return spawn_controllers_launch
