"""Move robot arm joints to target angles via MoveIt planning + execution."""

import math
import rclpy
from hulku_ai_agent.tools.base_tool import BaseTool, ToolResult


class MoveJointsTool(BaseTool):
    name = "move_joints"
    description = (
        "Move the robot arm joints to specific target angles in degrees. "
        "Provide a list of 5 joint angles. Use -402 for any joint you want to keep unchanged. "
        "Joint indices: 0=Base, 1-3=Intermediate, 4=Wrist."
    )
    parameters = {
        "type": "object",
        "properties": {
            "joint_angles": {
                "type": "array",
                "items": {"type": "number"},
                "description": "List of 5 target joint angles in degrees. Use -402 for unchanged joints.",
            }
        },
        "required": ["joint_angles"],
    }

    def __init__(self, node, plan_client, execute_client, joint_names, arm_group):
        self._node = node
        self._plan_client = plan_client
        self._execute_client = execute_client
        self._joint_names = joint_names
        self._arm_group = arm_group

    def execute(self, joint_angles: list = None, **kwargs) -> ToolResult:
        if joint_angles is None:
            return ToolResult(False, "Missing required parameter: joint_angles")

        from moveit_msgs.srv import GetMotionPlan
        from moveit_msgs.action import ExecuteTrajectory
        from moveit_msgs.msg import MotionPlanRequest, Constraints, JointConstraint
        from sensor_msgs.msg import JointState

        dof = len(self._joint_names)
        if len(joint_angles) != dof:
            return ToolResult(False, f"Expected {dof} joint angles, got {len(joint_angles)}")

        # Get current joint state for -402 handling
        current_state = self._node.current_joint_state
        if current_state is None:
            return ToolResult(False, "Joint state not received yet. Is the robot running?")

        js_map = dict(zip(current_state.name, current_state.position))

        # Convert degrees to radians, preserving current for -402
        joint_rad = []
        for name, v in zip(self._joint_names, joint_angles):
            if v == -402:
                joint_rad.append(js_map.get(name, 0.0))
            else:
                joint_rad.append(math.radians(v))

        # Build MoveIt plan request
        constraints = Constraints()
        for name, value in zip(self._joint_names, joint_rad):
            jc = JointConstraint()
            jc.joint_name = name
            jc.position = value
            jc.tolerance_above = 0.01
            jc.tolerance_below = 0.01
            jc.weight = 1.0
            constraints.joint_constraints.append(jc)

        mpr = MotionPlanRequest()
        mpr.group_name = self._arm_group
        mpr.goal_constraints.append(constraints)
        mpr.allowed_planning_time = 5.0

        req = GetMotionPlan.Request()
        req.motion_plan_request = mpr

        # Plan
        future = self._plan_client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future, timeout_sec=10.0)

        res = future.result()
        if res is None or res.motion_plan_response.error_code.val != 1:
            return ToolResult(False, "Motion planning failed. Target may be unreachable.")

        # Execute
        goal = ExecuteTrajectory.Goal()
        goal.trajectory = res.motion_plan_response.trajectory

        send_future = self._execute_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self._node, send_future, timeout_sec=10.0)

        handle = send_future.result()
        if not handle.accepted:
            return ToolResult(False, "Trajectory execution was rejected by the controller.")

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self._node, result_future, timeout_sec=30.0)

        if result_future.result().result.error_code.val != 1:
            return ToolResult(False, "Trajectory execution failed.")

        return ToolResult(True, f"Successfully moved joints to {joint_angles} degrees.")
