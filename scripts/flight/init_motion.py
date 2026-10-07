#!/usr/bin/env python3
"""init_motion.py - pre-circle IMU+visual excitation maneuver.

Streams fast bob/sway position setpoints right after arming so VINS
visual-init sees 3D parallax AND the IMU sees changing acceleration
(non-degenerate gravity/scale observability). Publishes 20Hz on
/mavros/setpoint_raw/local. Exits after ~18s; caller then starts the
regular circle controller, which takes over the same topic.
"""
import rospy
import time
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State, PositionTarget

# (x, y, z, hold_s) in local NED-enu plane (z up)
SEQ = [
    (0.00, 0.00, 3.0, 3.5),   # initial climb
    (0.00, 1.5, 2.6, 1.7),    # sway + dip
    (0.00, 0.8, 3.5, 1.7),
    (0.00, -1.5, 2.4, 1.7),   # sway back, deeper tank
    (0.00, -0.8, 3.4, 1.7),
    (0.00, 0.0, 2.5, 1.5),
    (0.00, 0.0, 3.2, 2.0),    # settle at circle altitude
]


def main():
    rospy.init_node('init_motion', anonymous=True)
    pub = rospy.Publisher('/mavros/setpoint_raw/local', PositionTarget,
                          queue_size=10)
    rospy.sleep(2.0)          # wait for subscriber to connect
    rate = rospy.Rate(20)
    start = time.time()
    for (x, y, z, hold) in SEQ:
        end = start + hold
        rospy.loginfo('INIT_MOT seg tgt=(%.2f,%.2f,%.2f) hold=%.1f',
                      x, y, z, hold)
        while time.time() < end and not rospy.is_shutdown():
            msg = PositionTarget()
            msg.header.stamp = rospy.Time.now()
            msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
            msg.type_mask = (
                PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY |
                PositionTarget.IGNORE_VZ | PositionTarget.IGNORE_AFX |
                PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ |
                PositionTarget.IGNORE_YAW | PositionTarget.IGNORE_YAW_RATE
            )
            msg.position.x = x
            msg.position.y = y
            msg.position.z = z
            pub.publish(msg)
            rate.sleep()
        start = end
    rospy.loginfo('INIT_MOT done')
    # keep the last setpoint alive a little longer so PX4 maintains position
    end = time.time() + 2.0
    while time.time() < end and not rospy.is_shutdown():
        msg = PositionTarget()
        msg.header.stamp = rospy.Time.now()
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = (
            PositionTarget.IGNORE_VX | PositionTarget.IGNORE_VY |
            PositionTarget.IGNORE_VZ | PositionTarget.IGNORE_AFX |
            PositionTarget.IGNORE_AFY | PositionTarget.IGNORE_AFZ |
            PositionTarget.IGNORE_YAW | PositionTarget.IGNORE_YAW_RATE
        )
        msg.position.x = 0.0
        msg.position.y = 0.0
        msg.position.z = 3.2
        pub.publish(msg)
        rate.sleep()
    rospy.loginfo('INIT_MOT exit')


if __name__ == '__main__':
    main()