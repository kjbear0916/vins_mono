#!/usr/bin/env python3
"""
Waypoint flight controller for VINS-Mono simulation experiments.
Generates circular or figure-8 trajectories at specified speeds.

Usage:
    python3 waypoint_flight.py --trajectory circle --speed 1.5 --radius 5.0
    python3 waypoint_flight.py --trajectory figure8 --speed 1.5
"""

import rospy
import math
import argparse
import sys
import time
from geometry_msgs.msg import PoseStamped, Twist
from mavros_msgs.msg import State, PositionTarget
from mavros_msgs.srv import SetMode, CommandBool
from sensor_msgs.msg import Image


class WaypointController:
    def __init__(self, trajectory='circle', speed=1.5, radius=5.0, altitude=3.0,
                 pre_armed=False):
        rospy.init_node('waypoint_controller', anonymous=True)

        self.trajectory = trajectory
        self.speed = speed
        self.radius = radius
        self.altitude = altitude
        self.pre_armed = pre_armed

        # State
        self.current_state = State()
        self.current_pose = None
        self.offboard_ready = False
        self.start_time = None

        # Publishers
        self.setpoint_pub = rospy.Publisher(
            '/mavros/setpoint_raw/local', PositionTarget, queue_size=10)

        # Subscribers
        rospy.Subscriber('/mavros/state', State, self.state_cb)
        rospy.Subscriber('/mavros/local_position/pose',
                         PoseStamped, self.pose_cb)

        # Services
        rospy.wait_for_service('/mavros/set_mode')
        rospy.wait_for_service('/mavros/cmd/arming')
        self.set_mode = rospy.ServiceProxy('/mavros/set_mode', SetMode)
        self.arm = rospy.ServiceProxy('/mavros/cmd/arming', CommandBool)

        rospy.loginfo(f"Trajectory: {self.trajectory}, Speed: {self.speed} m/s, "
                      f"Radius: {self.radius} m, Altitude: {self.altitude} m")

    def state_cb(self, msg):
        self.current_state = msg

    def pose_cb(self, msg):
        self.current_pose = msg.pose

    def get_circle_position(self, t):
        """Calculate position on circular trajectory."""
        angle = self.speed / self.radius * t
        x = self.radius * math.cos(angle)
        y = self.radius * math.sin(angle)
        z = self.altitude
        return x, y, z

    def get_figure8_position(self, t):
        """Calculate position on figure-8 (lemniscate) trajectory."""
        omega = self.speed / (math.sqrt(2) * self.radius)
        x = self.radius * math.sin(omega * t)
        y = self.radius * math.sin(omega * t) * math.cos(omega * t)
        z = self.altitude
        return x, y, z

    def takeoff(self, target_alt=3.0):
        """Arm and takeoff to target altitude."""
        if self.pre_armed:
            rospy.loginfo("Pre-armed mode: skipping arming/OFFBOARD services")
        else:
            rospy.loginfo("Arming...")
            self.arm(True)
            rospy.sleep(2)

            # Switch to OFFBOARD mode
            for i in range(10):
                self.set_mode(0, "OFFBOARD")
                rospy.sleep(0.5)

        # Hold at initial position while switching (keep the OFFBOARD
        # setpoint stream alive long enough for a parallel arming step)
        rate = rospy.Rate(10)
        for _ in range(150):
            self.send_position(0, 0, target_alt)
            rate.sleep()

        rospy.loginfo("Takeoff complete, starting trajectory...")

    def send_position(self, x, y, z):
        """Send a position setpoint."""
        msg = PositionTarget()
        msg.header.stamp = rospy.Time.now()
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = (
            PositionTarget.IGNORE_VX |
            PositionTarget.IGNORE_VY |
            PositionTarget.IGNORE_VZ |
            PositionTarget.IGNORE_AFX |
            PositionTarget.IGNORE_AFY |
            PositionTarget.IGNORE_AFZ |
            PositionTarget.IGNORE_YAW |
            PositionTarget.IGNORE_YAW_RATE
        )
        msg.position.x = x
        msg.position.y = y
        msg.position.z = z
        self.setpoint_pub.publish(msg)

    def run(self, duration=60):
        """Execute trajectory for given duration."""
        self.takeoff(self.altitude)
        self.start_time = rospy.Time.now()
        rate = rospy.Rate(50)

        rospy.loginfo(f"Starting trajectory for {duration} seconds...")

        while not rospy.is_shutdown():
            elapsed = (rospy.Time.now() - self.start_time).to_sec()

            if elapsed > duration:
                rospy.loginfo("Trajectory complete. Landing...")
                break

            if self.trajectory == 'circle':
                x, y, z = self.get_circle_position(elapsed)
            else:
                x, y, z = self.get_figure8_position(elapsed)

            self.send_position(x, y, z)
            rate.sleep()

        # Land
        if not self.pre_armed:
            self.set_mode(0, "AUTO.LAND")
            rospy.sleep(5)
            self.arm(False)
        rospy.loginfo("Landed and disarmed.")


def main():
    parser = argparse.ArgumentParser(description='Waypoint flight controller')
    parser.add_argument('--trajectory', choices=['circle', 'figure8'],
                        default='circle', help='Trajectory type')
    parser.add_argument('--speed', type=float, default=1.5,
                        help='Flight speed in m/s')
    parser.add_argument('--radius', type=float, default=5.0,
                        help='Trajectory radius in meters')
    parser.add_argument('--altitude', type=float, default=3.0,
                        help='Flight altitude in meters')
    parser.add_argument('--duration', type=int, default=60,
                        help='Flight duration in seconds')
    parser.add_argument('--pre-armed', action='store_true',
                        help='Skip arming/OFFBOARD service calls (use raw-mavlink helper first)')
    args = parser.parse_args()

    controller = WaypointController(
        trajectory=args.trajectory,
        speed=args.speed,
        radius=args.radius,
        altitude=args.altitude,
        pre_armed=args.pre_armed
    )

    try:
        controller.run(duration=args.duration)
    except rospy.ROSInterruptException:
        pass


if __name__ == '__main__':
    main()
