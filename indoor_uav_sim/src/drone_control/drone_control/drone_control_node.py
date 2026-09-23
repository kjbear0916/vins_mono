#!/usr/bin/env python3
"""drone_control: MAVSDK-Python bridge node.

Connects to PX4 SITL over UDP, arms + takes off, then streams
/offboard velocity setpoints from the fused /drone/cmd_vel topic.
On `mission/command` "land" (or "-1" waypoint action), calls action.land().

Frame mapping: cmd_vel is in the Gazebo world/ENU frame
(x=east, y=north, z=up). PX4 offboard takes NED body-neutral velocities:
    v_NED = (v_enu.y, v_enu.x, -v_enu.z)
Yaw rate is left 0 (heading follows MAVSDK defaults) in this phase.

Parameters (overridable in the launch file):
  connection_url  udpin://0.0.0.0:14540
  takeoff_alt_m   1.4   (matches navigation_params cruise_offset on 1F)
  cmd_vel_topic   /drone/cmd_vel
  command_topic   /mission/command
"""
import asyncio
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from mavsdk import System
from mavsdk.offboard import VelocityNedYaw
from mavsdk.action import ActionError


class DroneControlNode(Node):
    def __init__(self):
        super().__init__("drone_control")

        self.declare_parameter("connection_url", "udp://0.0.0.0:14540")
        self.declare_parameter("takeoff_alt_m", 1.4)
        self.declare_parameter("cmd_vel_topic", "/drone/cmd_vel")
        self.declare_parameter("command_topic", "/mission/command")

        self.url = self.get_parameter("connection_url").value
        self.takeoff_alt = float(self.get_parameter("takeoff_alt_m").value)

        self.drone = None
        self.latest = Twist()
        self.can_stream = False
        self.offboard_started = False
        self.landing = False
        self.armed = False
        self._loop = None
        self._alt_ok = False

        self.cmd_sub = self.create_subscription(
            Twist, self.get_parameter("cmd_vel_topic").value, self.on_cmd, 10)

        self.command_sub = self.create_subscription(
            String, self.get_parameter("command_topic").value, self.on_command, 10)

        # tread lightly: MAVSDK is asyncio; run its event loop on a worker
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()
        self.get_logger().info(f"drone_control connecting to {self.url}")

    # ---- ROS side ---------------------------------------------------------
    def on_cmd(self, msg: Twist):
        self.latest = msg

    def on_command(self, msg: String):
        cmd = msg.data.strip().lower()
        if cmd == "land" and not self.landing:
            self.landing = True
            self.get_logger().info("Land command received")
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._land(), self._loop)

    # ---- MAVSDK side ------------------------------------------------------
    def _run_async(self):
        asyncio.run(self._main())

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self.drone = System()
        await self.drone.connect(system_address=self.url)

        await self._wait_health()
        await self._arm_takeoff()
        await self._offboard_stream()

    async def _wait_health(self):
        self.get_logger().info("waiting for vehicle connection...")
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                break
        self.get_logger().info("connected; waiting for health...")
        async for health in self.drone.telemetry.health():
            ok = health.is_armable and health.is_local_position_ok
            if ok:
                break
        self.get_logger().info("vehicle is armable")

    async def _arm_takeoff(self):
        self.get_logger().info("arming + takeoff")
        await self.drone.action.arm()
        self.armed = True
        await self.drone.action.takeoff()
        self.get_logger().info(f"takeoff commanded to {self.takeoff_alt} m")

    async def _offboard_stream(self):
        # wait until we're at target altitude before engaging offboard
        while not self.landing:
            pos = await self.drone.telemetry.position().__anext__()
            rel = pos.relative_altitude_m or 0.0
            if rel >= self.takeoff_alt - 0.3:
                break
            await asyncio.sleep(0.2)
        self.get_logger().info("altitude reached; starting offboard velocity stream")

        if self.landing:
            return
        await self.drone.offboard.set_velocity_ned(VelocityNedYaw(0, 0, 0, 0))
        await self.drone.offboard.start()
        self.offboard_started = True
        self.can_stream = True
        self.get_logger().info("offboard active")

        while not self.landing:
            vx, vy, vz = self.latest.linear.x, self.latest.linear.y, self.latest.linear.z
            ned = VelocityNedYaw(vy, vx, -vz, 0.0)
            try:
                await self.drone.offboard.set_velocity_ned(ned)
            except Exception as e:
                self.get_logger().warn(f"set_velocity_ned: {e}")
            await asyncio.sleep(0.05)

    async def _land(self):
        try:
            await self.drone.offboard.set_velocity_ned(VelocityNedYaw(0, 0, 0, 0))
            await asyncio.sleep(0.3)
            await self.drone.action.land()
            self.get_logger().info("landing")
        except ActionError as e:
            self.get_logger().error(f"land failed: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = DroneControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()