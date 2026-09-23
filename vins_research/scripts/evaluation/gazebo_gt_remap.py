#!/usr/bin/env python3
"""
Remap Gazebo model_states into separate trajectory topics so RViz can show
ground truth alongside the VINS estimate.

Usage:
    python3 gazebo_gt_remap.py

Subscribes: /gazebo/model_states
Publishes:  /gazebo/model_states_gt (nav_msgs/Path of target model)
"""
import rospy
import numpy as np
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped
from gazebo_msgs.msg import ModelStates
from std_msgs.msg import Header


MODEL_NAME = 'iris'


class GTRepublisher:
    def __init__(self):
        rospy.init_node('gazebo_gt_remap', anonymous=True)
        self.model_name = rospy.get_param('~model', MODEL_NAME)
        self.pub = rospy.Publisher('/gazebo/model_states_gt', Path, queue_size=10)
        self.sub = rospy.Subscriber('/gazebo/model_states', ModelStates, self.cb)

    def cb(self, msg):
        if self.model_name not in msg.name:
            return
        idx = msg.name.index(self.model_name)
        pose = msg.pose[idx]

        path = Path()
        path.header = Header(stamp=rospy.Time.now(), frame_id='world')

        ps = PoseStamped()
        ps.header = path.header
        ps.pose = pose
        path.poses.append(ps)

        self.pub.publish(path)


if __name__ == '__main__':
    gt = GTRepublisher()
    rospy.spin()