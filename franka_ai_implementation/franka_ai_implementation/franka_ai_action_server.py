#!/usr/bin/env python3

import json
import math
import subprocess  # <--- ADDED for running external scripts

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient

from custom_interfaces.action import ArmTask

from moveit_msgs.srv import GetMotionPlan
from moveit_msgs.action import ExecuteTrajectory
from moveit_msgs.msg import (
    MotionPlanRequest,
    Constraints,
    JointConstraint
)

from sensor_msgs.msg import JointState


class FrankaActionServer(Node):

    def __init__(self):
        super().__init__('franka_action_server')

        # ==========================================================
        # PARAMETERS
        # ==========================================================
        self.declare_parameter('arm_planning_group', '')
        self.declare_parameter('gripper_planning_group', 'gripper')
        self.declare_parameter('dof', 0)
        self.declare_parameter('joint_names', [''])

        self.arm_group = self.get_parameter('arm_planning_group').value
        self.gripper_group = self.get_parameter('gripper_planning_group').value
        self.joint_names = self.get_parameter('joint_names').value
        self.dof = self.get_parameter('dof').value

        if (
            not self.arm_group
            or self.joint_names == ['']
            or self.dof == 0
        ):
            raise RuntimeError(
                'Missing required parameters: arm_planning_group, joint_names, dof'
            )

        if len(self.joint_names) != self.dof:
            raise RuntimeError(
                f'dof={self.dof} but {len(self.joint_names)} joint names provided'
            )

        self.get_logger().info(f'Arm group: {self.arm_group}')
        self.get_logger().info(f'Gripper group: {self.gripper_group}')
        self.get_logger().info(f'Joint names: {self.joint_names}')

        # ==========================================================
        # ACTION SERVER
        # ==========================================================
        self._action_server = ActionServer(
            self,
            ArmTask,
            'arm_command',
            self.execute_callback
        )

        # ==========================================================
        # MOVEIT INTERFACES
        # ==========================================================
        self.plan_client = self.create_client(
            GetMotionPlan,
            '/plan_kinematic_path'
        )
        self.plan_client.wait_for_service()

        self.execute_client = ActionClient(
            self,
            ExecuteTrajectory,
            '/execute_trajectory'
        )
        self.execute_client.wait_for_server()

        # ==========================================================
        # JOINT STATES
        # ==========================================================
        self.current_joint_state = None
        self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_state_callback,
            10
        )

        self.get_logger().info('Arm + Numeric Gripper Action Server ready')

    # ==========================================================
    def joint_state_callback(self, msg):
        self.current_joint_state = msg

    # ==========================================================
    def execute_callback(self, goal_handle):
        self.get_logger().info(
            f'Received command:\n{goal_handle.request.json_command}'
        )

        try:
            command = json.loads(goal_handle.request.json_command)
            print(f"commnad action server: {command}")
        except json.JSONDecodeError:
            goal_handle.abort()
            return self._result(False, 'Invalid JSON')

        # ------------------------------------------------------------
        # NEW LOGIC: PICK & PLACE / CLEANING TASK
        # ------------------------------------------------------------
        if 'strategy' in command:
            success, msg = self._execute_pick_place(command)
            if success:
                goal_handle.succeed()
                return self._result(True, msg)
            else:
                goal_handle.abort()
                return self._result(False, msg)
        # ------------------------------------------------------------


        # ---------------- SPAWNER ----------------
        if 'num_cubes' in command:
            success, msg = self._execute_spawner(command)
            if success:
                goal_handle.succeed()
                return self._result(True, msg)
            else:
                goal_handle.abort()
                return self._result(False, msg)
        # ------------------------------------------------

        # ---------------- ARM MOVEMENT ----------------
        if 'move' in command and command['move'] is not None:
            success, msg = self._execute_arm(command['move'])
            if not success:
                goal_handle.abort()
                return self._result(False, msg)

        # ---------------- GRIPPER MOVEMENT ----------------
        if 'gripper' in command and command['gripper'] is not None:
            print(f"gripper command: {command['gripper']}")
            success, msg = self._execute_gripper(command['gripper'][0])
            if not success:
                goal_handle.abort()
                return self._result(False, msg)

        goal_handle.succeed()
        return self._result(True, 'Command executed successfully')
    # ==========================================================
    # NEW HELPER: RUN SPAWNER NODE
    # ==========================================================
    def _execute_spawner(self, params):
        """
        Launches the random_cube_spawner.py node as a subprocess.
        """
        self.get_logger().info("--- Launching Cube Spawner Subprocess ---")
        
        # 1. Extract parameters with defaults
        # Default to 'random' if not specified
        color_mode = params.get('color_mode', 'random') 
        # Default to 'green' if manual mode but no color specified
        manual_color = params.get('manual_color', 'green')
        # Default to 0 (Infinite) if not specified
        num_cubes = int(params.get('num_cubes', 0)) 
        
        # 2. Construct the ROS 2 run command
        # Package: pick_n_place, Executable: random_cube_spawner.py
        cmd = [
            "ros2", "run", "cube_spawner", "random_cube_spawner",
            "--ros-args",
            "-p", f"color_mode:={color_mode}",
            "-p", f"num_cubes:={num_cubes}"
        ]
        
        # Only add manual_color if mode is actually manual
        if color_mode == "manual":
            cmd.extend(["-p", f"manual_color:={manual_color}"])
            
        self.get_logger().info(f"Executing: {' '.join(cmd)}")
        
        try:
            # 3. Run Blocking Call
            # NOTE: Spawner usually runs forever unless num_cubes > 0.
            # If num_cubes > 0, it stops automatically, so this blocking call will return.
            # If num_cubes == 0 (Infinite), this will block the Action Server forever!
            # Fix: We use 'timeout' for infinite mode or run non-blocking.
            
            if num_cubes > 0:
                # Finite spawning: Wait for it to finish (it auto-stops)
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.get_logger().info(f"Spawned {num_cubes} cubes successfully.")
                    return True, f"Spawned {num_cubes} {manual_color if color_mode == 'manual' else 'random'} cubes."
                else:
                    self.get_logger().error(f"Spawner Failed: {result.stderr}")
                    return False, f"Spawner script failed: {result.stderr}"
            else:
                # Infinite spawning: Launch and forget (Non-blocking)
                # We use Popen so the Action Server doesn't freeze
                subprocess.Popen(cmd)
                return True, "Spawner started in infinite mode."
                
        except Exception as e:
            return False, f"Spawner Execution Error: {str(e)}"

    # ==========================================================
    # NEW HELPER: RUN EXTERNAL CLEANER NODE
    # ==========================================================
    def _execute_pick_place(self, params):
        """
        Launches the universal_cleaner.py node as a subprocess with provided args.
        """
        self.get_logger().info("--- Launching Pick & Place Subprocess ---")
        
        # Extract parameters with defaults
        strategy = params.get('strategy', 'random')
        sort_cubes = str(params.get('sort_cubes', True)).lower() # Convert bool to 'true'/'false' string
        target_colors = params.get('target_colors', [])
        target_cube = params.get('target_cube', 'cube_0')
        
        # Format list for ROS command line: "['red', 'green']"
        # Construct the ROS 2 run command
        # NOTE: Assuming your package name is 'pick_n_place'. Change if different.
        cmd = [
            "ros2", "run", "pick_n_place", "advanced_cleaner_node",
            "--ros-args",
            "-p", "use_sim_time:=true",
            "-p", f"strategy:={strategy}",
        ]
        
        if target_colors:
            colors_str = json.dumps(target_colors)
            cmd.extend(["-p", f"target_colors:={colors_str}"])
        
        # Add target_cube only if manual mode
        if strategy == "manual":
            cmd.extend(["-p", f"target_cube:={target_cube}"])
            
        self.get_logger().info(f"Executing: {' '.join(cmd)}")
        
        try:
            # Run blocking call - this waits until cleaning is finished
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.get_logger().info("Pick & Place Task Completed.")
                return True, "Cleaning task finished successfully."
            else:
                self.get_logger().error(f"Pick & Place Failed: {result.stderr}")
                return False, f"Cleaner script failed: {result.stderr}"
                
        except Exception as e:
            return False, f"Subprocess Execution Error: {str(e)}"

    # ==========================================================
    def _execute_arm(self, joint_deg):
        if not isinstance(joint_deg, list) or len(joint_deg) != self.dof:
            return False, f'Expected {self.dof} arm joint values'

        if self.current_joint_state is None:
            return False, 'Joint state not received yet'

        js_map = dict(zip(
            self.current_joint_state.name,
            self.current_joint_state.position
        ))

        joint_rad = []
        for name, v in zip(self.joint_names, joint_deg):
            if v == -402:
                joint_rad.append(js_map[name])
            else:
                joint_rad.append(math.radians(v))

        constraints = Constraints()
        for name, value in zip(self.joint_names, joint_rad):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = value
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            constraints.joint_constraints.append(jc)

        mpr = MotionPlanRequest()
        mpr.group_name = self.arm_group
        mpr.goal_constraints.append(constraints)
        mpr.allowed_planning_time = 5.0

        req = GetMotionPlan.Request()
        req.motion_plan_request = mpr

        future = self.plan_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        res = future.result()
        if res is None or res.motion_plan_response.error_code.val != 1:
            return False, 'Arm motion planning failed'

        return self._execute_trajectory(res.motion_plan_response.trajectory)

    # ==========================================================
    def _execute_gripper(self, width):
        if not isinstance(width, (int, float)):
            return False, 'Gripper value must be numeric (meters)'

        # Clamp width
        width = max(0.0, min(0.04, float(width)))
        finger_pos = width

        constraints = Constraints()
        for joint in ['panda_finger_joint1','panda_finger_joint2']:
            jc = JointConstraint()
            jc.joint_name = joint
            jc.position = finger_pos
            jc.tolerance_above = 0.001
            jc.tolerance_below = 0.001
            jc.weight = 1.0
            constraints.joint_constraints.append(jc)

        mpr = MotionPlanRequest()
        mpr.group_name = self.gripper_group
        mpr.goal_constraints.append(constraints)
        mpr.allowed_planning_time = 2.0

        req = GetMotionPlan.Request()
        req.motion_plan_request = mpr

        future = self.plan_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        res = future.result()
        if res is None or res.motion_plan_response.error_code.val != 1:
            return False, 'Gripper motion planning failed'

        return self._execute_trajectory(res.motion_plan_response.trajectory)

    # ==========================================================
    def _execute_trajectory(self, trajectory):
        goal = ExecuteTrajectory.Goal()
        goal.trajectory = trajectory

        send_future = self.execute_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)

        handle = send_future.result()
        if not handle.accepted:
            return False, 'Execution rejected'

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        if result_future.result().result.error_code.val != 1:
            return False, 'Execution failed'

        return True, 'Executed'

    # ==========================================================
    def _result(self, success, message):
        result = ArmTask.Result()
        result.success = success
        result.message = message
        return result


def main(args=None):
    rclpy.init(args=args)
    node = FrankaActionServer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()